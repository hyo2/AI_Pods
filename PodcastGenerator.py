# -*- coding: utf-8 -*-
import os
import re
import uuid
import struct
import base64
import subprocess
import logging
import time
import requests
from typing import List, Dict, Any, Tuple, TypedDict, Annotated
from operator import add
from bs4 import BeautifulSoup
from docx import Document
import pdfplumber

# LangGraph imports
from langgraph.graph import StateGraph, END
from langgraph.checkpoint.memory import MemorySaver

# Google Cloud & Vertex AI Libraries
from google.oauth2 import service_account
from google.api_core.exceptions import NotFound
from vertexai.generative_models import GenerativeModel
import vertexai

# 로깅 설정
logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')

# TTS API 호출 재시도 설정
MAX_RETRIES = 10
BASE_DELAY = 2.0
INTER_CHUNK_DELAY = 1.0
SPEAKER_TURN_DELAY = 0.5

# =========================
# State 정의
# =========================
class PodcastState(TypedDict):
    """팟캐스트 생성 워크플로우의 상태를 정의합니다."""
    sources: List[str]
    extracted_texts: Annotated[List[str], add]
    combined_text: str
    script: str
    audio_metadata: List[Dict[str, Any]]
    wav_files: List[str]
    final_podcast_path: str
    transcript_path: str
    errors: Annotated[List[str], add]
    current_step: str
    project_id: str
    region: str
    sa_file: str
    host_name: str
    guest_name: str

# =========================
# 헬퍼 함수
# =========================
def generate_korean_names() -> Tuple[str, str]:
    """한국 이름을 자동으로 생성합니다."""
    surnames = ["김", "이", "박", "최", "정", "강", "조", "윤", "장", "임", "한", "오", "서", "신", "권", "황", "안", "송", "류", "전"]
    given_names_host = ["지수", "민준", "서연", "하준", "서준", "도윤", "예은", "시우", "지우", "수빈", "하윤", "지민", "은우", "채원", "유진"]
    given_names_guest = ["준서", "현우", "지훈", "민서", "지안", "예준", "서현", "우진", "다은", "시윤", "민재", "수현", "유나", "정우", "하은"]
    
    import random
    host_name = random.choice(surnames) + random.choice(given_names_host)
    guest_name = random.choice(surnames) + random.choice(given_names_guest)
    
    # 혹시 같은 이름이 생성되면 다시 생성
    while host_name == guest_name:
        guest_name = random.choice(surnames) + random.choice(given_names_guest)
    
    return host_name, guest_name

def base64_to_bytes(base64_string: str) -> bytes:
    """Base64 문자열을 바이트로 디코딩합니다."""
    try:
        if isinstance(base64_string, bytes):
            return base64_string
        missing_padding = len(base64_string) % 4
        if missing_padding:
            base64_string += '=' * (4 - missing_padding)
        return base64.b64decode(base64_string)
    except Exception as e:
        logging.error(f"Base64 디코딩 실패: {e}")
        return b""

def pcm_to_wav(pcm_data: bytes, sample_rate: int = 24000, num_channels: int = 1, bits_per_sample: int = 16) -> bytes:
    """16비트 서명된 PCM 바이트 데이터를 WAV 파일 형식으로 변환합니다."""
    byte_rate = sample_rate * num_channels * bits_per_sample // 8
    block_align = num_channels * bits_per_sample // 8
    subchunk2_size = len(pcm_data)
    chunk_size = 36 + subchunk2_size
    
    wav_header = b'RIFF'
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
    text = re.sub(r'[\x00-\x1f\x7f-\x9f\ufeff]', '', text)
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

def sanitize_tts_text_wrapper(text: str, host_name: str, guest_name: str) -> str:
    """TTS 텍스트 정리를 위한 래퍼 함수"""
    text = re.sub(r"\s+", " ", text).strip()
    
    # 플레이스홀더 패턴 제거 및 실제 이름으로 대체
    text = re.sub(r'\[진행자\s*이름\]', host_name, text, flags=re.IGNORECASE)
    text = re.sub(r'\[게스트\s*이름\]', guest_name, text, flags=re.IGNORECASE)
    text = text.replace("OOO", "김철수").replace("OO", "이하나")
    
    # 제어 문자, 한글 자모, 특수 기호 제거 (TTS 발음에 방해되는 문자 위주)
    text = re.sub(r'[\x00-\x1f\x7f-\x9f\ufeff]', '', text)
    text = re.sub(r"[^가-힣a-zA-Z0-9.,?! ]", "", text)
    return text.strip()

