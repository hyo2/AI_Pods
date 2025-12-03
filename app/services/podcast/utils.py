# app/services/podcast/utils.py
import re
import random
import base64
import struct
from typing import List, Tuple

def generate_korean_names() -> Tuple[str, str]:
    """한국 이름을 자동으로 생성"""
    surnames = ["김", "이", "박", "최", "정", "강", "조", "윤", "장", "임"]
    given_names_host = ["지수", "민준", "서연", "하준", "예은"]
    given_names_guest = ["준서", "현우", "지훈", "민서", "예준"]
    
    host_name = random.choice(surnames) + random.choice(given_names_host)
    guest_name = random.choice(surnames) + random.choice(given_names_guest)
    
    while host_name == guest_name:
        guest_name = random.choice(surnames) + random.choice(given_names_guest)
    
    return host_name, guest_name


def sanitize_tts_text(text: str, host_name: str = "", guest_name: str = "") -> str:
    """TTS용 텍스트 정리"""
    text = re.sub(r"\s+", " ", text).strip()
    text = re.sub(r'\[진행자\s*이름\]', host_name, text, flags=re.IGNORECASE)
    text = re.sub(r'\[게스트\s*이름\]', guest_name, text, flags=re.IGNORECASE)
    text = re.sub(r'[\x00-\x1f\x7f-\x9f\ufeff]', '', text)
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