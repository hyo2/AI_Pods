# scripts/ko_tts_voices.py (배치 전용)

"""
[Batch Script]
- DB(tts_voice)에 존재하는 Gemini voice 목록을 기준으로
- 한국어 샘플 음성 생성
- feature_vector 계산
- Supabase Storage 업로드
- DB 업데이트
"""

import os
import time
import soundfile as sf
import numpy as np

from app.langgraph_pipeline.podcast.tts_service import TTSService
from app.services.tts_voice_features import extract_audio_features
from app.services.supabase_service import (
    supabase,
    upload_bytes,
    safe_filename
)

# =========================
# 배치용 long-form 스크립트
# =========================
KOREAN_SAMPLE_SCRIPT = """
[진행자]
안녕하세요. 지금부터 오늘의 학습 내용을 정리해 드리겠습니다.
이번 시간에는 중요한 개념을 중심으로 내용을 차분하게 설명하겠습니다.

먼저 이 개념이 왜 중요한지부터 살펴보겠습니다.
이 개념은 이후 학습 전반에서 반복적으로 등장하며,
문제를 이해하고 해결하는 데 핵심적인 역할을 합니다.

처음 접하면 다소 어렵게 느껴질 수 있지만,
기본 구조를 이해하고 나면 훨씬 쉽게 받아들일 수 있습니다.
지금부터 전체 흐름을 먼저 설명한 뒤,
세부적인 내용을 하나씩 정리해 보겠습니다.
"""

def merge_wavs(wav_files: list[str], output_path: str):
    """여러 wav 파일을 하나로 병합"""
    data_list = []
    sr = None

    for w in wav_files:
        data, sr = sf.read(w)
        data_list.append(data)

    merged = np.concatenate(data_list)
    sf.write(output_path, merged, sr)


def run():
    tts_service = TTSService()

    voices = (
        supabase
        .table("tts_voice")
        .select("id, name")
        .execute()
        .data
    )

    for v in voices:
        voice_id = v["id"]
        voice_name = v["name"]

        print(f"\n[SEED] {voice_name}")

        # 1️⃣ 팟캐스트 TTS 파이프라인 재사용
        _, wav_chunks = tts_service.generate_audio(
            script=KOREAN_SAMPLE_SCRIPT,
            host_name=voice_name, # DB의 tts_voice.name
            guest_name=None
        )

        if not wav_chunks:
            print("  ❌ TTS 생성 실패")
            continue

        # 2️⃣ chunk 병합
        merged_path = f"tmp_{voice_name}_ko.wav"
        merge_wavs(wav_chunks, merged_path)

        # 3️⃣ feature_vector 계산
        feature_vector = extract_audio_features(merged_path)

        # 4️⃣ storage 업로드
        with open(merged_path, "rb") as f:
            wav_bytes = f.read()

        storage_path = upload_bytes(
            file_bytes=wav_bytes,
            folder="tts_samples",
            filename=safe_filename(f"{voice_name}_ko.wav"),
            content_type="audio/wav"
        )

        # 5️⃣ DB 업데이트
        supabase.table("tts_voice").update({
            "sample_path": storage_path,
            "feature_vector": feature_vector.tolist()
        }).eq("id", voice_id).execute()

        print("  ✅ 완료")

        time.sleep(10)  # voice 간 충분한 간격

    print("\n🎉 Gemini TTS 한국어 샘플 배치 완료")


if __name__ == "__main__":
    run()