# =========================
# 노드 함수들
# =========================
def extract_texts_node(state: PodcastState) -> PodcastState:
    """노드 1: 모든 소스에서 텍스트를 추출합니다."""
    print(f"\n[노드 1] 텍스트 추출 시작: {len(state['sources'])}개 소스")
    
    extracted_texts = []
    errors = []
    
    for i, source in enumerate(state['sources']):
        source = source.strip()
        source_name = os.path.basename(source) if not source.startswith('http') else source
        
        print(f"  → 소스 {i+1}/{len(state['sources'])} ({source_name}) 처리 중...")
        
        try:
            if source.startswith("http://") or source.startswith("https://"):
                text = extract_from_web(source)
            elif source.lower().endswith(".docx"):
                text = extract_from_docx(source)
            elif source.lower().endswith(".pdf"):
                text = extract_from_pdf(source)
            else:
                raise ValueError("지원하지 않는 소스 유형")
            
            if text:
                extracted_texts.append(text)
            else:
                errors.append(f"소스 {source_name}에서 텍스트 추출 실패")
        except Exception as e:
            errors.append(f"소스 {source_name} 처리 오류: {str(e)}")
    
    return {
        **state,
        "extracted_texts": extracted_texts,
        "errors": errors,
        "current_step": "extract_complete"
    }

def extract_from_web(url: str) -> str:
    """웹 URL에서 텍스트를 추출합니다."""
    try:
        resp = requests.get(url, timeout=10)
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, 'html.parser')
        for script_or_style in soup(['script', 'style']):
            script_or_style.decompose()
        text = soup.get_text(separator='\n', strip=True)
        return re.sub(r'\n{3,}', '\n\n', text)
    except Exception as e:
        logging.error(f"웹 URL 처리 실패: {e}")
        return ""

def extract_from_docx(file_path: str) -> str:
    """DOCX 파일에서 텍스트를 추출합니다."""
    if not os.path.exists(file_path):
        raise FileNotFoundError(f"DOCX 파일을 찾을 수 없습니다: {file_path}")
    try:
        doc = Document(file_path)
        return "\n".join([p.text for p in doc.paragraphs if p.text.strip()])
    except Exception as e:
        logging.error(f"DOCX 처리 실패: {e}")
        return ""

def extract_from_pdf(pdf_path: str) -> str:
    """PDF에서 텍스트를 추출합니다."""
    text = ""
    try:
        with pdfplumber.open(pdf_path) as pdf:
            for page in pdf.pages:
                page_text = page.extract_text() or ""
                text += page_text + "\n"
    except FileNotFoundError:
        raise FileNotFoundError(f"PDF 파일을 찾을 수 없습니다: {pdf_path}")
    except Exception as e:
        logging.error(f"PDF 처리 실패: {e}")
        return ""
    
    text = re.sub(r"[\*\U00010000-\U0010ffff]|#", "", text)
    return text.strip()

def combine_texts_node(state: PodcastState) -> PodcastState:
    """노드 2: 추출된 텍스트들을 결합합니다."""
    print("\n[노드 2] 텍스트 결합 중...")
    
    if not state['extracted_texts']:
        return {
            **state,
            "errors": state.get('errors', []) + ["추출된 텍스트가 없습니다"],
            "current_step": "error"
        }
    
    combined = "\n\n---\n\n".join(state['extracted_texts'])
    
    return {
        **state,
        "combined_text": combined,
        "current_step": "combine_complete"
    }

