# app/langgraph_pipeline/podcast/utils.py

import re
import base64
import struct
from typing import List, Tuple

def sanitize_tts_text(
    text: str,
    host_name: str = "",
    guest_name: str | None = None
) -> str:
    """TTS용 텍스트 정리"""

    # 공백 정리
    text = re.sub(r"\s+", " ", text).strip()

    # 진행자 이름 치환
    text = re.sub(
        r"\[진행자\s*이름\]",
        host_name or "진행자",
        text,
        flags=re.IGNORECASE
    )

    # 게스트 이름 치환 (None 안전 처리)
    if guest_name:
        text = re.sub(
            r"\[게스트\s*이름\]",
            guest_name,
            text,
            flags=re.IGNORECASE
        )
    else:
        # 게스트 없는 경우 placeholder 제거
        text = re.sub(
            r"\[게스트\s*이름\]",
            "",
            text,
            flags=re.IGNORECASE
        )

    # 제어 문자 제거
    text = re.sub(r"[\x00-\x1f\x7f-\x9f\ufeff]", "", text)

    # 허용 문자만 남기기 (한글, 영문, 숫자, 기본 문장부호)
    text = re.sub(r"[^가-힣a-zA-Z0-9.,?! ]", "", text)

    return text.strip()


def chunk_text(text: str, max_chars: int = 200) -> List[str]:
    """긴 텍스트를 문장 경계를 유지하며 분할"""
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


def base64_to_bytes(base64_string: str) -> bytes:
    """Base64 문자열을 바이트로 디코딩"""
    try:
        if isinstance(base64_string, bytes):
            return base64_string
        missing_padding = len(base64_string) % 4
        if missing_padding:
            base64_string += '=' * (4 - missing_padding)
        return base64.b64decode(base64_string)
    except Exception:
        return b""


def pcm_to_wav(
    pcm_data: bytes, 
    sample_rate: int = 24000, 
    num_channels: int = 1, 
    bits_per_sample: int = 16
) -> bytes:
    """PCM을 WAV 형식으로 변환"""
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

# 스크립트 글자 길이 계산용
def estimate_korean_chars_for_budget(text: str) -> int:
    """
    길이 예산 계산용 글자수 추정.
    - 타임스탬프 제거
    - 「선생님」/「학생」 화자 태그 제거
    - 공백/개행 제거 후 길이 측정
    """
    text = re.sub(r"\[\d{2}:\d{2}:\d{2}\]\s*", "", text)
    text = re.sub(r"^「(선생님|학생)」\s*:?\s*", "", text, flags=re.MULTILINE)
    text = re.sub(r"\s+", "", text)
    return len(text)

# ✅ 프로젝트 기준 분당 글자수 (실제 TTS 시간 기반으로 재조정)
def target_char_budget(duration_min: float, style: str) -> int:
    """
    style별 분당 글자수 기반으로 budget 계산 (duration_min은 float 허용)
    - lecture: 380자/분
    - explain: 400자/분
    """
    if style == "lecture":
        chars_per_min = 380
    else:
        chars_per_min = 400

    # ✅ float duration 반영 + int로 반올림
    budget = int(round(duration_min * chars_per_min))

    # ✅ 극단값 방어 (30초~20분 같은 입력 대응)
    budget = max(250, min(budget, 20000))
    return budget