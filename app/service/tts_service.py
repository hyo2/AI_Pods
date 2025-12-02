# app/services/podcast/tts_service.py
import re
import time
import uuid
import logging
from typing import List, Dict, Any
from vertexai.generative_models import GenerativeModel
from .utils import sanitize_tts_text, chunk_text, base64_to_bytes, pcm_to_wav

logger = logging.getLogger(__name__)

# TTS 설정
MAX_RETRIES = 10
BASE_DELAY = 2.0
INTER_CHUNK_DELAY = 1.0
SPEAKER_TURN_DELAY = 0.5


class TTSService:
    """Vertex AI TTS 서비스"""
    
    def __init__(self):
        self.model = GenerativeModel("gemini-2.5-flash-preview-tts")
        self.speaker_map = {
            "진행자": "Charon",
            "게스트": "Puck"
        }
    
    def generate_audio(
        self, 
        script: str, 
        host_name: str, 
        guest_name: str
    ) -> tuple[List[Dict[str, Any]], List[str]]:
        """
        스크립트를 TTS로 변환
        
        Returns:
            (audio_metadata, wav_files)
        """
        logger.info("Multi-Speaker TTS 변환 시작...")
        
        audio_metadata = []
        
        # 스크립트 파싱
        segments = re.split(r"\[([^\]]+)\]", script)
        
        if len(segments) <= 1:
            segments = ["", "진행자", script]
        
        base_filename = f"podcast_temp_{uuid.uuid4().hex[:4]}"
        i = 1
        
        while i < len(segments):
            speaker = segments[i].strip()
            raw_content = segments[i + 1].strip()
            i += 2
            
            if not raw_content:
                continue
            
            # 긴 텍스트는 청크로 분할
            content_chunks = chunk_text(raw_content, max_chars=200)
            
            for chunk_index, content in enumerate(content_chunks):
                sanitized_content = sanitize_tts_text(content, host_name, guest_name)
                
                if not sanitized_content:
                    continue
                
                voice_name = self.speaker_map.get(speaker, "Charon")
                
                # TTS 생성 (재시도 로직 포함)
                audio_file = self._generate_single_audio(
                    sanitized_content,
                    voice_name,
                    speaker,
                    base_filename,
                    len(audio_metadata),
                    chunk_index
                )
                
                if audio_file:
                    audio_metadata.append(audio_file)
                
                # 청크 간 대기
                time.sleep(INTER_CHUNK_DELAY)
            
            # 화자 전환 시 대기
            if content_chunks:
                time.sleep(SPEAKER_TURN_DELAY)
        
        wav_files = [m['file'] for m in audio_metadata]
        
        logger.info(f"TTS 변환 완료: {len(wav_files)}개 파일 생성")
        
        return audio_metadata, wav_files
    
    def _generate_single_audio(
        self,
        text: str,
        voice_name: str,
        speaker: str,
        base_filename: str,
        index: int,
        chunk_index: int
    ) -> Dict[str, Any] | None:
        """단일 오디오 청크 생성 (재시도 로직 포함)"""
        
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
                
                candidate = response.candidates[0]
                audio_data_part = next(
                    (p for p in candidate.content.parts
                     if p.inline_data and p.inline_data.mime_type.startswith("audio/")),
                    None
                )
                
                if not audio_data_part:
                    raise Exception("응답에 오디오 데이터가 누락됨")
                
                # PCM을 WAV로 변환
                pcm_bytes = base64_to_bytes(audio_data_part.inline_data.data)
                duration_seconds = len(pcm_bytes) / 48000.0
                
                wav_bytes = pcm_to_wav(pcm_bytes, sample_rate=24000)
                output_file = f"{base_filename}_{index + 1}_{speaker}_{chunk_index}.wav"
                
                with open(output_file, "wb") as f:
                    f.write(wav_bytes)
                
                return {
                    'speaker': speaker,
                    'text': text,
                    'duration': duration_seconds,
                    'file': output_file
                }
                
            except Exception as e:
                if attempt < MAX_RETRIES - 1:
                    delay = BASE_DELAY * (2 ** attempt)
                    logger.warning(f"TTS 재시도 {attempt + 1}/{MAX_RETRIES} ({delay}초 후)")
                    time.sleep(delay)
                else:
                    logger.error(f"TTS 생성 실패: {str(e)}")
                    return None
        
        return None