def generate_script_node(state: PodcastState) -> PodcastState:
    """노드 3: LLM을 사용하여 팟캐스트 스크립트를 생성합니다."""
    print("\n[노드 3] 팟캐스트 스크립트 생성 중...")
    print(f"  → 진행자: {state['host_name']}")
    print(f"  → 게스트: {state['guest_name']}")
    
    # Vertex AI 초기화
    credentials = load_credentials(state['sa_file'])
    vertexai.init(project=state['project_id'], location=state['region'], credentials=credentials)
    
    model_name = os.getenv("VERTEX_AI_MODEL_TEXT", "gemini-2.5-flash")
    model = GenerativeModel(model_name)
    
    prompt = f"""
당신은 청취자를 사로잡는 전문적인 팟캐스트 스크립트 작가입니다.
아래 텍스트를 분석하여 두 명의 화자(진행자, 게스트)가 대화하는 형식의 팟캐스트 스크립트를 한국어로 작성해 주세요.

**[중요: 화자 태그 규칙]**
- 화자를 구분할 때는 반드시 "[진행자]"와 "[게스트]" 태그만 사용하세요.
- 절대로 "[박지우]", "[이하은]" 같은 이름 태그를 사용하지 마세요.
- 대화 내용 안에서 이름을 언급할 때만 "{state['host_name']}", "{state['guest_name']}"을 사용하세요.

**올바른 예시:**
[진행자] 안녕하세요, 저는 진행자 {state['host_name']}입니다!
[게스트] 안녕하세요, {state['guest_name']}입니다.
[진행자] {state['guest_name']} 님, 오늘 주제가 흥미롭네요.

**잘못된 예시 (절대 금지):**
[{state['host_name']}] 안녕하세요!
[박지우] 안녕하세요!

**[필수 지침: 인간적인 대화를 위한 구성]**
1. **톤 앤 매너:** 편안하고, 친근하며, 청취자와 눈높이를 맞추는 대화체로 작성해 주세요.
2. **흐름:** 자연스러운 대화의 흐름을 위해 추임새나 감탄사를 적절히 사용해 주세요.
3. **구조:** 도입부, 본론, 마무리의 세 부분으로 명확하게 구분되어야 합니다.
4. **화자 역할:**
   - **[진행자]:** 청취자를 대표하여 질문하고 대화를 이끕니다. (이름: {state['host_name']})
   - **[게스트]:** 전문가적인 지식을 전달합니다. (이름: {state['guest_name']})

원본 텍스트:
---
{state['combined_text']}
---
"""
    
    config = {
        "max_output_tokens": 8192,
        "temperature": 0.7,
    }
    
    try:
        response = model.generate_content(prompt, generation_config=config)
        script_text = getattr(response, "text", "")
        
        if not script_text:
            raise RuntimeError("모델이 텍스트를 반환하지 않았습니다")
        
        script_text = re.sub(r"```python|```json|```text|```|```markdown", "", script_text, flags=re.IGNORECASE)
        script_text = re.sub(r"[\*\U00010000-\U0010ffff]|#", "", script_text)
        
        print(f"\n--- 스크립트 미리보기 (첫 500자) ---\n{script_text[:500]}...\n")
        
        return {
            **state,
            "script": script_text.strip(),
            "current_step": "script_complete"
        }
    except Exception as e:
        return {
            **state,
            "errors": state.get('errors', []) + [f"스크립트 생성 오류: {str(e)}"],
            "current_step": "error"
        }

