# app/langgraph_pipeline/podcast/script_generator.py
import os
import re
import logging

from google.oauth2 import service_account
from vertexai.generative_models import GenerativeModel
import vertexai

from .script.parsing import extract_json_from_llm, extract_title_fallback
from .script.cleanup import clean_script
from .script.validation import is_script_truncated, measure
from .script.prompt_builder import create_prompt
from .script.options_parser import parse_user_prompt_overrides, apply_overrides
from .script.compression import compress_script_once
from .script.postprocess import hard_cap_fallback, continue_script_fallback, expand_script_fallback, expand_middle_content
from .script.structure_analyzer import analyze_script_structure
from .utils import target_char_budget
 
from app.services.supabase_service import supabase
from .prompt_service import PromptTemplateService
 
logger = logging.getLogger(__name__)

class ScriptGenerator:
    """LLM을 사용한 팟캐스트 스크립트 생성 (Supabase + Vertex AI)"""
   
    def __init__(self, project_id: str, region: str, sa_file: str, style: str = "explain"):
        self.project_id = project_id
        self.region = region
        self.sa_file = sa_file
        self.style = style
       
        self._init_vertex_ai()
        self._load_prompt_template()
   
    def _init_vertex_ai(self):
        """Vertex AI 초기화"""
        if self.sa_file and os.path.exists(self.sa_file):
            os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = self.sa_file
            logger.info(f"인증 파일 환경변수 설정 완료: {self.sa_file}")
 
        credentials = self._load_credentials()
       
        try:
            vertexai.init(
                project=self.project_id,
                location=self.region,
                credentials=credentials
            )
            logger.info(f"Vertex AI 초기화 완료: {self.project_id} / {self.region}")
        except Exception as e:
            logger.error(f"Vertex AI 초기화 실패: {e}")
            raise
   
    def _load_credentials(self):
        """서비스 계정 인증 정보 로드"""
        if os.path.exists(self.sa_file):
            try:
                return service_account.Credentials.from_service_account_file(self.sa_file)
            except Exception as e:
                raise RuntimeError(f"서비스 계정 파일 로드 오류: {e}")
        else:
            logger.warning(f"서비스 계정 파일을 찾을 수 없습니다: {self.sa_file}")
            return None
   
    def _load_prompt_template(self):
        """프롬프트 템플릿 로드 (Supabase 연동)"""
        try:
            template = PromptTemplateService.get_template(supabase, self.style)
           
            if template:
                self.system_prompt = template["system_prompt"]
                self.user_prompt_template = template["user_prompt_template"]
                logger.info(f"프롬프트 템플릿 로드 성공: {template['style_name']}")
            else:
                logger.warning(f"템플릿을 찾을 수 없어 기본 템플릿 사용: {self.style}")
                default_template = PromptTemplateService.get_default_template(supabase)
                self.system_prompt = default_template["system_prompt"]
                self.user_prompt_template = default_template["user_prompt_template"]
               
        except Exception as e:
            logger.error(f"템플릿 로드 중 오류 발생: {e}")
            self.system_prompt = "You are a teacher. Respond in Korean."
            self.user_prompt_template = "Create a dialogue in Korean:\n{combined_text}"
 
    def _extract_text_from_gemini_response(self, resp) -> str:
        """Gemini 응답에서 텍스트를 안전하게 추출"""
        if not resp or not getattr(resp, "candidates", None):
            return ""

        text = ""
        try:
            c = resp.candidates[0]
            if hasattr(c, "content") and hasattr(c.content, "parts"):
                for part in c.content.parts:
                    if getattr(part, "text", None):
                        text += part.text
        except Exception:
            return ""

        return text.strip()

    def generate_script(
        self,
        combined_text: str,
        host_name: str,
        guest_name: str,
        duration: int = 5,
        difficulty: str = "intermediate",
        user_prompt: str = ""
    ) -> dict:
        """팟캐스트 스크립트 생성"""
         # ---------------------------------------------------------------------------------
         # ✅ 안전장치: 입력 컨텍스트(강의 텍스트)가 비어있으면 스크립트 생성 금지
         # - OCR 비활성화 / 이미지 기반 PDF 등으로 실제 텍스트를 못 뽑았을 때
         # - LangSmith에서 [MAIN-PAGE ...] 마커만 있고 본문이 비는 케이스를 차단
         # ---------------------------------------------------------------------------------
        if not combined_text or not combined_text.strip():
             logger.error("[입력 텍스트 비정상] combined_text가 비어있거나 마커-only 입니다. OCR/추출 실패 가능.")
             raise ValueError(
                 "강의 텍스트(combined_text)가 비어 있어 스크립트를 생성할 수 없습니다. "
                 "이미지 기반 PDF(OCR 필요) 또는 텍스트 추출 실패 가능성이 큽니다."
             )
        
        # 페이지 마커만 있고 실제 본문이 없는 경우도 차단
         # 예: [MAIN-PAGE 1: Page 1]\n\n ... 반복
        marker_stripped = re.sub(r"\[(MAIN|SUPP\d+)-PAGE\s*\d+:[^\]]*\]", "", combined_text)
        marker_stripped = re.sub(r"===\s*\[[^\]]+\]\s*===.*?\n", "", marker_stripped)
        marker_stripped = re.sub(r"\s+", "", marker_stripped)
        if len(marker_stripped) < 30:
            logger.error("[입력 텍스트 비정상] combined_text가 비어있거나 마커-only 입니다. OCR/추출 실패 가능.")
            raise ValueError(
                "강의 텍스트가 페이지 마커만 존재하고 실제 본문이 거의 없습니다. "
                "OCR이 비활성화되어 있거나, PDF가 이미지 기반일 수 있습니다."
            )

        model_name = os.getenv("VERTEX_AI_MODEL_TEXT", "gemini-2.0-flash-exp")

       # ✅ user_prompt에서 override 추출 → 옵션보다 우선 적용
        duration_min = float(duration)
    
       # ✅ user_prompt에서 override 추출 → 옵션보다 우선 적용
        overrides = parse_user_prompt_overrides(user_prompt)
        duration_min, style_from_prompt, difficulty = apply_overrides(duration_min, self.style, difficulty, overrides)

        # style override가 들어오면, self.style도 이 호출에 한해 덮어쓰기(로컬 변수로)
        style = style_from_prompt or self.style

        # ✅ (추가) 대화형 여부는 style 결정 직후 확정해둔다 (UnboundLocalError 방지)
        is_dialogue = (style != "lecture")

        # ✅ float 분을 반영해 budget 계산 (반올림/상한/하한)
        budget = target_char_budget(duration_min, style)

        logger.info(
            f"[override 적용] duration_min={duration_min:.2f}, "
            f"budget={budget}, style={style}, difficulty={difficulty}"
        )
        
        logger.info(f"모델: {model_name} / 목표: {duration_min:.2f}분 ({budget}자) / 난이도: {difficulty} / 스타일: {style}")
       
        model = GenerativeModel(
            model_name,
            system_instruction=self.system_prompt
        )
       
        # ✅ budget을 그대로 전달
        final_prompt = create_prompt(
            combined_text=combined_text,
            host_name=host_name,
            guest_name=guest_name,
            duration=duration_min,
            difficulty=difficulty,
            user_prompt=user_prompt,
            budget=budget,
            style=style,
            user_prompt_template=self.user_prompt_template,
        )
       
        config = {
            "max_output_tokens": 8192,
            "temperature": 0.7,
        }
       
        try:
            logger.info("LLM 스크립트 생성 요청 중...")
            response = model.generate_content(final_prompt, generation_config=config)
           
            usage_metadata = response.usage_metadata
            input_tokens = usage_metadata.prompt_token_count
            output_tokens = usage_metadata.candidates_token_count
            total_tokens = usage_metadata.total_token_count
            
            input_cost = (input_tokens / 1_000_000) * 0.30
            output_cost = (output_tokens / 1_000_000) * 2.50
            total_cost = input_cost + output_cost
            
            logger.info(f"📊 [스크립트 생성] 토큰: {input_tokens:,} in / {output_tokens:,} out / {total_tokens:,} total")
            logger.info(f"💰 [스크립트 생성] 비용: ${total_cost:.6f}")

            # ✅ finish_reason 확인 추가
            raw_text = ""
            finish_reason = None
            if response.candidates:
                candidate = response.candidates[0]
                finish_reason = getattr(candidate, 'finish_reason', None)
                if hasattr(candidate.content, 'parts'):
                    for part in candidate.content.parts:
                        if part.text:
                            raw_text += part.text
           
            # ✅ finish_reason 로깅
            if finish_reason:
                logger.info(f"[LLM 완료 이유] {finish_reason}")
                if finish_reason != 1:  # 1 = STOP (정상 완료)
                    logger.warning(f"[비정상 종료] finish_reason={finish_reason} (1=STOP, 2=MAX_TOKENS, 3=SAFETY, 4=RECITATION)")
           
            if not raw_text:
                logger.error(f"모델 응답 텍스트 없음")
                raise RuntimeError("모델이 빈 텍스트를 반환했습니다")
           
            # ✅ 너무 짧은 출력 조기 감지
            # - micro duration(예: 30초)도 지원해야 하므로 budget 기반 최소 길이를 사용
            # - 기존 동작(큰 duration에서 500자 기준)을 유지하기 위해 상한을 500으로 둠
            min_raw_chars = min(500, max(120, int(budget * 0.6)))

            if len(raw_text.strip()) < min_raw_chars:
                logger.error(f"[출력 너무 짧음] {len(raw_text)}자 (최소 {min_raw_chars}자 필요) - 즉시 재시도")
                retry_resp = model.generate_content(
                    final_prompt,
                    generation_config={**config, "temperature": 0.3}
                )
                raw_text = self._extract_text_from_gemini_response(retry_resp)
                if len(raw_text.strip()) < min_raw_chars:
                    raise RuntimeError(
                        f"재시도 후에도 출력 너무 짧음: {len(raw_text)}자 (최소 {min_raw_chars}자 필요)"
                    )
           
            try:
                data = extract_json_from_llm(raw_text)
                title = data.get("title", "제목 없음").strip()
                script_text = data.get("script", "").strip()
            except Exception as e:
                logger.error(f"JSON 파싱 실패: {e}")
                logger.warning(f"raw_text 미리보기: {raw_text[:300]}...")
                extracted_title = extract_title_fallback(raw_text)
                title = extracted_title if extracted_title else "자동 생성된 팟캐스트"
                script_text = clean_script(raw_text.strip())
 
            script_text = clean_script(script_text)

            # ✅ 끊김 감지 + 재시도 1회
            is_trunc, reason = is_script_truncated(script_text)
            current_len = measure(script_text)
            
            # ✅ 조건 강화: 끊김 OR 너무 짧음(budget의 50% 미만)
            if is_trunc or current_len < int(budget * 0.5):
                if is_trunc:
                    logger.warning(f"[끊김 감지] {reason} → 재시도")
                else:
                    logger.warning(f"[너무 짧음] {current_len}자 < {int(budget*0.5)}자 → 재시도")
                
                # ✅ 재시도 시 temperature 낮추고 더 명확한 지시
                retry_config = {
                    "max_output_tokens": 8192,
                    "temperature": 0.2,  # 더 낮춤
                }
                
                retry_resp = model.generate_content(final_prompt, generation_config=retry_config)
                retry_raw = self._extract_text_from_gemini_response(retry_resp)
                
                # ✅ 재시도 결과도 너무 짧으면 에러
                if len(retry_raw.strip()) < min_raw_chars:
                    logger.error(f"[재시도 실패] 출력 여전히 너무 짧음: {len(retry_raw)}자 (최소 {min_raw_chars}자 필요)")
                    logger.warning("[재시도 실패] ... → 원본 유지하고 진행")
                
                try:
                    retry_data = extract_json_from_llm(retry_raw)
                    retry_script = clean_script(retry_data.get("script", "").strip())
                except Exception:
                    retry_script = clean_script(retry_raw.strip())

                is_trunc2, reason2 = is_script_truncated(retry_script)
                retry_len = measure(retry_script)
                
                # ✅ 재시도 성공 조건: 끊김 없음 AND 충분한 길이
                if (not is_trunc2) and retry_len >= int(budget * 0.5):
                    script_text = retry_script
                    logger.info(f"[재시도 성공] {retry_len}자")
                else:
                    logger.warning(f"[재시도 무효] reason2={reason2}, len={retry_len}")
                    # ✅ 재시도도 실패하면 에러 발생
                    if retry_len < int(budget * 0.5):
                        logger.warning("[재시도 후에도 짧음] ... → 원본 유지하고 진행")

            # ✅ 길이 검증 및 압축/보강
            max_ratio = 1.10  # 10% 여유
            min_ratio = 0.90  # 90% 하한
            strict_min_ratio = 0.85  # 85% - 심각한 부족 기준

            current = measure(script_text)
            min_chars = int(budget * min_ratio)
            strict_min_chars = int(budget * strict_min_ratio)

            logger.info(f"[길이검증] budget={budget}, current={current}, ratio={current/budget:.2f}")

            # ========================================
            # 보강 로직 (분량 부족 시)
            # ========================================
            if current < min_chars:
                logger.warning(f"[분량 부족 감지] {current}자 < {min_chars}자")
                
                # 1️⃣ 구조 분석
                structure = analyze_script_structure(script_text, is_dialogue)
                logger.info(
                    f"[구조 분석] quality={structure['structure_quality']}, "
                    f"본론비율={structure['main_content_ratio']:.1%}, "
                    f"완결={structure['is_complete']}"
                )
                
                # 2️⃣ 구조에 따른 전략 선택
                if structure['structure_quality'] == 'truncated':
                    # Case A: 끊김 → 이어쓰기
                    logger.info("[보강 전략] 스크립트 끊김 감지 → 이어쓰기")
                    script_text = continue_script_fallback(
                        script_text=script_text,
                        budget=budget,
                        model=model,
                        style=style,
                        extract_text_fn=self._extract_text_from_gemini_response,
                    )
                    script_text = clean_script(script_text)
                    current = measure(script_text)
                    logger.info(f"[보강 후] {current}자, ratio={current/budget:.2f}")
                    
                elif structure['structure_quality'] == 'incomplete':
                    # Case B: 마무리 없음 → 이어쓰기
                    logger.info("[보강 전략] 마무리 없음 → 이어쓰기")
                    script_text = continue_script_fallback(
                        script_text=script_text,
                        budget=budget,
                        model=model,
                        style=style,
                        extract_text_fn=self._extract_text_from_gemini_response,
                    )
                    script_text = clean_script(script_text)
                    current = measure(script_text)
                    logger.info(f"[보강 후] {current}자, ratio={current/budget:.2f}")
                    
                elif structure['structure_quality'] == 'needs_expansion':
                    # Case C: 완결되었지만 본론 빈약 → 중간 확장
                    logger.info("[보강 전략] 본론 빈약 → 중간 내용 확장")
                    script_text = expand_middle_content(
                        script_text=script_text,
                        budget=budget,
                        current_len=current,
                        structure=structure,
                        model=model,
                        style=style,
                        extract_text_fn=self._extract_text_from_gemini_response,
                    )
                    script_text = clean_script(script_text)
                    current = measure(script_text)
                    logger.info(f"[보강 후] {current}자, ratio={current/budget:.2f}")
                    
                elif structure['structure_quality'] == 'good':
                    # Case D: 구조 양호하지만 짧음
                    if structure['main_content_ratio'] >= 0.7:
                        # 본론 비율이 70% 이상이면 품질 우선
                        logger.info(
                            f"[보강 스킵] 구조 양호(본론 {structure['main_content_ratio']:.1%}) - "
                            f"품질 우선으로 현재 길이 유지"
                        )
                    else:
                        # 그래도 본론이 부족하면 중간 확장 시도
                        logger.info("[보강 전략] 구조는 양호하나 본론 부족 → 중간 확장")
                        script_text = expand_middle_content(
                            script_text=script_text,
                            budget=budget,
                            current_len=current,
                            structure=structure,
                            model=model,
                            style=style,
                            extract_text_fn=self._extract_text_from_gemini_response,
                        )
                        script_text = clean_script(script_text)
                        current = measure(script_text)
                        logger.info(f"[보강 후] {current}자, ratio={current/budget:.2f}")
                
                # 3️⃣ 보강 후에도 여전히 부족한 경우 추가 시도
                current = measure(script_text)
                if current < min_chars:
                    logger.warning(f"[1차 보강 후에도 부족] {current}자 < {min_chars}자 → 2차 시도")
                    
                    # 구조 재분석
                    structure2 = analyze_script_structure(script_text, is_dialogue)
                    
                    if structure2['structure_quality'] in ['truncated', 'incomplete']:
                        # 여전히 불완전하면 이어쓰기
                        script_text = continue_script_fallback(
                            script_text=script_text,
                            budget=budget,
                            model=model,
                            style=style,
                            extract_text_fn=self._extract_text_from_gemini_response,
                        )
                    else:
                        # 완결되었으면 강제 확장
                        script_text = expand_script_fallback(
                            script_text=script_text,
                            budget=budget,
                            min_chars=min_chars,
                            model=model,
                            style=style,
                            extract_text_fn=self._extract_text_from_gemini_response,
                        )
                    
                    script_text = clean_script(script_text)
                    current = measure(script_text)
                    logger.info(f"[2차 보강 후] {current}자, ratio={current/budget:.2f}")
            
            # 4️⃣ 최종 분량 체크
            current = measure(script_text)
            if current < strict_min_chars:
                # 85% 미만은 심각
                logger.error(
                    f"[심각한 분량 부족] {current}자 < {strict_min_chars}자 (목표의 85% 미만)"
                )
                # 구조가 좋으면 경고만, 나쁘면 실패 처리 고려
                final_structure = analyze_script_structure(script_text, is_dialogue)
                if final_structure['structure_quality'] != 'good':
                    logger.warning("[품질+분량 모두 미달] 하지만 생성 계속 진행")
            elif current < min_chars:
                # 85~90%는 경고
                logger.warning(
                    f"[분량 부족] {current}자 < {min_chars}자 (목표의 90% 미만) - 생성 계속"
                )

            # ========================================
            # 압축 로직 (분량 초과 시)
            # ========================================
            max_compress_rounds = 3

            for round_idx in range(max_compress_rounds):
                current = measure(script_text)
                if current <= int(budget * max_ratio):
                    break

                logger.warning(f"[압축 {round_idx+1}회] current={current} > {int(budget*max_ratio)}")

                original_script = script_text
                compressed = compress_script_once(
                    model=model,
                    extract_text_fn=self._extract_text_from_gemini_response,
                    script_text=script_text,
                    budget=budget,
                    is_dialogue=is_dialogue,
                    round_idx=round_idx,
                )
                compressed = clean_script(compressed)
                compressed_current = measure(compressed)

                logger.info(f"[압축 결과] {compressed_current}자, ratio={compressed_current/budget:.2f}")

                # ✅ 압축 결과 완결성 검증 (대화형만)
                if is_dialogue:
                    is_incomplete, incomplete_reason = is_script_truncated(compressed)
                    if is_incomplete:
                        logger.warning(f"[압축 결과 불완전] {incomplete_reason} → 원본 유지")
                        script_text = original_script
                        continue  # 다음 라운드 시도

                # 너무 짧아진 경우
                if compressed_current < min_chars:
                    logger.warning(f"[압축 과다] {compressed_current} < {int(budget*min_ratio)}")
                    
                    if is_dialogue and round_idx < max_compress_rounds - 1:
                        script_text = original_script
                        continue
                    else:
                        script_text = original_script
                        break
                else:
                    script_text = compressed

            # ✅ 최종 확인: 여전히 너무 길면 하드 캡 적용
            final_current = measure(script_text)
            if final_current > int(budget * max_ratio):
                logger.warning(f"[하드캡 트리거] {final_current} > {int(budget*max_ratio)}")
                script_text = hard_cap_fallback(
                    script_text=script_text,
                    budget=budget,
                    model=model,
                    style=style,
                    extract_text_fn=self._extract_text_from_gemini_response,
                )
                final_current = measure(script_text)
            
            # ✅ 최종 완결성 검증 (대화형)
            if is_dialogue:
                is_final_incomplete, final_reason = is_script_truncated(script_text)
                if is_final_incomplete:
                    logger.warning(f"[최종 스크립트 불완전] {final_reason} → 이어쓰기 폴백 시도")

                    # 1) 먼저 이어쓰기(추가분 생성)로 완결 시도
                    continued = continue_script_fallback(
                        script_text=script_text,
                        budget=budget,
                        model=model,
                        style=style,
                        extract_text_fn=self._extract_text_from_gemini_response,
                    )
                    continued = clean_script(continued)

                    is_after_cont, reason_after = is_script_truncated(continued)
                    if not is_after_cont:
                        script_text = continued
                        logger.info("[이어쓰기 성공] 최종 스크립트 완결 처리")
                    else:
                        logger.warning(f"[이어쓰기 실패] {reason_after} → 하드캡 적용")
                        script_text = hard_cap_fallback(
                            script_text=script_text,
                            budget=budget,
                            model=model,
                            style=style,
                            extract_text_fn=self._extract_text_from_gemini_response,
                        )

            final_current = measure(script_text)
            logger.info(f"[최종] {final_current}자, ratio={final_current/budget:.2f}")
            logger.info(f"제목: {title}")
 
            return {
                "title": title,
                "script": script_text,
                "usage": {
                    "script_generation": {
                        "input_tokens": input_tokens,
                        "output_tokens": output_tokens,
                        "total_tokens": total_tokens,
                        "cost_usd": total_cost
                    }
                }
            }
           
        except Exception as e:
            logger.error(f"스크립트 생성 오류: {e}", exc_info=True)
            raise RuntimeError(f"스크립트 생성 실패: {str(e)}") from e
   
    