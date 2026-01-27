"""
Tail Focus V5 - 글자 수 + 문장 개수 동시 제한 최종 버전 (중복 방지 개선!)
150개+ 발화 대응: 2500자 또는 50개 중 먼저 도달 시 배치 분할

개선사항:
- MAX_BATCH_SIZE = 50 (문장 개수 제한)
- MAX_BATCH_CHARS = 2500 (글자 수 제한, 3000 → 2500 안정성 향상)
- 둘 중 먼저 도달하는 조건으로 배치 분할
- 문장 완전성 100% 보장 (절대 중간에 안 자름!)
- 선생님 긴 발화 안전하게 처리

✅ 중복 방지 개선 (v5.1):
- Tail 길이: 3단어 → 5-7단어 (동적 조정)
- Search Window: -2~+5초 → -1~+2초 (범위 축소)
- 중복 문구 필터링: 동일 STT 문구 재사용 방지
- 시간 우선 정책: 가중치 30% → 50% (시간상 가까운 후보 우선)
- 시간 범위 필터링: 예상 시간 ±3초 이내만 고려
"""

import os
from venv import logger
import wave
import json
import requests
import base64
import time
import difflib
import re
import uuid
import numpy as np
from pathlib import Path
from dataclasses import dataclass
from typing import List, Dict, Optional, Tuple
from collections import deque
from dotenv import load_dotenv
from google.oauth2 import service_account
from google.auth.transport.requests import Request
from google.cloud import speech

load_dotenv()


@dataclass
class Dialogue:
    speaker: str
    text: str


