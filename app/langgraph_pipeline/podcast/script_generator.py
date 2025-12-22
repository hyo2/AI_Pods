# app/langgraph_pipeline/podcast/script_generator.py

import json
import os
import re
import logging
from google.oauth2 import service_account
from vertexai.generative_models import GenerativeModel
import vertexai

# [Supabase] 프로젝트 구조에 맞춰 임포트
from app.services.supabase_service import supabase 
from .prompt_service import PromptTemplateService

logger = logging.getLogger(__name__)


def _extract_json_from_llm(text: str) -> dict:
    """
    LLM 출력에서 JSON만 안전하게 추출
    - ```json 코드블록 제거
    - 가장 바깥 {} 블록 추출
    """
    # 1. 코드블록 마크다운 제거 (```json, ```)
    cleaned = re.sub(r"```json|```", "", text, flags=re.IGNORECASE).strip()

    # 2. 가장 바깥쪽 중괄호 {} 찾기
    match = re.search(r"\{.*\}", cleaned, re.DOTALL)
    if not match:
        # JSON 블록을 못 찾았을 경우, 텍스트 전체가 JSON일 수도 있으니 시도
        try:
            return json.loads(cleaned)
        except:
            raise ValueError("LLM 출력에서 JSON 블록을 찾을 수 없습니다.")

    json_text = match.group().strip()
    return json.loads(json_text)


