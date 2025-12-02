# -*- coding: utf-8 -*-
# 필요한 라이브러리들을 가져오고 로깅을 설정합니다.
import os
import re
import uuid
import struct
import base64
import pdfplumber
import subprocess
import logging
import time
from typing import List, Dict, Any, Tuple
from google.oauth2 import service_account
from google.api_core.exceptions import NotFound
from vertexai.generative_models import GenerativeModel, FinishReason

# 로깅 설정
logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')

# TTS API 호출 재시도 설정
MAX_RETRIES = 10
BASE_DELAY = 2.0
INTER_CHUNK_DELAY = 1.0

# 최소 유효 PCM 데이터 크기 (24kHz, 16bit, 모노 = 1초당 48,000 바이트)
MIN_PCM_SIZE_BYTES = 48000 

# =========================
# 1. 헬퍼 함수: PCM 데이터 처리
# =========================
def base64_to_bytes(base64_string: str) -> bytes:
    """Base64 문자열을 바이트로 디코딩합니다."""
    try:
        # Base64 문자열이 이미 bytes인 경우 처리
        if isinstance(base64_string, bytes):
            return base64_string
        
        # padding 문제 해결
        missing_padding = len(base64_string) % 4
        if missing_padding:
            base64_string += '=' * (4 - missing_padding)
        
        return base64.b64decode(base64_string)
    except Exception as e:
        logging.error(f"Base64 디코딩 실패: {e}")
        logging.error(f"Base64 문자열 타입: {type(base64_string)}")
        logging.error(f"Base64 문자열 길이: {len(base64_string) if hasattr(base64_string, '__len__') else 'N/A'}")
        # 이미 bytes인 경우 그대로 반환
        if isinstance(base64_string, bytes):
            return base64_string
        return b""

def pcm_to_wav(pcm_data: bytes, sample_rate: int = 24000, num_channels: int = 1, bits_per_sample: int = 16) -> bytes:
    """16비트 서명된 PCM 바이트 데이터를 WAV 파일 형식으로 변환합니다."""
    byte_rate = sample_rate * num_channels * bits_per_sample // 8
    block_align = num_channels * bits_per_sample // 8
    subchunk2_size = len(pcm_data)
    chunk_size = 36 + subchunk2_size
    
    wav_header = b''
    wav_header += b'RIFF'
    wav_header += struct.pack('<I', chunk_size)
    wav_header += b'WAVE'
    
    wav_header += b'fmt '
    wav_header += struct.pack('<I', 16)
    wav_header += struct.pack('<H', 1)
    wav_header += struct.pack('<H', num_channels)
    wav_header += struct.pack('<I', sample_rate)
    wav_header += struct.pack('<I', byte_rate)
    wav_header += struct.pack('<H', block_align)
    wav_header += struct.pack('<H', bits_per_sample)
    
    wav_header += b'data'
    wav_header += struct.pack('<I', subchunk2_size)
    
    return wav_header + pcm_data

def sanitize_tts_text(text: str) -> str:
    """TTS 모델이 인식하지 못할 수 있는 특수 문자를 제거하고 텍스트를 정리합니다."""
    text = re.sub(r"\s+", " ", text).strip()
    text = text.replace("OOO", "김철수").replace("OO", "이하나")
    
    # 제어 문자 및 보이지 않는 문자 제거
    text = re.sub(r'[\x00-\x1f\x7f-\x9f\ufeff]', '', text) 
    
    # 한글 자모나 알 수 없는 특수 기호 제거
    text = re.sub(r"[^가-힣a-zA-Z0-9.,?! ]", "", text)
    return text.strip()