class TailFocusV5Generator:
    """Tail Focus V5 Generator (글자 수 + 문장 개수 동시 제한)"""
    
    # ✅ 배치 제한 (둘 중 먼저 도달하면 분할!)
    MAX_BATCH_SIZE = 50      # 최대 문장 개수
    MAX_BATCH_CHARS = 2500   # 최대 글자 수 (3000 → 2500, 안정성 향상)
    
    def __init__(
        self,
        credentials_file: str = "./vertex-ai-service-account.json",
        output_dir: str = "podcast_tail_v5",
        host_voice: str = "Kore",
        guest_voice: str = "Leda",
        tts_model_name: str = "gemini-2.5-flash-preview-tts",
        tts_region: str = "us-central1",
        separator_text: str = "\n\n\n\n\n",
        tail_thresholds: List[float] = None,
        top_n_candidates: int = 10,
        silence_threshold: int = 500,
        silence_min_duration: float = 0.05,
        boundary_search_window: float = 1.0,
        default_margin: float = 0.2
    ):
        self.credentials_file = credentials_file
        self.output_dir = output_dir
        self.host_voice = host_voice
        self.guest_voice = guest_voice
        self.tts_model_name = tts_model_name
        self.tts_region = tts_region
        self.separator_text = separator_text
        self.tail_thresholds = tail_thresholds or [0.70, 0.60, 0.50]
        self.top_n_candidates = top_n_candidates
        self.silence_threshold = silence_threshold
        self.silence_min_duration = silence_min_duration
        self.boundary_search_window = boundary_search_window
        self.default_margin = default_margin
        
        # ✅ 세션 고유 ID (파일명 충돌 방지!)
        self.session_id = uuid.uuid4().hex[:8]
        
        # 재시도 설정
        self.retry_delays = [2.0, 4.0, 8.0]
        
        # 성능 측정 변수
        self.tts_time = 0.0
        self.stt_time = 0.0
        self.segment_time = 0.0
        self.merge_time = 0.0
        self.api_calls = 0
        self.error_429_count = 0
        self.retry_count = 0
        
        self.output_path = Path(output_dir).resolve()
        self.output_path.mkdir(parents=True, exist_ok=True)
        
        # 복합어 사전 (최소화)
        self.compound_mapping = {
            'AI': '에이아이', 'API': '에이피아이', 'URL': '유알엘',
            'COVID': '코비드', 'RNA': '알엔에이', 'DNA': '디엔에이'
        }
        
        # 영문자 매핑
        self.char_mapping = {
            'A': '에이', 'B': '비', 'C': '씨', 'D': '디', 'E': '이',
            'F': '에프', 'G': '지', 'H': '에이치', 'I': '아이', 'J': '제이',
            'K': '케이', 'L': '엘', 'M': '엠', 'N': '엔', 'O': '오',
            'P': '피', 'Q': '큐', 'R': '알', 'S': '에스', 'T': '티',
            'U': '유', 'V': '브이', 'W': '더블유', 'X': '엑스', 'Y': '와이', 'Z': '제트'
        }
        
        self._setup_auth()
    
    def _setup_auth(self):
        """인증 설정"""
        with open(self.credentials_file, 'r') as f:
            creds_data = json.load(f)
            self.project_id = creds_data.get("project_id")
        
        os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = str(
            Path(self.credentials_file).resolve()
        )
        
        self.creds = service_account.Credentials.from_service_account_file(
            self.credentials_file,
            scopes=['https://www.googleapis.com/auth/cloud-platform']
        )
        self.creds.refresh(Request())
        self.speech_client = speech.SpeechClient(credentials=self.creds)
    
    def _get_vertex_headers(self):
        """Vertex AI 헤더"""
        if self.creds.expired:
            self.creds.refresh(Request())
        return {
            "Authorization": f"Bearer {self.creds.token}",
            "Content-Type": "application/json; charset=utf-8"
        }
    
    def _get_retry_delay(self, attempt: int) -> float:
        """재시도 지연 시간 계산"""
        if attempt < len(self.retry_delays):
            return self.retry_delays[attempt]
        else:
            return self.retry_delays[-1]
    
    def _normalize_text(self, text: str) -> str:
        """영어를 한글 발음으로 변환"""
        for eng, kor in self.compound_mapping.items():
            text = text.replace(eng, kor)
            text = text.replace(eng.lower(), kor)
        
        result = []
        for char in text.upper():
            if char in self.char_mapping:
                result.append(self.char_mapping[char])
            else:
                result.append(char)
        text = "".join(result)
        
        return re.sub(r'[^가-힣]', '', text)
    
    # =========================================================================
    # 배치 분할 (글자 수 + 문장 개수!)
    # =========================================================================
    
    def _split_into_batches(self, texts: List[str]) -> List[List[str]]:
        """
        문장 단위로 배치 분할 (절대 문장 중간 안 자름!)
        
        조건:
        - MAX_BATCH_SIZE (50개) 도달 → 분할
        - MAX_BATCH_CHARS (2500자) 초과 예상 → 분할 (3000 → 2500 개선)
        """
        batches = []
        current_batch = []
        current_chars = 0
        
        for text in texts:
            text_len = len(text)
            
            # 조건 1: 문장 개수 도달
            # 조건 2: 글자 수 초과 예상
            if (len(current_batch) >= self.MAX_BATCH_SIZE or 
                (current_batch and current_chars + text_len > self.MAX_BATCH_CHARS)):
                
                # 현재 배치 완료 (이 문장 제외!)
                batches.append(current_batch)
                current_batch = []
                current_chars = 0
            
            # 이 문장을 현재 배치에 추가 (완전한 문장!)
            current_batch.append(text)
            current_chars += text_len
        
        # 마지막 배치
        if current_batch:
            batches.append(current_batch)
        
        return batches
    
    # =========================================================================
    # TTS (배치 분할!)
    # =========================================================================
    
    def _merge_wav_files(self, wav_files: List[str], output_path: str):
        """여러 WAV 파일을 하나로 병합"""
        print(f"  🔗 {len(wav_files)}개 배치 WAV 병합 중...")
        
        # 첫 번째 파일에서 파라미터 가져오기
        with wave.open(wav_files[0], 'rb') as w:
            params = w.getparams()
        
        # 모든 오디오 데이터 결합
        combined_data = bytearray()
        for wav_file in wav_files:
            with wave.open(wav_file, 'rb') as w:
                combined_data.extend(w.readframes(w.getnframes()))
        
        # 최종 파일 저장
        with wave.open(output_path, 'wb') as w:
            w.setparams(params)
            w.writeframes(combined_data)
        
        # 임시 파일 삭제
        for wav_file in wav_files:
            if os.path.exists(wav_file):
                os.remove(wav_file)
        
        print(f"  ✅ 배치 병합 완료")
    
    def _generate_single_batch(
        self, 
        texts: List[str], 
        voice: str, 
        output_path: str
    ):
        """단일 배치 TTS 생성 (무한 재시도)"""
        full_text = self.separator_text.join(texts)
        
        url = (
            f"https://{self.tts_region}-aiplatform.googleapis.com"
            f"/v1beta1/projects/{self.project_id}"
            f"/locations/{self.tts_region}"
            f"/publishers/google/models/{self.tts_model_name}:generateContent"
        )
        
        prompt = f"Read naturally in Korean. Please PAUSE clearly between sentences.\nText:\n{full_text}"
        
        data = {
            "contents": [{"role": "user", "parts": [{"text": prompt}]}],
            "generation_config": {
                "response_modalities": ["AUDIO"],
                "speech_config": {"voice_config": {"prebuilt_voice_config": {"voice_name": voice}}}
            }
        }
        
        # 무한 재시도
        attempt = 0
        while True:
            self.api_calls += 1
            
            try:
                res = requests.post(
                    url, 
                    headers=self._get_vertex_headers(), 
                    json=data,
                    timeout=300  # 5분 타임아웃
                )
                
                if res.status_code == 200:
                    audio_data = base64.b64decode(
                        res.json()["candidates"][0]["content"]["parts"][0]["inlineData"]["data"]
                    )
                    with wave.open(output_path, 'wb') as f:
                        f.setnchannels(1)
                        f.setsampwidth(2)
                        f.setframerate(24000)
                        f.writeframes(audio_data)
                    return
                
                elif res.status_code == 429:
                    self.error_429_count += 1
                    self.retry_count += 1
                    delay = self._get_retry_delay(attempt)
                    print(f"      ⚠️  429 에러 → {delay:.1f}초 후 재시도 ({attempt+1}회)")
                    time.sleep(delay)
                    attempt += 1
                else:
                    raise Exception(f"TTS Error: {res.status_code} - {res.text}")
                    
            except Exception as e:
                print(f"      ❌ 예외 발생: {e}")
                self.retry_count += 1
                delay = self._get_retry_delay(attempt)
                time.sleep(delay)
                attempt += 1
    
    def _generate_batch_audio(self, texts: List[str], voice: str, output_path: str):
        """배치 TTS 생성 (글자 수 + 문장 개수 동시 제한)"""
        # guset가 0이면 종료
        if not texts:
            return
        
        # ✅ 기존 오디오 재사용 로직 제거 (프로덕션 안정성)
        
        total_texts = len(texts)
        total_chars = sum(len(t) for t in texts)
        avg_chars = total_chars / total_texts if total_texts > 0 else 0
        
        print(f"  🔊 TTS 생성 중...")
        print(f"     문장 수: {total_texts}개")
        print(f"     총 글자수: {total_chars}자 (평균: {avg_chars:.0f}자/문장)")
        
        # ✅ 배치 분할 (글자 수 + 문장 개수 동시 체크!)
        batches = self._split_into_batches(texts)
        
        if len(batches) == 1:
            # 단일 배치
            print(f"     전략: 단일 배치 ({len(batches[0])}개, {sum(len(t) for t in batches[0])}자)")
            self._generate_single_batch(batches[0], voice, output_path)
            print(f"  ✅ TTS 완료")
        else:
            # 배치 분할
            print(f"     전략: {len(batches)}개 배치로 분할")
            for i, batch in enumerate(batches):
                batch_chars = sum(len(t) for t in batch)
                print(f"       배치 {i+1}: {len(batch)}개 문장, {batch_chars}자")
            
            temp_wavs = []
            for batch_idx, batch_texts in enumerate(batches):
                # ✅ 고유한 임시 파일명 (session_id 포함)
                temp_wav = str(self.output_path / f"temp_batch_{batch_idx}_{self.session_id}_{voice}.wav")
                
                batch_chars = sum(len(t) for t in batch_texts)
                print(f"     배치 {batch_idx+1}/{len(batches)}: {len(batch_texts)}개 문장, {batch_chars}자 생성 중...")
                
                self._generate_single_batch(batch_texts, voice, temp_wav)
                temp_wavs.append(temp_wav)
                
                # 배치 간 짧은 대기
                if batch_idx < len(batches) - 1:
                    time.sleep(1.0)
            
            # 배치 병합
            self._merge_wav_files(temp_wavs, output_path)
            print(f"  ✅ TTS 완료 ({len(batches)}개 배치)")
    
    def _transcribe_audio(self, wav_path: str) -> List[Dict]:
        """STT 변환"""
        with wave.open(wav_path, "rb") as wav:
            rate = wav.getframerate()
            content = wav.readframes(wav.getnframes())
        
        chunk_len = 50 * rate * 2
        all_words = []
        
        print(f"  🎧 STT 변환 중... ({os.path.basename(wav_path)})")
        
        for i, start_byte in enumerate(range(0, len(content), chunk_len)):
            chunk = content[start_byte:start_byte + chunk_len]
            if len(chunk) < 100:
                continue
            
            try:
                resp = self.speech_client.recognize(
                    config=speech.RecognitionConfig(
                        encoding=speech.RecognitionConfig.AudioEncoding.LINEAR16,
                        sample_rate_hertz=rate,
                        language_code="ko-KR",
                        enable_word_time_offsets=True
                    ),
                    audio=speech.RecognitionAudio(content=chunk)
                )
                
                time_offset = start_byte / (rate * 2)
                
                for res in resp.results:
                    for w in res.alternatives[0].words:
                        all_words.append({
                            "word": w.word,
                            "start": round(w.start_time.total_seconds() + time_offset, 3),
                            "end": round(w.end_time.total_seconds() + time_offset, 3)
                        })
            except Exception as e:
                print(f"    ⚠️  STT 청크 {i} 실패: {e}")
        
        print(f"  ✅ STT 완료 ({len(all_words)}개 단어)")
        return all_words
    
    # =========================================================================
    # 정밀 경계 감지
    # =========================================================================
    
    def _find_precise_boundary(self, wav_path: str, tail_end_time: float) -> float:
        """꼬리 이후 정밀한 묵음 경계 찾기"""
        with wave.open(wav_path, 'rb') as w:
            rate = w.getframerate()
            w.setpos(0)
            audio_data = np.frombuffer(
                w.readframes(w.getnframes()),
                dtype=np.int16
            )
        
        start_sample = int(tail_end_time * rate)
        end_sample = int((tail_end_time + self.boundary_search_window) * rate)
        
        if end_sample > len(audio_data):
            end_sample = len(audio_data)
        
        search_segment = audio_data[start_sample:end_sample]
        window_size = int(0.01 * rate)
        
        silence_start = None
        silence_duration = 0
        
        for i in range(0, len(search_segment) - window_size, window_size // 2):
            window = search_segment[i:i+window_size]
            energy = np.abs(window).mean()
            
            if energy < self.silence_threshold:
                if silence_start is None:
                    silence_start = i
                silence_duration += (window_size / 2) / rate
                
                if silence_duration >= self.silence_min_duration:
                    precise_end = tail_end_time + (silence_start / rate)
                    return round(precise_end, 3)
            else:
                silence_start = None
                silence_duration = 0
        
        return round(tail_end_time + self.default_margin, 3)
    
    # =========================================================================
    # 후보군 꼬리 찾기
    # =========================================================================
    
    def _find_tail_with_candidates(
        self,
        all_words: List[Dict],
        text: str,
        search_start_idx: int,
        expected_start_time: float
    ) -> Tuple[bool, float, str, float, int]:
        """후보군 방식으로 꼬리 찾기 (중복 방지 개선!)"""
        
        # ✅ 개선: Tail 길이 증가 (3단어 → 5-7단어)
        # - 짧은 패턴("2단계") 중복 매칭 방지
        # - 텍스트 길이에 따라 동적 조정
        words = text.strip().split()
        tail_len = min(7, max(5, len(words) // 3))  # 최소 5, 최대 7단어
        tail_words = words[-tail_len:]
        
        tail_raw = "".join(tail_words)
        target_tail = self._normalize_text(tail_raw)
        
        candidates = []
        
        # ✅ 개선: Search Window 축소 (-2~+5초 → -1~+2초)
        # - 다음 발화까지 검색 범위 확장 방지
        estimated_duration = len(text) * 0.20
        search_window_start = max(expected_start_time - 1.0, 0)  # 2초 → 1초
        search_window_end = expected_start_time + estimated_duration + 2.0  # 5초 → 2초
        
        # ✅ 개선: 중복 문구 필터링
        # - 동일한 STT 문구 재사용 방지
        seen_phrases = set()
        
        for j in range(len(all_words)):
            if all_words[j]['start'] < search_window_start:
                continue
            if all_words[j]['start'] > search_window_end:
                break
            
            for window_size in [2, 3, 4, 5, 6, 7, 8, 9, 10]:  # 윈도우 크기 확장 (tail 길이 증가 대응)
                if j + window_size > len(all_words):
                    continue
                
                stt_phrase_raw = "".join([
                    w['word'] for w in all_words[j:j+window_size]
                ])
                stt_phrase_norm = self._normalize_text(stt_phrase_raw)
                
                # ✅ 중복 방지: 이미 사용한 문구는 스킵
                if stt_phrase_norm in seen_phrases:
                    continue
                
                score = difflib.SequenceMatcher(
                    None, target_tail, stt_phrase_norm
                ).ratio()
                
                if score > 0.50:
                    time_diff = abs(all_words[j]['start'] - expected_start_time)
                    
                    # ✅ 시간 범위 필터링: 너무 먼 후보는 제외
                    if time_diff > estimated_duration + 3.0:  # 예상 시간 ± 3초 이내만
                        continue
                    
                    seen_phrases.add(stt_phrase_norm)  # 사용 기록
                    
                    candidates.append({
                        "score": score,
                        "end_time": all_words[j+window_size-1]['end'],
                        "phrase": stt_phrase_raw,
                        "idx": j + window_size,
                        "time_diff": time_diff
                    })
        
        if not candidates:
            return False, 0.0, "", 0.0, search_start_idx
        
        # ✅ 개선: 시간 우선 정책 강화
        # - 시간 가중치: 30% → 50% (시간상 가까운 후보 우선)
        for c in candidates:
            time_score = 1.0 / (1.0 + c['time_diff'])
            c['combined_score'] = c['score'] * 0.5 + time_score * 0.5  # 50:50
        
        candidates.sort(key=lambda x: -x['combined_score'])
        
        for threshold in self.tail_thresholds:
            for c in candidates:
                if c['score'] >= threshold:
                    return True, c['end_time'], c['phrase'], c['score'], c['idx']
        
        best = candidates[0]
        return True, best['end_time'], best['phrase'], best['score'], best['idx']
    
    # =========================================================================
    # 문장 분할
    # =========================================================================
    
    def _find_segments_robust(
        self,
        wav_path: str,
        all_words: List[Dict],
        texts: List[str]
    ) -> List[Dict]:
        """강화된 문장 분할 (세그먼트 개수 보장!)"""
        print(f"\n  🧩 강화된 문장 분할 (후보군 방식)...")
        
        with wave.open(wav_path, 'rb') as w:
            total_duration = w.getnframes() / w.getframerate()
        
        print(f"     오디오 총 길이: {total_duration:.1f}초")
        
        segments = []
        stt_search_idx = 0
        current_start = 0.0
        
        for i, text in enumerate(texts):
            is_last = (i == len(texts) - 1)
            
            if is_last:
                final_end = total_duration
            else:
                success, found_end, best_phrase, score, next_idx = self._find_tail_with_candidates(
                    all_words, text, stt_search_idx, current_start
                )
                
                if success:
                    precise_end = self._find_precise_boundary(wav_path, found_end)
                    stt_search_idx = next_idx
                    final_end = precise_end
                else:
                    if segments:
                        avg_duration = sum([s['end'] - s['start'] for s in segments]) / len(segments)
                        final_end = round(current_start + avg_duration, 3)
                    else:
                        final_end = round(current_start + len(text) * 0.15, 3)
                
                if final_end > total_duration:
                    final_end = total_duration
            
            segments.append({
                "start": round(current_start, 3),
                "end": final_end
            })
            
            current_start = final_end
        
        # ✅ 세그먼트 개수 검증 및 보장!
        if len(segments) != len(texts):
            print(f"  ⚠️  세그먼트 개수 불일치 감지!")
            print(f"     텍스트: {len(texts)}개, 세그먼트: {len(segments)}개")
            
            # 부족하면 추가
            while len(segments) < len(texts):
                last_end = segments[-1]['end'] if segments else 0.0
                # 평균 duration 계산
                if segments:
                    avg_dur = sum([s['end'] - s['start'] for s in segments]) / len(segments)
                else:
                    avg_dur = 5.0
                
                new_seg = {
                    'start': last_end,
                    'end': min(last_end + avg_dur, total_duration)
                }
                segments.append(new_seg)
                print(f"     세그먼트 추가: {len(segments)}번째 ({new_seg['start']:.1f}초~{new_seg['end']:.1f}초)")
            
            # 너무 많으면 제거
            while len(segments) > len(texts):
                removed = segments.pop()
                print(f"     세그먼트 제거: {len(segments)+1}번째")
        
        print(f"  ✅ 최종 세그먼트: {len(segments)}개 (텍스트: {len(texts)}개)")
        
        # ============================================================
        # ✅ 세그먼트 검증 (비정상 duration 감지)
        # ============================================================
        MAX_SEGMENT_DURATION = 60.0  # 60초 초과 시 경고

        for i, seg in enumerate(segments):
            duration = seg['end'] - seg['start']
            
            # 비정상적으로 긴 세그먼트 감지
            if duration > MAX_SEGMENT_DURATION:
                logger.error(f"❌ 비정상 세그먼트 감지!")
                logger.error(f"   세그먼트 {i+1}: {duration:.1f}초 (최대: {MAX_SEGMENT_DURATION}초)")
                logger.error(f"   텍스트: {texts[i][:100] if i < len(texts) else 'N/A'}...")
                
                # 옵션 1: 경고만 (현재)
                logger.warning(f"⚠️  비정상 세그먼트를 그대로 사용합니다 (수동 확인 필요)")
                
                # 옵션 2: 에러 발생 (권장)
                # raise ValueError(
                #     f"비정상적으로 긴 세그먼트 감지: {duration:.1f}초 > {MAX_SEGMENT_DURATION}초. "
                #     f"스크립트에 중복 또는 불완전한 발화가 있을 수 있습니다."
                # )
            
            # 음수 duration도 체크
            if duration < 0:
                logger.error(f"❌ 음수 세그먼트 감지!")
                logger.error(f"   세그먼트 {i+1}: {duration:.1f}초")
                raise ValueError(f"음수 duration 감지: {duration:.1f}초")

        logger.info(f"✅ 세그먼트 검증 완료: {len(segments)}개 세그먼트 (최대: {max([s['end']-s['start'] for s in segments]):.1f}초)")

        return segments
    
    # =========================================================================
    # 병합
    # =========================================================================
    
    def _merge_segments_safe(
        self,
        dialogues: List[Dialogue],
        host_wav: str,
        guest_wav: str,
        host_segs: List[Dict],
        guest_segs: List[Dict],
        output_path: str
    ):
        """안전한 세그먼트 병합"""
        print(f"\n  ✂️  대본 순서대로 조립 중...")
        
        with wave.open(host_wav, 'rb') as w:
            host_duration = w.getnframes() / w.getframerate()
        with wave.open(guest_wav, 'rb') as w:
            guest_duration = w.getnframes() / w.getframerate()
        
        print(f"    Host 길이: {host_duration:.1f}초 / Guest 길이: {guest_duration:.1f}초")
        
        def extract_audio(path, start, end, max_duration):
            with wave.open(path, 'rb') as w:
                params = w.getparams()
                rate = w.getframerate()
                
                start_sample = int(start * rate)
                end_sample = int(end * rate)
                
                if start_sample < 0:
                    start_sample = 0
                if end_sample > w.getnframes():
                    end_sample = w.getnframes()
                if start_sample >= end_sample:
                    return b"", params
                
                w.setpos(start_sample)
                return w.readframes(end_sample - start_sample), params
        
        host_queue = deque(host_segs)
        guest_queue = deque(guest_segs)
        final_audio = bytearray()
        params = None
        
        print(f"    진행자: {len(host_queue)}개 / 게스트: {len(guest_queue)}개")
        
        for i, line in enumerate(dialogues):
            if line.speaker == "host":
                if host_queue:
                    seg = host_queue.popleft()
                    data, params = extract_audio(host_wav, seg['start'], seg['end'], host_duration)
                    final_audio.extend(data)
            elif line.speaker == "guest":
                if guest_queue:
                    seg = guest_queue.popleft()
                    data, params = extract_audio(guest_wav, seg['start'], seg['end'], guest_duration)
                    final_audio.extend(data)
        
        with wave.open(output_path, 'wb') as f:
            f.setparams(params)
            f.writeframes(final_audio)
        
        print(f"  ✅ 병합 완료: {output_path}")
    
    # =========================================================================
    # Main Pipeline
    # =========================================================================
    
    def generate(self, dialogues: List[Dialogue]):
        """메인 파이프라인"""
        print("\n" + "="*60)
        print("🚀 Tail Focus V5 Generator 시작")
        print("   (글자 수 + 문장 개수 동시 제한)")
        print(f"   Session ID: {self.session_id}")
        print("="*60 + "\n")
        
        host_texts = [d.text for d in dialogues if d.speaker == "host"]
        guest_texts = [d.text for d in dialogues if d.speaker == "guest"]
        
        print(f"📊 대화 분석:")
        print(f"   진행자: {len(host_texts)}개")
        print(f"   게스트: {len(guest_texts)}개")
        print(f"   배치 제한: {self.MAX_BATCH_SIZE}개 또는 {self.MAX_BATCH_CHARS}자\n")
        
        # Stage 1: TTS
        print("="*60)
        print("📍 Stage 1: 배치 TTS (글자 수 + 문장 개수 제한)")
        print("="*60)
        
        tts_start = time.time()
        
        # ✅ 고유한 파일명 (session_id 포함)
        host_wav = str(self.output_path / f"host_{self.session_id}.wav")
        guest_wav = str(self.output_path / f"guest_{self.session_id}.wav")
        
        self._generate_batch_audio(host_texts, self.host_voice, host_wav)
        # ✅ guest 발화가 없으면 guest wav를 만들지 않음
        if guest_texts:
            self._generate_batch_audio(guest_texts, self.guest_voice, guest_wav)
        else:
            guest_wav = None
        
        self.tts_time = time.time() - tts_start
        
        # Stage 2: STT
        print("\n" + "="*60)
        print("📍 Stage 2: STT 변환")
        print("="*60)
        
        stt_start = time.time()
        
        host_words = self._transcribe_audio(host_wav)
        # ✅ guest가 없으면 STT 스킵
        if guest_wav:
            guest_words = self._transcribe_audio(guest_wav)
        else:
            guest_words = []
        
        self.stt_time = time.time() - stt_start
        
        # Stage 3: 분할
        print("\n" + "="*60)
        print("📍 Stage 3: 강화된 분할 (후보군 방식)")
        print("="*60)
        
        segment_start = time.time()
        
        host_segs = self._find_segments_robust(host_wav, host_words, host_texts)
        # ✅ guest가 없으면 분할 스킵
        if guest_wav:
            guest_segs = self._find_segments_robust(guest_wav, guest_words, guest_texts)
        else:
            guest_segs = []
        
        self.segment_time = time.time() - segment_start
        
        # Stage 4: 병합
        print("\n" + "="*60)
        print("📍 Stage 4: 안전한 병합")
        print("="*60)
        
        merge_start = time.time()
        
        # ✅ 고유한 최종 파일명 (session_id 포함)
        final_wav = str(self.output_path / f"podcast_final_{self.session_id}.wav")
        # ✅ guest가 없으면 host만으로 병합(=사실상 host 복사)
        if guest_wav:
            self._merge_segments_safe(
                dialogues, host_wav, guest_wav,
                host_segs, guest_segs, final_wav
            )
        else:
            # host_wav를 최종 파일로 복사 (wave 복사로 안전하게)
            with wave.open(host_wav, 'rb') as src:
                params = src.getparams()
                frames = src.readframes(src.getnframes())
            with wave.open(final_wav, 'wb') as dst:
                dst.setparams(params)
                dst.writeframes(frames)
        
        self.merge_time = time.time() - merge_start
        
        print("\n" + "="*60)
        print("🎉 완료! 최종 WAV 파일:")
        print(f"   📁 {final_wav}")
        print("="*60 + "\n")
        
        print("📊 성능 측정:")
        print(f"   TTS: {self.tts_time:.2f}초")
        print(f"   STT: {self.stt_time:.2f}초")
        print(f"   분할: {self.segment_time:.2f}초")
        print(f"   병합: {self.merge_time:.2f}초")
        print(f"   총: {self.tts_time + self.stt_time + self.segment_time + self.merge_time:.2f}초")
        print(f"   API 호출: {self.api_calls}번")
        print(f"   429 에러: {self.error_429_count}번")
        print(f"   재시도: {self.retry_count}번")
        print("="*60 + "\n")
        
        # ✅ 최종 WAV 경로 + 세그먼트 정보 반환 (정확한 타임스탬프용!)
        return final_wav, host_segs, guest_segs


if __name__ == "__main__":
    # 테스트: 선생님 긴 발화 + 학생 짧은 응답
    dialogues = []
    for i in range(50):
        # 선생님: 긴 설명 (100자)
        dialogues.append(Dialogue(
            "host", 
            f"선생님 발화 {i+1}번입니다. 오늘은 중요한 개념에 대해 자세히 설명드리겠습니다. 이 내용은 여러분의 학습에 매우 중요합니다."
        ))
        # 학생: 짧은 응답 (20자)
        dialogues.append(Dialogue(
            "guest", 
            f"네, 이해했어요!"
        ))
    
    generator = TailFocusV5Generator(
        tail_thresholds=[0.70, 0.60, 0.50],
        top_n_candidates=10
    )
    generator.generate(dialogues)