class ScriptGenerator:
    """LLM을 사용한 팟캐스트 스크립트 생성 (Supabase + Vertex AI)"""
    
    def __init__(self, project_id: str, region: str, sa_file: str, style: str = "explain"):
        self.project_id = project_id
        self.region = region
        self.sa_file = sa_file
        self.style = style
        
        # 초기화 실행
        self._init_vertex_ai()
        self._load_prompt_template()
    
    def _init_vertex_ai(self):
        """Vertex AI 초기화"""
        
        # [중요] 401 인증 오류 방지를 위한 환경 변수 강제 설정
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
            # Supabase 클라이언트를 전달하여 템플릿 조회
            template = PromptTemplateService.get_template(supabase, self.style)
            
            if template:
                self.system_prompt = template["system_prompt"]
                self.user_prompt_template = template["user_prompt_template"]
                logger.info(f"프롬프트 템플릿 로드 성공: {template['style_name']}")
            else:
                logger.warning(f"템플릿을 찾을 수 없어 기본 템플릿 사용: {self.style}")
                # 기본 템플릿 폴백
                default_template = PromptTemplateService.get_default_template(supabase)
                self.system_prompt = default_template["system_prompt"]
                self.user_prompt_template = default_template["user_prompt_template"]
                
        except Exception as e:
            logger.error(f"템플릿 로드 중 오류 발생: {e}")
            # 최후의 수단: 하드코딩 폴백
            self.system_prompt = "You are a teacher. Respond in Korean."
            self.user_prompt_template = "Create a dialogue in Korean:\n{combined_text}"

    def generate_script(
        self, 
        combined_text: str, 
        host_name: str, 
        guest_name: str,
        duration: int = 5,              # 기본값 5분
        difficulty: str = "intermediate", # 난이도 설정 (basic, intermediate, advanced)
        user_prompt: str = ""           # 사용자 추가 요청
    ) -> dict:
        """팟캐스트 스크립트 생성"""
        # 환경 변수에서 모델명 가져오기 (기본값: gemini-2.0-flash-exp)
        model_name = os.getenv("VERTEX_AI_MODEL_TEXT", "gemini-2.0-flash-exp")
        
        logger.info(f"모델 사용: {model_name} / 목표 시간: {duration}분 / 난이도: {difficulty}")
        
        # 시스템 프롬프트와 함께 모델 생성
        model = GenerativeModel(
            model_name,
            system_instruction=self.system_prompt 
        )
        
        # 프롬프트 생성 (시간 + 난이도 + 사용자 요청 포함)
        final_prompt = self._create_prompt(combined_text, host_name, guest_name, duration, difficulty, user_prompt)
        
        config = {
            "max_output_tokens": 8192,
            "temperature": 0.7,
        }
        
        try:
            logger.info("LLM 스크립트 생성 요청 중...")
            response = model.generate_content(final_prompt, generation_config=config)
            
            # [핵심 수정 부분] response.text 대신 Parts를 순회하며 텍스트 추출
            # 이유: Gemini가 긴 응답을 여러 Part로 나누어 보낼 때 response.text 접근 시 에러 발생
            raw_text = ""
            if response.candidates:
                candidate = response.candidates[0]
                if hasattr(candidate.content, 'parts'):
                    for part in candidate.content.parts:
                        if part.text:
                            raw_text += part.text
            
            if not raw_text:
                logger.error(f"모델 응답 텍스트 없음. 응답 객체: {response}")
                raise RuntimeError("모델이 빈 텍스트를 반환했습니다. (Safety Filter 가능성)")
            
            # JSON 파싱
            try:
                data = _extract_json_from_llm(raw_text)
                title = data.get("title", "제목 없음").strip()
                script_text = data.get("script", "").strip()
            except Exception as e:
                logger.error(f"JSON 파싱 실패. 원본 출력 미리보기:\n{raw_text[:500]}")

                # Fallback: JSON 실패 시 전체 텍스트를 스크립트로 간주
                title = "자동 생성된 팟캐스트"
                script_text = raw_text.strip()
                logger.warning("JSON 파싱 실패 → raw_text를 스크립트로 사용합니다.")

            # 스크립트 후처리
            script_text = self._clean_script(script_text)

            logger.info(f"제목 생성 완료: {title}")
            logger.info(f"스크립트 길이: {len(script_text)}자")

            return {
                "title": title,
                "script": script_text
            }
            
        except Exception as e:
            logger.error(f"스크립트 생성 오류: {e}", exc_info=True)
            raise RuntimeError(f"스크립트 생성 실패: {str(e)}") from e
    
    def _create_prompt(self, combined_text: str, host_name: str, guest_name: str, duration: int, difficulty: str, user_prompt: str = "") -> str:
        """템플릿을 사용해 프롬프트 생성"""
        
        # 1. 소스 텍스트 길이 제한 (6만자로 상향)
        max_text_length = 60000
        if len(combined_text) > max_text_length:
            logger.warning(f"텍스트가 너무 깁니다 ({len(combined_text)}자). {max_text_length}자로 제한합니다.")
            combined_text = combined_text[:max_text_length] + "\n\n[... truncated ...]"
        
        # 2. 시간(분) 기반 글자 수 계산
        chars_per_min = 700
        target_chars = duration * chars_per_min

        # 3. ✅ [NEW] 난이도별 지침 설정
        difficulty_map = {
            "basic": (
                "**[DIFFICULTY: BASIC / BEGINNER]**\n"
                "- Explain concepts as if talking to a middle school student.\n"
                "- Use simple analogies and avoid difficult jargon.\n"
                "- Focus on the 'What' and 'Why' rather than complex details."
            ),
            "intermediate": (
                "**[DIFFICULTY: INTERMEDIATE / COLLEGE LEVEL]**\n"
                "- Balance clear explanations with technical accuracy.\n"
                "- You can use technical terms but briefly explain them.\n"
                "- Focus on applying the concepts."
            ),
            "advanced": (
                "**[DIFFICULTY: ADVANCED / EXPERT]**\n"
                "- Speak like a professional in the field.\n"
                "- Dive deep into the nuances and technical details.\n"
                "- Assume the audience already knows the basics."
            )
        }
        # 기본값은 intermediate
        diff_instruction = difficulty_map.get(difficulty.lower(), difficulty_map["intermediate"])
        
        # 4. 지시사항 생성
        instruction_block = (
            f"First, generate a concise and engaging TITLE for this podcast.\n"
            f"Then, write a script suitable for a **{duration}-minute** session.\n"
            f"\n"
            f"{diff_instruction}\n"
            f"\n"
            f"OUTPUT FORMAT (IMPORTANT):\n"
            f"Respond strictly in valid JSON format as follows:\n"
            f"{{\n"
            f'  "title": "팟캐스트 제목",\n'
            f'  "script": "전체 팟캐스트 스크립트"\n'
            f"}}\n"
            f"\n"
            f"Target length: Approximately **{target_chars} Korean characters**.\n"
        )

        # 5. 사용자 추가 요청 반영
        if user_prompt and user_prompt.strip():
            instruction_block += f"\n - **USER SPECIAL REQUEST:** {user_prompt}\n"
        
        return self.user_prompt_template.format(
            combined_text=combined_text,
            host_name=host_name,
            guest_name=guest_name,
            length_instruction=instruction_block
        )
    
    def _clean_script(self, script_text: str) -> str:
        """스크립트 텍스트 정리"""
        # 코드블록 제거
        script_text = re.sub(
            r"```python|```json|```text|```|```markdown", 
            "", 
            script_text, 
            flags=re.IGNORECASE
        )
        # 이모지 등 4바이트 문자 제거 (DB 저장 오류 방지), 단 *나 #은 유지 (강조용)
        script_text = re.sub(r"[\U00010000-\U0010ffff]", "", script_text)
        
        # 과도한 줄바꿈 정리
        script_text = re.sub(r'\n{3,}', '\n\n', script_text)
        
        return script_text.strip()