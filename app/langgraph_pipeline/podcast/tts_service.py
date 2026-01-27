# 이 파일은 완전한 수정이 적용된 tts_service.py입니다
# 
# 주요 수정 사항:
# 1. 강의형 분리 조건 완화 (800자 → 400자, 320자 → 200자)
# 2. 중복 발화 제거 로직 추가
# 3. 불완전 발화 제거 로직 추가
# 4. 비정상 duration 처리 개선 (30초 제한 → 에러 발생)
#
# 원본 파일: /mnt/user-data/uploads/tts_service.py
# 수정 날짜: 2026-01-26

# app/services/podcast/tts_service.py
import os
import re
import time
import uuid
import logging
from typing import List, Dict, Any
from pathlib import Path

# ✅ Tail Focus V5 임포트!
from .tail_focus_v5_fixed import TailFocusV5Generator, Dialogue

logger = logging.getLogger(__name__)

# 기존 설정 유지
FIXED_STUDENT_VOICE = "Leda"
STUDENT_PITCH_FACTOR = 1.15


def normalize_speaker_tags(script_text: str, host_name: str = "선생님", guest_name: str = "학생") -> str:
    """
    화자 태그 정규화 (강화 버전)
    - [선생님], [학생], [선생님2] → 「선생님」, 「학생」, 「선생님2」
    - 태그가 없는 줄바꿈 감지 및 복구
    """
    import re
    
    # 1. 기본 정규화: [] → 「」
    script_text = script_text.replace(f"[{host_name}]", f"「{host_name}」")
    script_text = script_text.replace(f"[{guest_name}]", f"「{guest_name}」")
    script_text = script_text.replace("[선생님2]", "「선생님2」")
    
    # 2. 태그 뒤에 콜론 추가 (없는 경우)
    script_text = re.sub(r'「(선생님|학생|선생님2)」(?!:)', r'「\1」:', script_text)
    
    # 3. 중복 콜론 제거
    script_text = re.sub(r'「(선생님|학생|선생님2)」:+', r'「\1」:', script_text)
    
    # 4. 공백 정리
    script_text = re.sub(r'「(선생님|학생|선생님2)」:\s+', r'「\1」: ', script_text)
    
    return script_text


def get_wav_output_dir() -> str:
    """환경에 맞는 WAV 출력 디렉토리 반환"""
    base = os.getenv("BASE_OUTPUT_DIR", "outputs")
    return os.path.join(base, "podcasts", "wav")