def chunk_text(text: str, max_chars: int = 200) -> List[str]:
    """긴 텍스트를 문장 경계를 유지하며 지정된 최대 문자 수로 분할합니다."""
    text = re.sub(r"\s+", " ", text).strip()
    if len(text) <= max_chars:
        return [text]

    chunks = []
    current_chunk = ""
    sentences = re.split(r'([.?!])\s*', text)
    
    if len(sentences) % 2 != 0:
        sentences.append("") 
        
    for i in range(0, len(sentences), 2):
        sentence = sentences[i].strip()
        delimiter = sentences[i+1] if i + 1 < len(sentences) else ""
        full_sentence = sentence + delimiter
        
        if not full_sentence.strip():
            continue

        if len(current_chunk) + len(full_sentence) > max_chars and current_chunk:
            chunks.append(current_chunk.strip())
            current_chunk = full_sentence
        else:
            current_chunk += full_sentence
            
    if current_chunk:
        chunks.append(current_chunk.strip())
        
    return chunks

# =========================
# 2. 메인 클래스: 팟캐스트 생성기
# =========================
class PodcastGenerator:
    """PDF 텍스트 추출부터 TTS를 통한 오디오 생성 및 병합까지 전 과정을 처리하는 클래스입니다."""
    
    def __init__(self, project_id: str, region: str, sa_file: str):
        self.PROJECT_ID = project_id
        self.REGION = region
        self.SA_FILE = sa_file
        self.MODEL_NAME_TEXT = os.getenv("VERTEX_AI_MODEL_TEXT", "gemini-2.5-flash")
        self.MODEL_NAME_TTS = "gemini-2.5-flash-preview-tts"
        self.SPEAKER_MAP = {"진행자": "Charon", "게스트": "Puck"}
        self.CREDENTIALS = self._load_credentials()

        try:
            import vertexai
            self.HAS_VERTEXAI = True
            if self.CREDENTIALS:
                vertexai.init(project=self.PROJECT_ID, location=self.REGION, credentials=self.CREDENTIALS)
        except ImportError:
            self.HAS_VERTEXAI = False
            logging.error("vertexai SDK가 설치되어 있지 않습니다.")
        
        if not self.HAS_VERTEXAI:
             raise RuntimeError("Vertex AI SDK를 사용할 수 없습니다.")

    def _load_credentials(self):
        """서비스 계정 파일에서 인증 정보를 로드합니다."""
        if not all([self.PROJECT_ID, self.REGION]):
            raise RuntimeError("PROJECT_ID와 REGION 환경 변수를 확인하세요.")
        
        if os.path.exists(self.SA_FILE):
            try:
                logging.info(f"Vertex AI 서비스 계정 파일 로드 시도: {self.SA_FILE}")
                return service_account.Credentials.from_service_account_file(self.SA_FILE)
            except Exception as e:
                raise RuntimeError(f"Vertex AI 서비스 계정 파일 로드 오류: {e}")
        else:
            logging.warning(f"Vertex AI 서비스 계정 파일을 찾을 수 없습니다: {self.SA_FILE}. ADC를 시도합니다.")
            return None

    # =========================
    # 3. PDF → 텍스트 추출
    # =========================
    def _extract_text_from_pdf(self, pdf_path: str) -> str:
        """PDF에서 텍스트를 추출하고 불필요한 마크다운을 제거합니다."""
        logging.info("PDF 텍스트 추출 중...")
        text = ""
        try:
            with pdfplumber.open(pdf_path) as pdf:
                for page in pdf.pages:
                    page_text = page.extract_text() or ""
                    text += page_text + "\n"
        except FileNotFoundError:
            raise FileNotFoundError(f"PDF 파일을 찾을 수 없습니다: {pdf_path}")
        
        text = re.sub(r"[\*\U00010000-\U0010ffff]|#", "", text)
        return text.strip()

    # =========================
    # 4. 텍스트 → 팟캐스트 스크립트
    # =========================
    def _generate_podcast_script(self, text_to_convert: str, max_output_tokens: int = 8192) -> str:
        """Gemini 모델을 사용하여 텍스트를 멀티 스피커 팟캐스트 스크립트로 변환합니다."""
        if not self.CREDENTIALS:
            raise RuntimeError("Vertex AI 인증 정보를 로드할 수 없습니다.")
            
        model = GenerativeModel(self.MODEL_NAME_TEXT)

        prompt = f"""
        아래 텍스트를 분석하여 두 명의 화자(진행자, 게스트)가 대화하는 형식의 팟캐스트 스크립트를 한국어로 작성해 주세요.
        각 대화는 반드시 "[화자 이름] 내용"의 형식을 지켜야 하며, 화자 이름 뒤에 콜론(:)을 포함하지 마세요.
        (예: [진행자] 안녕하세요. [게스트] 반갑습니다.)
        
        원본 텍스트:
        ---
        {text_to_convert}
        ---
        """
        
        config = {
            "max_output_tokens": max_output_tokens,
            "temperature": 0.5,
        }

        try:
            response = model.generate_content(prompt, generation_config=config)
        except NotFound as e:
            raise RuntimeError(f"모델 {self.MODEL_NAME_TEXT}을(를) 찾을 수 없습니다: {str(e)}") from e

        script_text = getattr(response, "text", "")

        if not script_text:
            raise RuntimeError(f"GenerativeModel이 텍스트를 반환하지 않았습니다. 응답: {response}")

        script_text = re.sub(r"```python|```json|```text|```", "", script_text, flags=re.IGNORECASE)
        script_text = re.sub(r"[\*\U00010000-\U0010ffff]|#", "", script_text)
        
        return script_text.strip()

    # =========================
    # 5. TTS API 진단 함수
    # =========================
    def diagnose_api_issue(self, sample_text: str = None):
        """TTS API 문제를 진단하는 헬퍼 함수"""
        if sample_text is None:
            sample_text = "안녕하세요 여러분. 오늘은 인공지능 음성 합성 기술에 대해 이야기해 보겠습니다. 이 기술은 텍스트를 자연스러운 음성으로 변환하는 놀라운 기술입니다."
        
        print("\n" + "="*60)
        print("=== TTS API 진단 시작 ===")
        print("="*60)
        print(f"테스트 텍스트: '{sample_text}'")
        print(f"텍스트 길이: {len(sample_text)}자")
        
        tts_model = GenerativeModel(self.MODEL_NAME_TTS)
        
        # 다양한 화자로 테스트
        test_voices = ["Charon", "Puck", "Kore", "Fenrir"]
        
        for voice in test_voices:
            print(f"\n[{voice}] 테스트 중...")
            try:
                config = {
                    "response_modalities": ["AUDIO"],
                    "speech_config": {
                        "voice_config": {
                            "prebuilt_voice_config": {
                                "voice_name": voice
                            }
                        }
                    }
                }
                
                # 추가 디버깅: 요청 구조 확인
                print(f"  - 요청 config: {config}")
                
                response = tts_model.generate_content(
                    contents=[{"role": "user", "parts": [{"text": sample_text}]}],
                    generation_config=config
                )
                
                candidate = response.candidates[0]
                finish_reason = candidate.finish_reason.name
                
                audio_part = next(
                    (p for p in candidate.content.parts 
                     if p.inline_data and p.inline_data.mime_type.startswith("audio/")), 
                    None
                )
                
                if audio_part:
                    pcm_bytes = base64_to_bytes(audio_part.inline_data.data)
                    duration_sec = len(pcm_bytes) / 48000
                    print(f"  ✓ 성공: {len(pcm_bytes)} bytes ({duration_sec:.2f}초)")
                    print(f"  - 종료 이유: {finish_reason}")
                else:
                    print(f"  ✗ 실패: 오디오 데이터 없음")
                    print(f"  - 종료 이유: {finish_reason}")
                    
            except Exception as e:
                print(f"  ✗ 오류: {str(e)}")
        
        print("\n" + "="*60)
        print("=== 진단 완료 ===")
        print("="*60 + "\n")

    # =========================
    # 6. Multi-Speaker TTS (개선된 버전)
    # =========================
    def _tts_multi_speaker(self, text: str, base_filename: str) -> List[str]:
        """스크립트를 TTS 모델로 변환하여 임시 WAV 파일을 생성합니다."""
        tts_model = GenerativeModel(self.MODEL_NAME_TTS)
        wav_files = []
        segments = re.split(r"\[([^\]]+)\]", text)
        
        if len(segments) <= 1:
            logging.warning("스크립트에서 '[화자] 내용' 패턴을 찾을 수 없습니다.")
            if not text.strip(): 
                return []
            segments = ["", "진행자", text]
        
        total_segments_estimate = (len(segments) - 1) // 2 
        logging.info(f"총 {total_segments_estimate}개의 대화 세그먼트를 TTS로 요청합니다.")

        current_segment_count = 0
        i = 1 
        
        while i < len(segments):
            speaker = segments[i].strip()
            raw_content = segments[i + 1].strip()
            i += 2 

            if not raw_content: 
                continue
            current_segment_count += 1
            
            # 텍스트 청크 분할 (200자 단위)
            content_chunks = chunk_text(raw_content, max_chars=200)
            
            for chunk_index, content in enumerate(content_chunks):
                sanitized_content = sanitize_tts_text(content)
                
                if not sanitized_content:
                    logging.warning(f"세그먼트 {current_segment_count} (part {chunk_index+1})의 텍스트가 비어 있어 건너뜁니다.")
                    continue

                voice_name = self.SPEAKER_MAP.get(speaker, "Charon")
                progress_label = f"[{current_segment_count}/{total_segments_estimate} - part {chunk_index+1}/{len(content_chunks)}]"
                
                # 텍스트 정보 출력
                text_length = len(sanitized_content)
                char_count = len(sanitized_content.replace(" ", ""))
                
                print(f"\n{progress_label} TTS 요청 준비:")
                print(f"  - 화자: {speaker} ({voice_name})")
                print(f"  - 텍스트 길이: {text_length}자 (공백 제외: {char_count}자)")
                print(f"  - 내용: '{sanitized_content[:80]}...'")
                
                if char_count < 10:
                    logging.warning(f"{progress_label} 텍스트가 너무 짧습니다 ({char_count}자).")
                
                success = False
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
                        
                        print(f"  시도 {attempt+1}/{MAX_RETRIES}...")
                        
                        response = tts_model.generate_content(
                            contents=[{"role": "user", "parts": [{"text": sanitized_content}]}],
                            generation_config=config
                        )
                        
                        # 응답 분석
                        if not response.candidates:
                            raise Exception("API 응답에 candidates가 없습니다.")
                        
                        candidate = response.candidates[0]
                        finish_reason = candidate.finish_reason.name
                        
                        print(f"  → API 종료 이유: {finish_reason}")
                        
                        if finish_reason != 'STOP':
                            print(f"  → 경고: 비정상 종료 ({finish_reason})")
                            if hasattr(candidate, 'safety_ratings'):
                                print(f"  → Safety Ratings: {candidate.safety_ratings}")
                        
                        # 오디오 데이터 추출
                        audio_data_part = next(
                            (p for p in candidate.content.parts 
                             if p.inline_data and p.inline_data.mime_type.startswith("audio/")), 
                            None
                        )
                        
                        if not audio_data_part:
                            print(f"  → 오류: 응답에 오디오 데이터가 없습니다.")
                            print(f"  → 응답 구조: {[p.WhichOneof('data') for p in candidate.content.parts]}")
                            raise Exception("TTS 응답에 오디오 데이터가 누락됨.")
                        
                        # Base64 디코딩 및 크기 확인
                        base64_data = audio_data_part.inline_data.data
                        base64_length = len(base64_data)
                        print(f"  → Base64 데이터 길이: {base64_length}")
                        print(f"  → Base64 데이터 타입: {type(base64_data)}")
                        
                        # 데이터가 이미 bytes인지 확인
                        if isinstance(base64_data, bytes):
                            pcm_bytes = base64_data
                            print(f"  → 데이터가 이미 bytes 형태입니다.")
                        else:
                            pcm_bytes = base64_to_bytes(base64_data)
                        
                        pcm_size = len(pcm_bytes)
                        
                        print(f"  → PCM 데이터 크기: {pcm_size} bytes ({pcm_size/48000:.2f}초 분량)")
                        
                        # 임계값 체크 완전 제거 - 어떤 크기든 일단 사용
                        if pcm_size < 100:
                            logging.warning(f"  → 경고: PCM 데이터가 매우 작음 ({pcm_size} bytes). 거의 무음일 수 있습니다.")
                        
                        # 데이터가 아무리 작아도 WAV 파일로 생성
                        wav_bytes = pcm_to_wav(pcm_bytes, sample_rate=24000)
                        output_file = f"{base_filename}_{len(wav_files) + 1}_{speaker}_{chunk_index}.wav"
                        
                        with open(output_file, "wb") as f:
                            f.write(wav_bytes)
                        
                        final_wav_size = os.path.getsize(output_file)
                        print(f"  ✓ 생성됨: {output_file} ({final_wav_size} bytes)")
                        
                        if pcm_size < 1000:
                            print(f"  ⚠️  경고: 생성된 오디오가 매우 짧을 수 있습니다.")
                        
                        wav_files.append(output_file)
                        success = True
                        
                        time.sleep(INTER_CHUNK_DELAY)
                        break
                        
                    except Exception as e:
                        print(f"  ✗ 실패: {str(e)}")
                        
                        if attempt < MAX_RETRIES - 1:
                            delay = BASE_DELAY * (2 ** attempt)
                            print(f"  → {delay:.1f}초 후 재시도...")
                            time.sleep(delay)
                        else:
                            print(f"  ✗ 최종 실패: {MAX_RETRIES}회 시도 후 포기")
                
                if not success:
                    print(f"\n경고: {progress_label} 세그먼트 생성 실패. 다음 세그먼트로 이동합니다.\n")

        return wav_files

    # =========================
    # 7. 오디오 파일 병합
    # =========================
    def _combine_audio_files(self, input_files: List[str], output_filename: str = "final_podcast_episode.mp3") -> str or None:
        """FFmpeg을 사용하여 여러 WAV 파일을 하나의 MP3 파일로 병합합니다."""
        if not input_files:
            logging.warning("병합할 오디오 파일이 없습니다.")
            return None
            
        list_file_path = "concat_list.txt"
        try:
            with open(list_file_path, "w", encoding="utf-8") as f:
                for file in input_files:
                    f.write(f"file '{os.path.abspath(file)}'\n")

            print(f"FFMPEG: {len(input_files)}개 오디오 파일을 {output_filename}로 병합 중...")
            
            command = [
                "ffmpeg", "-f", "concat", "-safe", "0", "-i", list_file_path,
                "-c:a", "libmp3lame", "-b:a", "192k", "-y", output_filename
            ]
            
            subprocess.run(command, check=True, capture_output=True, text=True, encoding="utf-8")
            
            # 임시 파일 정리
            os.remove(list_file_path)
            for file in input_files:
                if os.path.exists(file):
                    os.remove(file)
                
            print(f"FINAL SUCCESS: 최종 팟캐스트 파일 생성 완료: {output_filename}")
            return output_filename
            
        except FileNotFoundError:
            print("\n[FFmpeg 오류] FFmpeg을 찾을 수 없습니다. 병합을 건너뜁니다.")
            print("  → 임시 WAV 파일들은 현재 폴더에 남아 있습니다.")
            return None
        except subprocess.CalledProcessError as e:
            print(f"\n[FFmpeg 오류] FFmpeg 실행 중 오류 발생: {e}")
            print(f"  → Stderr: {e.stderr}")
            print("  → 임시 WAV 파일들은 현재 폴더에 남아 있습니다.")
            return None
        except Exception as e:
            print(f"FFmpeg 병합 중 예상치 못한 오류 발생: {e}")
            return None

    # =========================
    # 8. 전체 실행 메서드
    # =========================
    def generate_podcast(self, pdf_file: str) -> str or None:
        """전체 팟캐스트 생성 파이프라인을 실행합니다."""
        try:
            # 1. 텍스트 추출
            text = self._extract_text_from_pdf(pdf_file)
            if not text:
                print("경고: PDF에서 추출된 텍스트가 없습니다.")
                return None

            # 2. 스크립트 생성
            print(f"STEP 1/3: 팟캐스트 스크립트 생성 중 (모델: {self.MODEL_NAME_TEXT})...")
            script = self._generate_podcast_script(text, max_output_tokens=8192)
            
            print("\n--- 팟캐스트 스크립트 미리보기 (첫 500자) ---\n")
            print(script[:500] + "..." if len(script) > 500 else script)
            print("\n-----------------------\n")

            # 3. TTS 변환
            print(f"STEP 2/3: Multi-Speaker TTS 변환 중 (모델: {self.MODEL_NAME_TTS})...")
            base_filename = f"podcast_temp_{uuid.uuid4().hex[:8]}"
            wav_files = self._tts_multi_speaker(script, base_filename=base_filename)
            
            if not wav_files:
                print("\nTTS 변환 결과, 생성된 오디오 파일이 없습니다.")
                return None

            # 4. 오디오 병합
            print("STEP 3/3: 오디오 파일 병합 중 (FFmpeg)...")
            final_file = self._combine_audio_files(wav_files)

            return final_file
        
        except Exception as e:
            print(f"\n[오류 발생]: {e}")
            return None

