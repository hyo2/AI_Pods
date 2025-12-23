# app/services/podcast/tts_service.py
import os
import re
import time
import uuid
import logging
import subprocess
from typing import List, Dict, Any
from vertexai.generative_models import GenerativeModel
from .utils import sanitize_tts_text, chunk_text, base64_to_bytes, pcm_to_wav

logger = logging.getLogger(__name__)

MAX_RETRIES = 5           
BASE_DELAY = 1.0          
INTER_CHUNK_DELAY = 1.0   
SPEAKER_TURN_DELAY = 0.5  

FIXED_STUDENT_VOICE = "Leda"
STUDENT_PITCH_FACTOR = 1.15


def get_wav_output_dir() -> str:
    """환경에 맞는 WAV 출력 디렉토리 반환"""
    base = os.getenv("BASE_OUTPUT_DIR", "outputs")
    return os.path.join(base, "podcasts", "wav")


class TTSService:
    """Vertex AI TTS 서비스"""
    
    def __init__(self):
        self.model = GenerativeModel("gemini-2.5-flash-preview-tts") 
    
    def generate_audio(
        self, 
        script: str, 
        host_name: str, 
        guest_name: str | None = None
    ) -> tuple[List[Dict[str, Any]], List[str]]:
        """스크립트를 TTS로 변환"""
        logger.info(f"TTS 변환 시작 - 선생님: {host_name}, 학생: {FIXED_STUDENT_VOICE} (Pitch x{STUDENT_PITCH_FACTOR})")
        
        audio_metadata = []
        segments = re.split(r"\[([^\]]+)\]", script)
        
        if len(segments) <= 1:
            segments = ["", "선생님", script]
        
        base_filename = f"podcast_temp_{uuid.uuid4().hex[:4]}"
        i = 1
        
        while i < len(segments):
            speaker_tag = segments[i].strip()
            raw_content = segments[i + 1].strip()
            i += 2
            
            if not raw_content:
                continue
            
            content_chunks = chunk_text(raw_content, max_chars=200)
            
            for chunk_index, content in enumerate(content_chunks):
                sanitized_content = sanitize_tts_text(content, host_name, guest_name)
                
                if not sanitized_content:
                    continue
                
                voice_name = host_name
                is_student = False
                
                if any(role in speaker_tag for role in ["선생", "진행", "teacher", "host"]):
                    voice_name = host_name
                elif any(role in speaker_tag for role in ["학생", "게스트", "student", "guest"]):
                    voice_name = FIXED_STUDENT_VOICE
                    is_student = True
                
                audio_file = self._generate_single_audio(
                    sanitized_content,
                    voice_name,
                    speaker_tag,
                    base_filename,
                    len(audio_metadata),
                    chunk_index,
                    is_student=is_student
                )
                
                if audio_file:
                    audio_metadata.append(audio_file)
                
                time.sleep(INTER_CHUNK_DELAY)
            
            if content_chunks:
                time.sleep(SPEAKER_TURN_DELAY)
        
        wav_files = [m['file'] for m in audio_metadata]
        logger.info(f"TTS 변환 완료: 총 {len(wav_files)}개 파일")
        
        return audio_metadata, wav_files
    
    def _generate_single_audio(
        self,
        text: str,
        voice_name: str,
        speaker: str,
        base_filename: str,
        index: int,
        chunk_index: int,
        is_student: bool = False
    ) -> Dict[str, Any] | None:
        """단일 오디오 청크 생성 및 후처리(피치 조절)"""
        
        for attempt in range(MAX_RETRIES):
            try:
                config = {
                    "response_modalities": ["AUDIO"],
                    "speech_config": {
                        "voice_config": {
                            "prebuilt_voice_config": {"voice_name": voice_name},
                        }
                    }
                }
                
                response = self.model.generate_content(
                    contents=[{"role": "user", "parts": [{"text": text}]}],
                    generation_config=config
                )
                
                if not response.candidates:
                     raise Exception("Candidate 없음")

                candidate = response.candidates[0]
                audio_data_part = next(
                    (p for p in candidate.content.parts
                     if p.inline_data and p.inline_data.mime_type.startswith("audio/")),
                    None
                )
                
                if not audio_data_part:
                    raise Exception("오디오 데이터 누락")
                
                pcm_bytes = base64_to_bytes(audio_data_part.inline_data.data)
                
                sample_rate = 24000
                duration_seconds = len(pcm_bytes) / (sample_rate * 2)
                
                # ✅ 환경 변수 기반 경로 사용
                output_dir = get_wav_output_dir()
                os.makedirs(output_dir, exist_ok=True)
                
                safe_speaker = re.sub(r"[^a-zA-Z0-9가-힣]", "", speaker)
                output_file = os.path.join(output_dir, f"{base_filename}_{index + 1}_{safe_speaker}_{chunk_index}.wav")
                
                wav_bytes = pcm_to_wav(pcm_bytes, sample_rate=sample_rate)
                
                with open(output_file, "wb") as f:
                    f.write(wav_bytes)

                if is_student:
                    temp_file = output_file.replace(".wav", "_temp.wav")
                    os.rename(output_file, temp_file)
                    
                    try:
                        new_rate = int(sample_rate * STUDENT_PITCH_FACTOR)
                        
                        command = [
                            "ffmpeg", "-i", temp_file,
                            "-af", f"asetrate={new_rate},aresample={sample_rate}",
                            "-y", output_file
                        ]
                        
                        subprocess.run(
                            command, 
                            check=True, 
                            capture_output=True 
                        )
                        
                        os.remove(temp_file)
                        duration_seconds = duration_seconds / STUDENT_PITCH_FACTOR
                        
                    except Exception as e:
                        logger.error(f"피치 조절 실패 (원본 사용): {e}")
                        if os.path.exists(temp_file):
                            os.rename(temp_file, output_file)

                return {
                    'speaker': speaker,
                    'text': text,
                    'duration': duration_seconds,
                    'file': output_file
                }
                
            except Exception as e:
                if "429" in str(e) or "quota" in str(e).lower():
                    wait_time = 10.0 * (attempt + 1)
                    logger.warning(f"🚨 쿼터 주의(429) - {wait_time}초 대기...")
                    time.sleep(wait_time)
                    continue
                
                if attempt < MAX_RETRIES - 1:
                    delay = BASE_DELAY * (2 ** attempt)
                    logger.warning(f"TTS 재시도 {attempt + 1}/{MAX_RETRIES} ({delay:.1f}초 후)")
                    time.sleep(delay)
                else:
                    logger.error(f"TTS 최종 실패: {str(e)}")
                    return None
        
        return None