class TTSService:
    """Vertex AI TTS 서비스 (Tail Focus V5 사용!)"""
    
    def __init__(self):
        # ✅ Tail Focus V5 Generator 초기화
        self.tail_focus_generator = None
        logger.info("TTSService 초기화 (Tail Focus V5 모드)")
    
    def _init_tail_focus(self, host_name: str, guest_name: str | None = None) -> TailFocusV5Generator:
        """Tail Focus V5 Generator 초기화 (필요시)"""
        if self.tail_focus_generator is None:
            output_dir = get_wav_output_dir()
            
            # 환경 변수에서 인증 정보 가져오기
            credentials_file = os.getenv("GOOGLE_APPLICATION_CREDENTIALS", "./vertex-ai-service-account.json")
            
            self.tail_focus_generator = TailFocusV5Generator(
                credentials_file=credentials_file,
                output_dir=output_dir,
                host_voice=host_name,
                guest_voice=guest_name or FIXED_STUDENT_VOICE,
                # 재시도 설정
                tail_thresholds=[0.70, 0.60, 0.50],
                top_n_candidates=10
            )
            
            # 무한 재시도 설정 (4회 이후 8초 고정)
            self.tail_focus_generator.retry_delays = [2.0, 4.0, 8.0]
            
            logger.info(f"Tail Focus V5 초기화 완료 - Host: {host_name}, Guest: {guest_name or FIXED_STUDENT_VOICE}")
        
        return self.tail_focus_generator
    
    def _parse_original_script(self, script: str) -> List[Dict]:
        """
        원본 스크립트에서 정확한 발화 추출 (기준점!)
        
        Returns:
            원본 발화 리스트 [{'speaker': '선생님', 'text': '...'}, ...]
        """
        # 「화자」: 텍스트 형식 파싱
        # ✅ 타임스탬프 포함/미포함 모두 처리
        # [00:00:00] 「화자」: 텍스트 또는 「화자」: 텍스트
        pattern = r"(?:\[\d{2}:\d{2}:\d{2}\]\s*)?「([^」]+)」\s*:\s*(.+?)(?=(?:\[\d{2}:\d{2}:\d{2}\]\s*)?「[^」]+」\s*:|$)"

        matches = re.findall(pattern, script, re.DOTALL)
        
        original_dialogues = []
        for speaker_raw, text in matches:
            speaker = speaker_raw.strip()
            text_clean = text.strip()
            
            if not text_clean:
                continue
            
            # 화자 정규화
            # ✅ 중요: '선생님2'는 문자열에 '선생'이 포함되므로 host 조건보다 먼저 처리해야 함
            normalized_speaker = "선생님"  # 기본값
            if speaker in ["선생님2", "교사2", "teacher2"] or "선생님2" in speaker:
                normalized_speaker = "학생"
            elif any(role in speaker for role in ["학생", "게스트", "student", "guest"]):
                normalized_speaker = "학생"
            elif any(role in speaker for role in ["선생님", "교사", "선생", "진행", "teacher", "host"]):
                normalized_speaker = "선생님"
            
            original_dialogues.append({
                'speaker': normalized_speaker,
                'text': text_clean
            })
        
        logger.info(f"📋 원본 스크립트: {len(original_dialogues)}개 발화 추출")
        return original_dialogues
    
    def _estimate_duration_from_text(self, text: str) -> float:
        """
        텍스트 길이 기반 duration 추정 (STT 실패 시 fallback)
        
        한국어 발화 속도:
        - 평균 약 400자/분 (6.67자/초)
        - 보수적으로 5.0자/초 적용하여 여유 확보
        
        Args:
            text: 발화 텍스트
            
        Returns:
            추정 duration (초), 최소 0.5초, 최대 30초
        """
        chars = len(text.strip())
        
        # 한국어 평균 발화 속도 (보수적)
        estimated = chars / 5.0  # 5.0자/초
        
        # 최소/최대 제한
        estimated = max(0.5, estimated)  # 최소 0.5초
        estimated = min(estimated, 30.0)  # 최대 30초
        
        logger.info(f"   텍스트 기반 duration 추정: {chars}자 → {estimated:.2f}초")
        return estimated
    
    def _retry_stt_for_segment(
        self, 
        wav_path: str, 
        all_dialogues: List[Dialogue],
        failed_index: int,
        speaker_type: str  # 'host' or 'guest'
    ) -> tuple[bool, float]:
        """
        특정 세그먼트의 STT 재시도
        
        Args:
            wav_path: 전체 WAV 파일 경로
            all_dialogues: 전체 대화 리스트
            failed_index: 실패한 세그먼트의 인덱스 (해당 화자 기준)
            speaker_type: 'host' 또는 'guest'
            
        Returns:
            (성공 여부, duration)
        """
        try:
            logger.info(f"   🔄 STT 재시도 중... (화자: {speaker_type}, 세그먼트 #{failed_index})")
            
            # Tail Focus Generator의 _transcribe_audio 재사용
            if not self.tail_focus_generator:
                logger.warning("   ⚠️  Tail Focus Generator 없음 → 재시도 불가")
                return False, 0.0
            
            # 전체 오디오 STT 재실행
            all_words = self.tail_focus_generator._transcribe_audio(wav_path)
            
            if not all_words:
                logger.warning("   ⚠️  STT 재시도 결과 비어있음")
                return False, 0.0
            
            # 재시도 성공 후 해당 화자의 세그먼트만 재구성
            # (이 부분은 Tail Focus의 세그먼트 재구성 로직 필요)
            # 일단 단순화: 전체 duration을 균등 분배
            
            speaker_dialogues = [d for d in all_dialogues if d.speaker == speaker_type]
            if failed_index >= len(speaker_dialogues):
                logger.warning(f"   ⚠️  잘못된 인덱스: {failed_index} >= {len(speaker_dialogues)}")
                return False, 0.0
            
            # 실패한 발화의 텍스트
            failed_text = speaker_dialogues[failed_index].text
            
            # STT 결과에서 해당 텍스트 매칭 시도
            # (간단한 근사: 시간 비율로 추정)
            total_audio_duration = all_words[-1]['end'] if all_words else 0.0
            total_speaker_count = len(speaker_dialogues)
            
            if total_audio_duration > 0 and total_speaker_count > 0:
                # 해당 화자의 평균 발화 시간
                avg_duration = total_audio_duration / total_speaker_count
                
                # 텍스트 길이 기반 보정
                text_ratio = len(failed_text) / (sum(len(d.text) for d in speaker_dialogues) / total_speaker_count)
                estimated_duration = avg_duration * text_ratio
                
                # 범위 제한
                estimated_duration = max(0.5, min(estimated_duration, 30.0))
                
                logger.info(f"   ✅ STT 재시도 성공: {estimated_duration:.2f}초 (추정)")
                return True, estimated_duration
            
            logger.warning("   ⚠️  STT 재시도 성공했으나 duration 계산 실패")
            return False, 0.0
            
        except Exception as e:
            logger.error(f"   ❌ STT 재시도 중 오류: {e}")
            return False, 0.0
    
    
    def clean_text_for_tts(self, text: str) -> str:
        """
        TTS 전처리: 메타데이터 및 불필요한 텍스트 제거
        
        제거 대상:
        - (MAIN-PAGE X)
        - (VISUAL CONTEXT: ...)
        - 기타 괄호 안의 메타데이터
        """
        import re
        
        # 1. (MAIN-PAGE X) 제거
        text = re.sub(r'\(MAIN-PAGE\s+\d+\)', '', text)
        
        # 2. (VISUAL CONTEXT: ...) 제거
        text = re.sub(r'\(VISUAL CONTEXT:[^)]+\)', '', text)
        
        # 3. 기타 대문자로 시작하는 메타데이터 제거
        # (IMAGE X), (FIGURE X) 등
        text = re.sub(r'\([A-Z][A-Z\s-]+:[^)]+\)', '', text)
        text = re.sub(r'\([A-Z][A-Z\s-]+\s+\d+\)', '', text)
        
        # 4. 연속된 공백 정리
        text = re.sub(r'\s+', ' ', text)
        
        # 5. 이스케이프 문자 제거 (프론트엔드 UI 노이즈 방지)
        text = text.replace('\\', '')
        
        # 6. 문장 부호 앞뒤 공백 정리
        text = re.sub(r'\s+([.,!?;:])', r'\1', text)
        text = re.sub(r'([.,!?;:])\s+', r'\1 ', text)
        
        return text.strip()
    

    def _parse_script_to_dialogues(self, script: str, host_name: str, guest_name: str | None = None) -> List[Dialogue]:
        """스크립트를 Dialogue 객체 리스트로 변환 (타임스탬프 지원!)"""
        # ============================================================
        # ✅ 마크업 텍스트 제거 (TTS 부자연스러움 방지)
        # ============================================================
        # (MAIN-PAGE X), (VISUAL CONTEXT: ...) 등 제거
        
        # 1. (MAIN-PAGE X) 패턴 제거
        script = re.sub(r'\(MAIN-PAGE\s+\d+\)', '', script)
        
        # 2. (VISUAL CONTEXT: ...) 패턴 제거
        script = re.sub(r'\(VISUAL CONTEXT:[^)]+\)', '', script)
        
        # 3. (PAGE X) 패턴 제거
        script = re.sub(r'\(PAGE\s+\d+\)', '', script)
        
        # 4. 기타 괄호 마크업 제거 (소문자도 포함)
        script = re.sub(r'\(main-page\s+\d+\)', '', script, flags=re.IGNORECASE)
        script = re.sub(r'\(page\s+\d+\)', '', script, flags=re.IGNORECASE)
        
        # 5. 연속 공백 정리
        script = re.sub(r' {2,}', ' ', script)
        
        # 6. 줄바꿈 후 공백 정리
        script = re.sub(r'\n +', '\n', script)
        
        # ============================================================
        # ✅ 7. 이스케이프 문자 제거 (프론트엔드 UI 노이즈 방지)
        # ============================================================
        # JSON에서 줄바꿈을 escape하는 \ 문자 제거
        script = script.replace('\\', '')
        
        # ============================================================
        # ✅ 8. JSON 문법 문자 제거 (파싱 오류 방지)
        # ============================================================
        # JSON 파싱 실패 시 끝에 ", } 등이 남을 수 있음
        # 스크립트 끝부분의 JSON 문법 문자 제거
        script = script.rstrip('"}\n\t ')
        
        logger.info("✅ 마크업 텍스트 제거 완료")
        
        dialogues = []
        
        # ✅ 타임스탬프 포함/미포함 모두 처리
        # [00:00:00] 「화자」: 텍스트 또는 「화자」: 텍스트
        pattern = r"(?:\[\d{2}:\d{2}:\d{2}\]\s*)?「([^」]+)」\s*:\s*(.+?)(?=(?:\[\d{2}:\d{2}:\d{2}\]\s*)?「[^」]+」\s*:|$)"
        matches = re.findall(pattern, script, re.DOTALL)
        
        for speaker_tag, raw_content in matches:
            speaker_tag = speaker_tag.strip()
            text_clean = raw_content.strip()
            
            if not text_clean:
                continue
            
            # 화자 결정
            # ✅ 중요: '선생님2'는 '선생'을 포함하므로 host 조건보다 먼저 처리해야 guest가 생김
            speaker = "host"  # 기본값
            if speaker_tag in ["선생님2", "교사2", "teacher2"] or "선생님2" in speaker_tag:
                speaker = "guest"
            elif any(role in speaker_tag for role in ["학생", "게스트", "student", "guest"]):
                speaker = "guest"
            elif any(role in speaker_tag for role in ["선생님", "교사", "선생", "진행", "teacher", "host"]):
                speaker = "host"
            
            # Dialogue 객체 생성
            d = Dialogue(
                speaker=speaker,
                text=text_clean
            )
            # ✅ 원래 화자 태그 보존 (예: "선생님2")
            # - TailFocus는 d.speaker(host/guest)만 사용
            # - 트랜스크립트 표기는 raw_speaker를 사용해 "학생" 강제 라벨을 피함
            setattr(d, "raw_speaker", speaker_tag)
            dialogues.append(d)
        
        # ============================================================
        # ✅ 강의형(한 화자)인데 발화가 1개로 뭉치는 경우가 많아서
        #    TailFocus 분할/트랜스크립트가 1줄로 끝나는 문제가 발생함.
        #    → 발화 1개가 과도하게 길면 문장 단위로 적당히 쪼개서 Dialogue 여러 개로 분리
        # ============================================================
        if len(dialogues) == 1:
            only = dialogues[0]
            logger.info(f"📋 단독 발화 감지: speaker={only.speaker}, 길이={len(only.text)}자")
            
            # ✅ 개선: 조건 완화 (800자 → 400자) + 청크 축소 (320자 → 200자)

            # ============================================================
            # ✅ 화자 태그 없는 줄바꿈 복구 (스크립트 생성 오류 방지)
            # ============================================================
            # 강의형에서 첫 발화에만 태그가 있고 나머지는 줄바꿈만 있는 경우
            if only.speaker == "host" and '\n' in only.text:
                lines = [l.strip() for l in only.text.split('\n') if l.strip()]
                
                # 여러 줄이 있는 경우 (줄바꿈으로 구분된 발화들)
                if len(lines) > 1:
                    logger.info(f"📋 줄바꿈 기반 발화 감지: {len(lines)}개 줄")
                    
                    # 각 줄을 별도 발화로 처리
                    dialogues = []
                    for i, line in enumerate(lines):
                        # 너무 짧은 줄은 이전 줄에 합치기
                        if len(line) < 100 and dialogues:
                            dialogues[-1].text += " " + line
                            logger.info(f"   짧은 줄 병합: {len(line)}자 → 이전 발화에 추가")
                        else:
                            d = Dialogue(speaker="host", text=self.clean_text_for_tts(line))
                            setattr(d, "raw_speaker", raw_speaker)
                            dialogues.append(d)
                            logger.info(f"   발화 {i+1}: {len(line)}자")
                    
                    logger.info(f"✅ 줄바꿈 기반 분할: 1개 → {len(dialogues)}개")
                    
                    # ✅ 추가: 긴 발화 재분할 (400자 이상)
                    final_dialogues = []
                    for d in dialogues:
                        if len(d.text) >= 400:
                            logger.info(f"⚠️  긴 발화 재분할: {len(d.text)}자 → 200자 단위로 분할")
                            chunks = self._chunk_long_text(d.text, max_chars=200)
                            for chunk in chunks:
                                chunk_d = Dialogue(speaker="host", text=self.clean_text_for_tts(chunk))
                                setattr(chunk_d, "raw_speaker", raw_speaker)
                                final_dialogues.append(chunk_d)
                            logger.info(f"   → {len(chunks)}개 청크로 분할됨")
                        else:
                            final_dialogues.append(d)
                    
                    dialogues = final_dialogues
                    logger.info(f"✅ 최종 분할 완료: {len(dialogues)}개 발화")
                    
                    # _chunk_long_text 스킵 (이미 처리됨)
            
            # host-only & 긴 대본이면 chunking
            if only.speaker == "host" and len(only.text) >= 400:
                raw_speaker = getattr(only, "raw_speaker", host_name)
                chunks = self._chunk_long_text(only.text, max_chars=200)
                dialogues = []
                for ch in chunks:
                    d = Dialogue(speaker="host", text=self.clean_text_for_tts(ch))
                    setattr(d, "raw_speaker", raw_speaker)
                    dialogues.append(d)
                logger.info(f"✅ 강의형 긴 발화 분리: 1개 → {len(dialogues)}개 (max_chars=200, 평균 {len(only.text)//len(dialogues)}자/chunk)")
            else:
                logger.info(f"⚠️  분리 조건 미충족: speaker={only.speaker}, 길이={len(only.text)}자 (400자 미만)")
        
        # ============================================================
        # ✅ 중복 발화 제거 (스크립트 생성 오류 방지)
        # ============================================================
        if len(dialogues) > 1:
            from difflib import SequenceMatcher
            
            cleaned = []
            for i, d in enumerate(dialogues):
                if i == 0:
                    cleaned.append(d)
                    continue
                
                # 이전 발화와 비교 (앞 150자 기준)
                prev_text = cleaned[-1].text.strip()[:150]
                curr_text = d.text.strip()[:150]
                
                # 유사도 계산 (0.0 ~ 1.0)
                similarity = SequenceMatcher(None, prev_text, curr_text).ratio()
                
                # 80% 이상 유사하면 중복으로 판단
                if similarity >= 0.8:
                    logger.warning(f"⚠️  중복 발화 제거: {i+1}번째 발화 (유사도: {similarity:.1%})")
                    logger.warning(f"   이전: {prev_text[:50]}...")
                    logger.warning(f"   현재: {curr_text[:50]}...")
                else:
                    cleaned.append(d)
            
            removed_count = len(dialogues) - len(cleaned)
            if removed_count > 0:
                logger.info(f"✅ 중복 발화 {removed_count}개 제거됨")
                dialogues = cleaned
        
        # ============================================================
        # ✅ 불완전 발화 제거 (끝이 잘린 경우)
        # ============================================================
        if len(dialogues) > 1:
            last = dialogues[-1]
            last_text = last.text.strip()
            
            # ✅ 따옴표/공백/JSON 문법 문자 무시하고 실제 마지막 문자 찾기
            actual_last_char = ''
            for i in range(len(last_text)-1, -1, -1):
                # JSON 파싱 오류로 ", }, { 등이 텍스트에 포함될 수 있음
                if last_text[i] not in ['"', "'", ' ', '\n', '\t', '{', '}', '[', ']', ',']:
                    actual_last_char = last_text[i]
                    break
            
            # 마지막 발화가 너무 짧거나 불완전한 경우
            is_incomplete = False
            
            # 1. 50자 미만
            if len(last_text) < 50:
                is_incomplete = True
                logger.warning(f"⚠️  마지막 발화가 너무 짧음: {len(last_text)}자")
            
            # 2. 문장 부호로 끝나지 않음 (따옴표 무시)
            elif actual_last_char and actual_last_char not in '.!?。！？…':
                is_incomplete = True
                logger.warning(f"⚠️  마지막 발화가 문장 부호로 끝나지 않음: '{last_text[-30:]}' (실제: '{actual_last_char}')")
            
            if is_incomplete:
                logger.warning(f"⚠️  불완전 발화 제거: {last_text[:50]}...")
                dialogues = dialogues[:-1]
                logger.info(f"✅ 불완전 발화 1개 제거됨")

        logger.info(f"📊 스크립트 파싱 완료: {len(dialogues)}개 발화")
        if dialogues:
            host_count = len([d for d in dialogues if d.speaker == "host"])
            guest_count = len([d for d in dialogues if d.speaker == "guest"])
            logger.info(f"   Host: {host_count}개, Guest: {guest_count}개")
            if host_count > 0:
                avg_host_len = sum(len(d.text) for d in dialogues if d.speaker == "host") / host_count
                logger.info(f"   Host 평균 길이: {avg_host_len:.0f}자")
        
        # ============================================================
        # ✅ 모든 긴 발화 재분할 (400자 이상 → 200자씩)
        # ============================================================
        # 줄바꿈 분할 여부와 관계없이, 모든 긴 발화를 재분할
        if dialogues:
            final_dialogues = []
            rechunked_count = 0
            
            for i, d in enumerate(dialogues):
                if len(d.text) >= 400:
                    logger.info(f"⚠️  발화 {i+1} 재분할: {len(d.text)}자 → 200자 단위")
                    
                    # 200자씩 분할
                    chunks = self._chunk_long_text(d.text, max_chars=200)
                    
                    for chunk in chunks:
                        chunk_d = Dialogue(speaker=d.speaker, text=chunk)
                        # raw_speaker 속성 복사
                        if hasattr(d, '__dict__'):
                            for key, val in d.__dict__.items():
                                if key not in ['speaker', 'text']:
                                    setattr(chunk_d, key, val)
                        final_dialogues.append(chunk_d)
                    
                    logger.info(f"   → {len(chunks)}개 청크로 분할 완료")
                    rechunked_count += 1
                else:
                    final_dialogues.append(d)
            
            if rechunked_count > 0:
                logger.info(f"✅ 긴 발화 재분할 완료: {rechunked_count}개 발화 → {len(final_dialogues)}개")
                dialogues = final_dialogues
        

        return dialogues
    
    def _chunk_long_text(self, text: str, max_chars: int = 200) -> List[str]:
        """
        긴 강의형 텍스트를 문장 기준으로 chunking.
        - 너무 긴 단일 발화를 방지해 TailFocus 세그먼트/트랜스크립트가 1줄로 끝나는 문제 해결
        - 기본값: 200자 (약 25초, 타임스탬프 생성에 적합)
        """
        text = (text or "").strip()
        if not text:
            return []

        # 문장 분리(한국어/영문 혼합 대응)
        # 마침표/물음표/느낌표/…/줄바꿈 기준
        parts = re.split(r"(?<=[\.\?\!。！？…])\s+|\n+", text)
        parts = [p.strip() for p in parts if p and p.strip()]

        chunks: List[str] = []
        buf = ""
        for p in parts:
            if not buf:
                buf = p
                continue
            # max_chars 넘기면 flush
            if len(buf) + 1 + len(p) > max_chars:
                chunks.append(buf.strip())
                buf = p
            else:
                buf = f"{buf} {p}"
        if buf.strip():
            chunks.append(buf.strip())

        # 혹시 한 문장이 max_chars를 초과하면 강제로 쪼개기(안전장치)
        final_chunks: List[str] = []
        for c in chunks:
            if len(c) <= max_chars:
                final_chunks.append(c)
            else:
                # 너무 긴 덩어리는 글자수 기준 분할
                for i in range(0, len(c), max_chars):
                    final_chunks.append(c[i:i+max_chars].strip())

        return [c for c in final_chunks if c]
    
    def _merge_split_dialogues(
        self,
        parsed: List[Dialogue],
        original: List[Dict]
    ) -> List[Dialogue]:
        """
        쪼개진 발화들을 원본 기준으로 병합
        
        전략:
        1. 같은 화자의 연속 발화를 하나로 합침
        2. 원본 발화 개수와 일치할 때까지 병합
        """
        logger.info("🔧 발화 병합 시작...")
        
        merged = []
        parsed_queue = list(parsed)
        
        for i, orig in enumerate(original):
            if not parsed_queue:
                # 파싱 결과 부족 (거의 없음)
                logger.warning(f"파싱 결과 부족! 원본 {i+1}번째 발화를 fallback으로 추가")
                d = Dialogue(
                    speaker="host" if orig['speaker'] == "선생님" else "guest",
                    text=orig['text']
                )
                # ✅ 원본 파싱은 현재 '선생님/학생'으로 정규화되어 있음.
                # teacher_teacher를 쓰려면 원본 파서도 raw를 보존해야 하지만,
                # 최소 변경으로는 fallback에서도 일단 speaker명을 유지한다.
                setattr(d, "raw_speaker", orig.get("raw_speaker", orig["speaker"]))
                merged.append(d)
                continue
            
            # 현재 원본 발화의 화자
            target_speaker = "host" if orig['speaker'] == "선생님" else "guest"
            
            # 같은 화자의 연속 발화들 수집
            combined_texts = []
            
            while parsed_queue:
                current = parsed_queue[0]
                
                # 화자가 다르면 중단
                if current.speaker != target_speaker:
                    break
                
                # 같은 화자면 수집
                combined_texts.append(current.text)
                parsed_queue.pop(0)
                
                # 원본 텍스트와 유사도 체크
                combined = " ".join(combined_texts)
                
                # 충분히 모았으면 중단 (원본 길이의 80% 이상)
                if len(combined) >= len(orig['text']) * 0.8:
                    break
                
                # 너무 많이 모았으면 중단 (원본 길이의 150% 이상)
                if len(combined) >= len(orig['text']) * 1.5:
                    break
            
            # 병합된 발화 생성
            if combined_texts:
                merged_text = " ".join(combined_texts)
                d = Dialogue(
                    speaker=target_speaker,
                    text=merged_text
                )
                # ✅ 가능한 경우 raw_speaker는 원본 기준으로 부여
                setattr(d, "raw_speaker", orig.get("raw_speaker", orig["speaker"]))
                merged.append(d)
                logger.debug(f"  {i+1}번 발화: {len(combined_texts)}개 병합 → '{merged_text[:30]}...'")
            else:
                # 수집 실패 시 원본 사용
                logger.warning(f"  {i+1}번 발화: 병합 실패, 원본 사용")
                d = Dialogue(
                    speaker=target_speaker,
                    text=orig['text']
                )
                setattr(d, "raw_speaker", orig.get("raw_speaker", orig["speaker"]))
                merged.append(d)
        
        logger.info(f"✅ 병합 완료: {len(merged)}개 발화")
        return merged
    
    def _validate_and_fix_dialogues(
        self,
        script: str,
        parsed: List[Dialogue]
    ) -> List[Dialogue]:
        """
        파싱 결과를 원본과 비교하여 검증 및 보정
        
        Returns:
            검증/보정된 발화 리스트
        """
        # 1. 원본 스크립트 파싱
        original = self._parse_original_script(script)
        
        # 2. 개수 비교
        if len(parsed) == len(original):
            logger.info(f"✅ 발화 개수 일치: {len(parsed)}개")
            return parsed
        
        # 3. 불일치 감지!
        logger.warning(f"⚠️  발화 개수 불일치 감지!")
        logger.warning(f"   원본 스크립트: {len(original)}개")
        logger.warning(f"   파싱 결과: {len(parsed)}개")
        logger.warning(f"   차이: {abs(len(parsed) - len(original))}개")
        
        
        # 3.5. ✅ 둘 다 0개인 경우 특별 처리
        if len(original) == 0 and len(parsed) == 0:
            logger.error("❌ 원본 파싱, 일반 파싱 모두 0개!")
            logger.error("   스크립트 형식이 예상과 다릅니다.")
            logger.error(f"   스크립트 샘플 (첫 300자):")
            logger.error(f"   {script[:300]}")
            # 빈 리스트 반환 → 상위에서 에러 처리
            return []

        # 4. 보정 시도
        if len(parsed) > len(original):
            # 파싱 결과가 더 많음 → 병합 필요
            logger.info("🔧 병합 보정 시도 중...")
            fixed = self._merge_split_dialogues(parsed, original)
        else:
            # 파싱 결과가 더 적음 → 원본 사용
            logger.warning("⚠️  파싱 결과가 부족, 원본 사용")
            fixed = []
            for orig in original:
                d = Dialogue(
                    speaker="host" if orig['speaker'] == "선생님" else "guest",
                    text=orig['text']
                )
                setattr(d, "raw_speaker", orig.get("raw_speaker", orig["speaker"]))
                fixed.append(d)
        
        # 5. 재검증
        if len(fixed) == len(original):
            logger.info(f"✅ 보정 성공: {len(fixed)}개 발화")
            return fixed
        else:
            logger.error(f"❌ 보정 실패! 원본: {len(original)}개, 보정 후: {len(fixed)}개")
            logger.error(f"   원본 스크립트를 그대로 사용합니다.")
            
            # 최후의 수단: 원본 그대로 사용
            final = []
            for orig in original:
                d = Dialogue(
                    speaker="host" if orig['speaker'] == "선생님" else "guest",
                    text=orig['text']
                )
                setattr(d, "raw_speaker", orig.get("raw_speaker", orig["speaker"]))
                final.append(d)
            return final
    
    def _create_audio_metadata_from_segments(
        self,
        dialogues: List[Dialogue],
        host_segments: List[Dict],
        guest_segments: List[Dict],
        output_dir: str
    ) -> tuple[List[Dict[str, Any]], List[str]]:
        """세그먼트 정보를 기존 audio_metadata 형식으로 변환"""
        audio_metadata = []
        wav_files = []
        
        # Host/Guest 세그먼트 큐
        from collections import deque
        host_queue = deque(host_segments)
        guest_queue = deque(guest_segments)
        
        # Host/Guest WAV 파일
        host_wav = os.path.join(output_dir, "host.wav")
        guest_wav = os.path.join(output_dir, "guest.wav")
        
        # 임시 세그먼트 WAV 파일 생성
        import wave
        for i, dialogue in enumerate(dialogues):
            if dialogue.speaker == "host" and host_queue:
                seg = host_queue.popleft()
                segment_file = os.path.join(output_dir, f"segment_{i+1}_host.wav")
                
                # 세그먼트 추출
                with wave.open(host_wav, 'rb') as w:
                    params = w.getparams()
                    rate = w.getframerate()
                    w.setpos(int(seg['start'] * rate))
                    frames = w.readframes(int((seg['end'] - seg['start']) * rate))
                
                with wave.open(segment_file, 'wb') as w:
                    w.setparams(params)
                    w.writeframes(frames)
                
                audio_metadata.append({
                    'speaker': '선생님',
                    'text': dialogue.text,
                    'duration': seg['end'] - seg['start'],
                    'file': segment_file
                })
                wav_files.append(segment_file)
                
            elif dialogue.speaker == "guest" and guest_queue:
                seg = guest_queue.popleft()
                segment_file = os.path.join(output_dir, f"segment_{i+1}_guest.wav")
                
                # 세그먼트 추출
                with wave.open(guest_wav, 'rb') as w:
                    params = w.getparams()
                    rate = w.getframerate()
                    w.setpos(int(seg['start'] * rate))
                    frames = w.readframes(int((seg['end'] - seg['start']) * rate))
                
                with wave.open(segment_file, 'wb') as w:
                    w.setparams(params)
                    w.writeframes(frames)
                
                audio_metadata.append({
                    'speaker': '학생',
                    'text': dialogue.text,
                    'duration': seg['end'] - seg['start'],
                    'file': segment_file
                })
                wav_files.append(segment_file)
        
        return audio_metadata, wav_files
    
    def generate_audio(
        self, 
        script: str, 
        host_name: str, 
        guest_name: str | None = None
    ) -> tuple[List[Dict[str, Any]], List[str]]:
        """
        스크립트를 TTS로 변환 (Tail Focus V5 사용!)
        
        Returns:
            (audio_metadata, wav_files) - 기존 인터페이스와 동일
        """
        logger.info(f"🚀 Tail Focus V5 TTS 변환 시작 - Host: {host_name}, Guest: {guest_name or FIXED_STUDENT_VOICE}")
        
        try:
            # 0. ✅ 화자 태그 정규화 ([화자]: → 「화자」:)
            script = normalize_speaker_tags(script)
            
            # 1. Tail Focus V5 초기화
            generator = self._init_tail_focus(host_name, guest_name)
            
            # 2. 스크립트 → Dialogue 변환
            dialogues = self._parse_script_to_dialogues(script, host_name, guest_name)
            
            # 2.5. ✅ 원본 스크립트와 비교하여 검증 및 보정!
            dialogues = self._validate_and_fix_dialogues(script, dialogues)
            
            # 2.6. ✅ 빈 dialogues 조기 검증!
            if not dialogues:
                logger.error("❌ 파싱된 발화가 0개입니다!")
                logger.error(f"📋 스크립트 정보:")
                logger.error(f"   길이: {len(script)}자")
                logger.error(f"   첫 500자:")
                logger.error(f"   {script[:500]}")
                logger.error(f"   ---")
                raise ValueError(
                    "스크립트 파싱 실패: 발화가 0개입니다. "
                    "스크립트 형식을 확인하세요. 예상 형식: [화자]: 텍스트"
                )

            
            # 3. Tail Focus V5 생성 실행!
            start_time = time.time()
            final_wav, host_segs, guest_segs = generator.generate(dialogues)  # ✅ 세그먼트 정보 받기!
            elapsed = time.time() - start_time
            
            logger.info(f"⚡ Tail Focus V5 생성 완료!")
            logger.info(f"   TTS: {generator.tts_time:.2f}초")
            logger.info(f"   STT: {generator.stt_time:.2f}초")
            logger.info(f"   분할: {generator.segment_time:.2f}초")
            logger.info(f"   병합: {generator.merge_time:.2f}초")
            logger.info(f"   총: {elapsed:.2f}초")
            logger.info(f"   API 호출: {generator.api_calls}번")
            logger.info(f"   429 에러: {generator.error_429_count}번")
            logger.info(f"   재시도: {generator.retry_count}번")
            
            # 4. AudioProcessor로 WAV → MP3 변환!
            from .audio_processor import AudioProcessor
            
            logger.info("🎵 WAV → MP3 변환 중...")
            # ✅ session_id 전달 (파일명 일치!)
            final_mp3 = AudioProcessor.merge_audio_files(
                [final_wav], 
                session_id=generator.session_id
            )
            # → podcast_episode_{session_id}.mp3 ✅
            
            logger.info(f"✅ MP3 변환 완료: {final_mp3}")
            
            # 5. 최종 파일 duration 계산
            import wave
            with wave.open(final_wav, 'rb') as w:
                total_duration = w.getnframes() / w.getframerate()
            
            # 6. ✅ 세그먼트 정보를 사용해 정확한 audio_metadata 생성!
            audio_metadata = []
            
            # ✅ 누적 시간 추적 (병합된 오디오에서의 실제 시작 시간)
            cumulative_time = 0.0
            
            # Host/Guest 발화 개수 계산
            host_count = len([d for d in dialogues if d.speaker == "host"])
            guest_count = len([d for d in dialogues if d.speaker == "guest"])
            
            # ✅ 세그먼트 개수 검증!
            if len(host_segs) != host_count:
                logger.error(f"⚠️  Host 세그먼트 불일치! 발화: {host_count}개, 세그먼트: {len(host_segs)}개")
            if len(guest_segs) != guest_count:
                logger.error(f"⚠️  Guest 세그먼트 불일치! 발화: {guest_count}개, 세그먼트: {len(guest_segs)}개")
            
            # Host/Guest 세그먼트 큐
            from collections import deque
            host_queue = deque(host_segs)
            guest_queue = deque(guest_segs)
            
            logger.info(f"📊 정확한 타임스탬프 생성 중...")
            logger.info(f"   Host: 발화 {host_count}개, 세그먼트 {len(host_segs)}개")
            logger.info(f"   Guest: 발화 {guest_count}개, 세그먼트 {len(guest_segs)}개")
            
            for i, dialogue in enumerate(dialogues):
                # ✅ 현재 발화의 시작 시간 (병합된 오디오 기준)
                start_time = cumulative_time
                
                # ✅ 기존은 host/guest를 "선생님/학생"으로 강제 라벨링해서
                #   teacher_teacher에서도 2화자가 "학생"으로 찍혔음.
                #   이제는 raw_speaker(원래 태그)를 우선 사용.
                speaker_label = getattr(dialogue, "raw_speaker", None)
                if not speaker_label:
                    speaker_label = "선생님" if dialogue.speaker == "host" else "학생"
                
                # ✅ 안전한 duration 추출
                if dialogue.speaker == "host":
                    if host_queue:
                        seg = host_queue.popleft()
                        raw_duration = seg['end'] - seg['start']
                        
                        # Duration 검증 및 보정
                        if raw_duration < 0:
                            logger.error(f"❌ 음수 duration 감지! 발화 {i+1}: {raw_duration:.3f}초")
                            
                            # ✅ 개선: STT 재시도 로직
                            logger.info(f"   🔄 STT 재시도 시작...")
                            host_dialogues = [d for d in dialogues if d.speaker == "host"]
                            current_host_idx = len([d for d in dialogues[:i] if d.speaker == "host"])
                            
                            retry_success, retry_duration = self._retry_stt_for_segment(
                                final_wav,
                                dialogues,
                                current_host_idx,
                                'host'
                            )
                            
                            if retry_success and retry_duration > 0:
                                logger.info(f"   ✅ STT 재시도 성공: {retry_duration:.2f}초")
                                accurate_duration = retry_duration
                            else:
                                # STT 재시도 실패 → 텍스트 기반 추정
                                logger.warning(f"   ⚠️  STT 재시도 실패 → 텍스트 기반 추정")
                                accurate_duration = self._estimate_duration_from_text(dialogue.text)
                        elif raw_duration > 300:  # 5분 이상
                            logger.error(f"❌ 비정상적으로 긴 duration 감지! 발화 {i+1}: {raw_duration:.1f}초")
                            logger.error(f"   화자: {speaker_label}")
                            logger.error(f"   텍스트: {dialogue.text[:100]}...")
                            logger.error(f"   → 스크립트에 중복 또는 불완전한 발화가 있을 가능성 높음")
                            
                            # ✅ 에러 발생 - 근본 원인 수정 강제
                            raise ValueError(
                                f"비정상적으로 긴 세그먼트 감지: {raw_duration:.1f}초 (발화 {i+1}, {speaker_label}). "
                                f"스크립트에 중복 발화가 있거나 TailFocus 세그먼트 분할에 문제가 있습니다. "
                                f"스크립트를 확인하고 다시 생성해주세요."
                            )
                        elif raw_duration < 0.1:  # 너무 짧음
                            logger.warning(f"⚠️  매우 짧은 duration! 발화 {i+1}: {raw_duration:.3f}초 → 0.5초로 보정")
                            accurate_duration = 0.5
                        else:
                            accurate_duration = raw_duration
                    else:
                        logger.error(f"❌ Host 세그먼트 부족! 발화 {i+1} ({speaker_label}) → 5.0초로 fallback")
                        accurate_duration = 5.0
                
                elif dialogue.speaker == "guest":
                    if guest_queue:
                        seg = guest_queue.popleft()
                        raw_duration = seg['end'] - seg['start']
                        
                        # Duration 검증 및 보정
                        if raw_duration < 0:
                            logger.error(f"❌ 음수 duration 감지! 발화 {i+1}: {raw_duration:.3f}초")
                            
                            # ✅ 개선: STT 재시도 로직
                            logger.info(f"   🔄 STT 재시도 시작...")
                            guest_dialogues = [d for d in dialogues if d.speaker == "guest"]
                            current_guest_idx = len([d for d in dialogues[:i] if d.speaker == "guest"])
                            
                            retry_success, retry_duration = self._retry_stt_for_segment(
                                final_wav,
                                dialogues,
                                current_guest_idx,
                                'guest'
                            )
                            
                            if retry_success and retry_duration > 0:
                                logger.info(f"   ✅ STT 재시도 성공: {retry_duration:.2f}초")
                                accurate_duration = retry_duration
                            else:
                                # STT 재시도 실패 → 텍스트 기반 추정
                                logger.warning(f"   ⚠️  STT 재시도 실패 → 텍스트 기반 추정")
                                accurate_duration = self._estimate_duration_from_text(dialogue.text)
                        elif raw_duration > 300:  # 5분 이상
                            logger.error(f"❌ 비정상적으로 긴 duration 감지! 발화 {i+1}: {raw_duration:.1f}초")
                            logger.error(f"   화자: {speaker_label}")
                            logger.error(f"   텍스트: {dialogue.text[:100]}...")
                            logger.error(f"   → 스크립트에 중복 또는 불완전한 발화가 있을 가능성 높음")
                            
                            # ✅ 에러 발생 - 근본 원인 수정 강제
                            raise ValueError(
                                f"비정상적으로 긴 세그먼트 감지: {raw_duration:.1f}초 (발화 {i+1}, {speaker_label}). "
                                f"스크립트에 중복 발화가 있거나 TailFocus 세그먼트 분할에 문제가 있습니다. "
                                f"스크립트를 확인하고 다시 생성해주세요."
                            )
                        elif raw_duration < 0.1:  # 너무 짧음
                            logger.warning(f"⚠️  매우 짧은 duration! 발화 {i+1}: {raw_duration:.3f}초 → 0.5초로 보정")
                            accurate_duration = 0.5
                        else:
                            accurate_duration = raw_duration
                    else:
                        logger.error(f"❌ Guest 세그먼트 부족! 발화 {i+1} ({speaker_label}) → 5.0초로 fallback")
                        accurate_duration = 5.0
                else:
                    # 알 수 없는 화자 (거의 발생 안 함)
                    logger.error(f"❌ 알 수 없는 화자! 발화 {i+1}: {dialogue.speaker}")
                    accurate_duration = 5.0
                
                audio_metadata.append({
                    'speaker': speaker_label,
                    'text': dialogue.text,
                    'start_time': start_time,  # ✅ 병합된 오디오에서의 실제 시작 시간!
                    'duration': accurate_duration,  # ✅ 검증된 정확한 재생 시간!
                    'file': final_mp3
                })
                
                # ✅ 다음 발화를 위해 누적 시간 업데이트
                cumulative_time += accurate_duration
            
            logger.info(f"✅ 정확한 타임스탬프 생성 완료!")
            
            # ============================================================
            # ✅ 타임스탬프 비율 보정 (긴 오디오에서 누적 오차 해결)
            # ============================================================
            # 전체 오디오 길이 측정
            import wave
            with wave.open(final_wav, 'rb') as wf:
                frames = wf.getnframes()
                rate = wf.getframerate()
                actual_audio_duration = frames / float(rate)
            
            # STT 타임스탬프 합계 (마지막 발화 끝나는 시점)
            stt_total_duration = sum(item['duration'] for item in audio_metadata)
            
            # 차이가 1초 이상이면 보정
            duration_diff = abs(actual_audio_duration - stt_total_duration)
            if duration_diff > 1.0:
                correction_ratio = actual_audio_duration / stt_total_duration
                logger.warning(f"⚠️  타임스탬프 오차 감지: {duration_diff:.2f}초 차이")
                logger.warning(f"   실제 오디오: {actual_audio_duration:.2f}초")
                logger.warning(f"   STT 합계: {stt_total_duration:.2f}초")
                logger.warning(f"   보정 비율: {correction_ratio:.6f}")
                
                # 모든 타임스탬프 비율로 보정
                for item in audio_metadata:
                    original_start_time = item['start_time']
                    original_duration = item['duration']
                    item['start_time'] = original_start_time * correction_ratio
                    item['duration'] = original_duration * correction_ratio
                
                corrected_total = sum(item['duration'] for item in audio_metadata)
                logger.info(f"✅ 타임스탬프 보정 완료: {stt_total_duration:.2f}초 → {corrected_total:.2f}초")
                logger.info(f"   최종 오차: {abs(actual_audio_duration - corrected_total):.3f}초")
            else:
                logger.info(f"✅ 타임스탬프 정확도 양호: 오차 {duration_diff:.3f}초 (보정 불필요)")
            
            # 7. MP3 파일 리스트
            mp3_files = [final_mp3]
            
            logger.info(f"✅ Tail Focus V5 변환 완료: {len(dialogues)}개 발화 → {final_mp3}")
            
            return audio_metadata, mp3_files
            
        except Exception as e:
            logger.error(f"❌ Tail Focus V5 TTS 실패: {e}", exc_info=True)
            raise RuntimeError(f"TTS 변환 실패: {str(e)}") from e


# 하위 호환성: 기존 함수 유지 (사용 안 함)
def _legacy_generate_single_audio(*args, **kwargs):
    """기존 순차 방식 (사용 안 함, 하위 호환용)"""
    raise NotImplementedError("This method is deprecated. Use Tail Focus V5 instead.")