def generate_audio_node(state: PodcastState) -> PodcastState:
    """노드 4: TTS를 사용하여 오디오를 생성합니다."""
    print("\n[노드 4] Multi-Speaker TTS 변환 중...")
    
    credentials = load_credentials(state['sa_file'])
    vertexai.init(project=state['project_id'], location=state['region'], credentials=credentials)
    
    tts_model = GenerativeModel("gemini-2.5-flash-preview-tts")
    speaker_map = {"진행자": "Charon", "게스트": "Puck"}
    audio_metadata = []
    
    segments = re.split(r"\[([^\]]+)\]", state['script'])
    
    if len(segments) <= 1:
        segments = ["", "진행자", state['script']]
    
    base_filename = f"podcast_temp_{uuid.uuid4().hex[:4]}"
    i = 1
    
    while i < len(segments):
        speaker = segments[i].strip()
        raw_content = segments[i + 1].strip()
        i += 2
        
        if not raw_content:
            continue
        
        content_chunks = chunk_text(raw_content, max_chars=200)
        
        for chunk_index, content in enumerate(content_chunks):
            sanitized_content = sanitize_tts_text_wrapper(content, state['host_name'], state['guest_name'])
            
            if not sanitized_content:
                continue
            
            voice_name = speaker_map.get(speaker, "Charon")
            
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
                    
                    response = tts_model.generate_content(
                        contents=[{"role": "user", "parts": [{"text": sanitized_content}]}],
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
                    
                    pcm_bytes = base64_to_bytes(audio_data_part.inline_data.data)
                    duration_seconds = len(pcm_bytes) / 48000.0
                    
                    wav_bytes = pcm_to_wav(pcm_bytes, sample_rate=24000)
                    output_file = f"{base_filename}_{len(audio_metadata) + 1}_{speaker}_{chunk_index}.wav"
                    
                    with open(output_file, "wb") as f:
                        f.write(wav_bytes)
                    
                    audio_metadata.append({
                        'speaker': speaker,
                        'text': sanitized_content,
                        'duration': duration_seconds,
                        'file': output_file
                    })
                    
                    success = True
                    time.sleep(INTER_CHUNK_DELAY)
                    break
                    
                except Exception as e:
                    if attempt < MAX_RETRIES - 1:
                        time.sleep(BASE_DELAY * (2 ** attempt))
                    else:
                        print(f"세그먼트 생성 실패: {str(e)}")
            
            if success and chunk_index == len(content_chunks) - 1:
                time.sleep(SPEAKER_TURN_DELAY)
    
    wav_files = [m['file'] for m in audio_metadata]
    
    return {
        **state,
        "audio_metadata": audio_metadata,
        "wav_files": wav_files,
        "current_step": "audio_complete"
    }

def merge_audio_node(state: PodcastState) -> PodcastState:
    """노드 5: 오디오 파일들을 병합합니다."""
    print("\n[노드 5] 오디오 파일 병합 중...")
    
    if not state['wav_files']:
        return {
            **state,
            "errors": state.get('errors', []) + ["병합할 오디오 파일이 없습니다"],
            "current_step": "error"
        }
    
    list_file_path = "concat_list.txt"
    final_filename = f"podcast_episode_{uuid.uuid4().hex[:8]}.mp3"
    
    try:
        with open(list_file_path, "w", encoding="utf-8") as f:
            for file in state['wav_files']:
                f.write(f"file '{os.path.abspath(file)}'\n")
        
        command = [
            "ffmpeg", "-f", "concat", "-safe", "0", "-i", list_file_path,
            "-c:a", "libmp3lame", "-b:a", "192k", "-y", final_filename
        ]
        
        subprocess.run(command, check=True, capture_output=True, text=True, encoding="utf-8")
        
        os.remove(list_file_path)
        for file in state['wav_files']:
            if os.path.exists(file):
                os.remove(file)
        
        print(f"✓ 최종 팟캐스트 파일 생성: {final_filename}")
        
        return {
            **state,
            "final_podcast_path": final_filename,
            "current_step": "merge_complete"
        }
        
    except Exception as e:
        return {
            **state,
            "errors": state.get('errors', []) + [f"병합 오류: {str(e)}"],
            "current_step": "error"
        }

def generate_transcript_node(state: PodcastState) -> PodcastState:
    """노드 6: 타임스탬프 스크립트를 생성합니다."""
    print("\n[노드 6] 타임스탬프 스크립트 생성 중...")
    
    current_time = 0.0
    transcript_lines = []
    
    for item in state['audio_metadata']:
        seconds = int(current_time)
        hh = seconds // 3600
        mm = (seconds % 3600) // 60
        ss = seconds % 60
        timestamp = f"[{hh:02}:{mm:02}:{ss:02}]"
        
        line = f"{timestamp} [{item['speaker']}]: {item['text']}"
        transcript_lines.append(line)
        
        current_time += item['duration'] + INTER_CHUNK_DELAY
    
    transcript_path = state['final_podcast_path'].replace(".mp3", ".txt")
    
    with open(transcript_path, "w", encoding="utf-8") as f:
        f.write("\n".join(transcript_lines))
    
    print(f"✓ 스크립트 생성 완료: {transcript_path}")
    
    return {
        **state,
        "transcript_path": transcript_path,
        "current_step": "complete"
    }

def load_credentials(sa_file: str):
    """서비스 계정 파일에서 인증 정보를 로드합니다."""
    if os.path.exists(sa_file):
        try:
            return service_account.Credentials.from_service_account_file(sa_file)
        except Exception as e:
            raise RuntimeError(f"서비스 계정 파일 로드 오류: {e}")
    else:
        logging.warning(f"서비스 계정 파일을 찾을 수 없습니다: {sa_file}")
        return None

# =========================
# 그래프 구성
# =========================
def create_podcast_graph():
    """팟캐스트 생성 워크플로우 그래프를 생성합니다."""
    workflow = StateGraph(PodcastState)
    
    # 노드 추가
    workflow.add_node("extract_texts", extract_texts_node)
    workflow.add_node("combine_texts", combine_texts_node)
    workflow.add_node("generate_script", generate_script_node)
    workflow.add_node("generate_audio", generate_audio_node)
    workflow.add_node("merge_audio", merge_audio_node)
    workflow.add_node("generate_transcript", generate_transcript_node)
    
    # 엣지 정의
    workflow.set_entry_point("extract_texts")
    workflow.add_edge("extract_texts", "combine_texts")
    workflow.add_edge("combine_texts", "generate_script")
    workflow.add_edge("generate_script", "generate_audio")
    workflow.add_edge("generate_audio", "merge_audio")
    workflow.add_edge("merge_audio", "generate_transcript")
    workflow.add_edge("generate_transcript", END)
    
    # 메모리 체크포인터 추가
    memory = MemorySaver()
    app = workflow.compile(checkpointer=memory)
    
    return app

# =========================
# CLI 실행
# =========================
if __name__ == "__main__":
    import argparse
    
    PROJECT_ID_ENV = os.getenv("VERTEX_AI_PROJECT_ID")
    REGION_ENV = os.getenv("VERTEX_AI_REGION", "us-central1")
    SA_FILE_DEFAULT = os.getenv("VERTEX_AI_SERVICE_ACCOUNT_FILE") or \
                      os.path.join(os.path.expanduser('~'), ".config", "gcloud", "vertex-ai-service-account.json")
    
    parser = argparse.ArgumentParser(description="LangGraph 기반 팟캐스트 생성기")
    parser.add_argument("--sources", nargs='+', required=True, help="변환할 파일 경로 또는 웹 URL")
    parser.add_argument("--project_id", default=PROJECT_ID_ENV, help="Google Cloud Project ID")
    parser.add_argument("--region", default=REGION_ENV, help="Vertex AI Region")
    parser.add_argument("--sa_file", default=SA_FILE_DEFAULT, help="서비스 계정 JSON 키 파일 경로")
    parser.add_argument("--host-name", default=None, help="진행자 이름 (미지정시 자동 생성)")
    parser.add_argument("--guest-name", default=None, help="게스트 이름 (미지정시 자동 생성)")
    
    args = parser.parse_args()
    
    if not args.project_id:
        print("오류: Google Cloud Project ID를 지정해야 합니다")
        exit(1)
    
    # 이름 생성 또는 사용자 지정 이름 사용
    if args.host_name and args.guest_name:
        host_name = args.host_name
        guest_name = args.guest_name
        print(f"\n 사용자 지정 이름 사용")
    else:
        host_name, guest_name = generate_korean_names()
        print(f"\n 자동 생성된 이름 사용")
    
    print(f"  → 진행자: {host_name}")
    print(f"  → 게스트: {guest_name}")
    
    # 초기 상태 설정
    initial_state = {
        "sources": args.sources,
        "extracted_texts": [],
        "combined_text": "",
        "script": "",
        "audio_metadata": [],
        "wav_files": [],
        "final_podcast_path": "",
        "transcript_path": "",
        "errors": [],
        "current_step": "start",
        "project_id": args.project_id,
        "region": args.region,
        "sa_file": args.sa_file,
        "host_name": host_name,
        "guest_name": guest_name
    }
    
    # 그래프 생성 및 실행
    app = create_podcast_graph()
    
    config = {"configurable": {"thread_id": "podcast_generation"}}
    
    print("\n LangGraph 기반 팟캐스트 생성 시작...\n")
    
    try:
        final_state = app.invoke(initial_state, config)
        
        if final_state.get('errors'):
            print("\n 경고: 일부 오류가 발생했습니다:")
            for error in final_state['errors']:
                print(f"  - {error}")
        
        if final_state.get('final_podcast_path'):
            print(f"\n 성공적으로 변환 완료!")
            print(f"  → 최종 팟캐스트 파일: {final_state['final_podcast_path']}")
            if final_state.get('transcript_path'):
                print(f"  → 타임스탬프 스크립트: {final_state['transcript_path']}")
        else:
            print("\n 팟캐스트 생성에 실패했습니다.")
            
    except Exception as e:
        print(f"\n 실행 오류: {e}")
        exit(1)