# =========================
# 9. CLI 실행 로직
# =========================
if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="PDF를 멀티 스피커 팟캐스트로 변환합니다.")
    
    PROJECT_ID_ENV = os.getenv("VERTEX_AI_PROJECT_ID")
    REGION_ENV = os.getenv("VERTEX_AI_REGION", "us-central1")
    SA_FILE_ENV = os.getenv("VERTEX_AI_SERVICE_ACCOUNT_FILE") or \
                   r"C:\Users\USER\Desktop\securityKey\companyKey\vertex-ai-service-account.json" 
    DEFAULT_PDF_PATH = r"C:\Users\USER\Desktop\feeling\팟캐스트_에이전트_PRD.pdf" 
    
    parser.add_argument("pdf", nargs="?", help=f"PDF 파일 경로", default=DEFAULT_PDF_PATH) 
    parser.add_argument("--check", action="store_true", help="환경 점검만 수행")
    parser.add_argument("--diagnose", action="store_true", help="TTS API 진단 수행")
    args = parser.parse_args()
    
    if args.check:
        print("=== 환경 진단 ===")
        print(f"PROJECT_ID: {'SET' if PROJECT_ID_ENV else 'MISSING'}")
        print(f"REGION: {REGION_ENV}")
        print(f"SA File: {SA_FILE_ENV} | Status: {'Found' if os.path.exists(SA_FILE_ENV) else 'MISSING'}")
        
    elif args.diagnose:
        try:
            generator = PodcastGenerator(PROJECT_ID_ENV, REGION_ENV, SA_FILE_ENV)
            generator.diagnose_api_issue()
        except Exception as e:
            print(f"진단 실패: {e}")
            exit(1)
    else:
        try:
            generator = PodcastGenerator(PROJECT_ID_ENV, REGION_ENV, SA_FILE_ENV)
            final_podcast_path = generator.generate_podcast(args.pdf)
            
            if final_podcast_path:
                print(f"\n✨ 모든 작업 완료! 최종 팟캐스트 파일: {final_podcast_path}")
        except Exception as e:
            print(f"\n[초기화 오류]: {e}")
            exit(1)
