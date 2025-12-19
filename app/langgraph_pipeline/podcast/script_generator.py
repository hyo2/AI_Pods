# app/langgraph_pipeline/podcast/script_generator.py

import json
import os
import re
import logging
from google.oauth2 import service_account
from vertexai.generative_models import GenerativeModel
import vertexai

# [Supabase] 프로젝트의 Supabase 서비스 파일 경로에 맞춰 수정하세요.
from app.services.supabase_service import supabase 
from .prompt_service import PromptTemplateService

logger = logging.getLogger(__name__)


def _extract_json_from_llm(text: str) -> dict:
    """
    LLM 출력에서 JSON만 안전하게 추출
    - ```json 코드블록 제거
    - 가장 바깥 {} 블록 추출
    """
    # 코드블록 제거
    cleaned = re.sub(r"```json|```", "", text, flags=re.IGNORECASE).strip()

    # 가장 바깥 JSON 블록 찾기
    match = re.search(r"\{.*\}", cleaned, re.DOTALL)
    if not match:
        raise ValueError("LLM 출력에서 JSON 블록을 찾을 수 없음")

    json_text = match.group().strip()

    # 🔥 추가: 개행 강제 escape
    json_text = json_text.replace("\n", "\\n")
    
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
        
        vertexai.init(
            project=self.project_id, 
            location=self.region, 
            credentials=credentials
        )
        logger.info(f"Vertex AI 초기화 완료: {self.project_id} / {self.region}")
    
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
        duration: int = 5,           # 기본값 5분
        user_prompt: str = ""        # 사용자 추가 요청
    ) -> str:
        """팟캐스트 스크립트 생성"""
        # 환경 변수에서 모델명 가져오기
        model_name = os.getenv("VERTEX_AI_MODEL_TEXT", "gemini-2.0-flash-exp")
        
        logger.info(f"모델 사용: {model_name} / 목표 시간: {duration}분")
        
        # 시스템 프롬프트와 함께 모델 생성
        model = GenerativeModel(
            model_name,
            system_instruction=self.system_prompt 
        )
        
        # 프롬프트 생성 (시간 + 사용자 요청 + 주/보조 소스 지침 포함)
        final_prompt = self._create_prompt(combined_text, host_name, guest_name, duration, user_prompt)
        
        config = {
            "max_output_tokens": 8192,
            "temperature": 0.7,
        }
        
        try:
            logger.info("LLM 스크립트 생성 요청 중...")
            response = model.generate_content(final_prompt, generation_config=config)
            raw_text = getattr(response, "text", "")
            
            if not raw_text:
                raise RuntimeError("모델이 텍스트를 반환하지 않았습니다")
            
            
            # JSON 파싱
            try:
                data = _extract_json_from_llm(raw_text)
                title = data["title"].strip()
                script_text = data["script"].strip()
            except Exception as e:
                logger.error(f"JSON 파싱 실패. 원본 출력 미리보기:\n{raw_text[:500]}")

                # 🔥 fallback: JSON 실패 시 생성 title, 스크립트라도 살림
                title_match = re.search(r'"title"\s*:\s*"([^"]+)"', raw_text)
                title = title_match.group(1) if title_match else "새 팟캐스트"
                script_text = raw_text.strip()

                logger.warning("JSON 파싱 실패 → raw_text를 스크립트로 사용합니다.")


            # 스크립트 후처리
            script_text = self._clean_script(script_text)

            logger.info(f"제목 생성 완료: {title}")
            logger.info(f"스크립트 길이: {len(script_text)}자")

            logger.info(f"스크립트 생성 완료 (스타일: {self.style}, 길이: {len(script_text)}자)")

            return {
                "title": title,
                "script": script_text.strip()
            }
            
        except Exception as e:
            logger.error(f"스크립트 생성 오류: {e}", exc_info=True)
            raise RuntimeError(f"스크립트 생성 실패: {str(e)}") from e
    
    def _create_prompt(self, combined_text: str, host_name: str, guest_name: str, duration: int, user_prompt: str = "") -> str:
        """템플릿을 사용해 프롬프트 생성"""
        
        # 1. 소스 텍스트 길이 제한 (6만자로 상향)
        max_text_length = 60000
        if len(combined_text) > max_text_length:
            logger.warning(f"텍스트가 너무 깁니다 ({len(combined_text)}자). {max_text_length}자로 제한합니다.")
            combined_text = combined_text[:max_text_length] + "\n\n[... truncated ...]"
        
        # 2. 시간(분) 기반 글자 수 계산
        chars_per_min = 500
        target_chars = duration * chars_per_min
        
        # 3. [핵심 수정] 지시사항 생성 (주/보조 소스 처리 방법 포함)
        instruction_block = (
            f"First, generate a concise and engaging TITLE for this podcast.\n"
            f"Then, write a script suitable for a **{duration}-minute conversation/lecture**.\n"
            f"\n"
            f"OUTPUT FORMAT (IMPORTANT):\n"
            f"Respond strictly in valid JSON format as follows:\n"
            f"{{\n"
            f'  "title": "팟캐스트 제목",\n'
            f'  "script": "전체 팟캐스트 스크립트"\n'
            f"}}\n"
            f"\n"
            f"IMPORTANT RULES:\n"
            f"- Output ONLY valid JSON.\n"
            f"- Do NOT include explanations, markdown, or code blocks.\n"
            f"- Do NOT include any text before or after the JSON.\n"
            f"Script requirements:\n"
            f"   - Target length: Approximately **{target_chars} Korean characters**.\n"
            f"   - **Source Handling Instructions:**\n"
            f"     The text below is divided into '[MAIN SOURCE]' and '[AUXILIARY SOURCE]'.\n"
            f"     1. **[MAIN SOURCE]:** This is the CORE topic. Dedicate 80-90% of the script to explaining this content.\n"
            f"     2. **[AUXILIARY SOURCE]:** Use this ONLY for supporting details, definitions, examples, or context. Do not make it the main topic.\n"
        )

        # 4. 사용자 추가 요청 반영
        if user_prompt and user_prompt.strip():
            instruction_block += f"\n   - **USER SPECIAL REQUEST:** {user_prompt}\n"
            instruction_block += f"   (Please reflect the user's request above explicitly in the script tone or content.)"
        
        return self.user_prompt_template.format(
            combined_text=combined_text,
            host_name=host_name,
            guest_name=guest_name,
            length_instruction=instruction_block
        )
    
    def _clean_script(self, script_text: str) -> str:
        """스크립트 텍스트 정리"""
        script_text = re.sub(
            r"```python|```json|```text|```|```markdown", 
            "", 
            script_text, 
            flags=re.IGNORECASE
        )
        script_text = re.sub(r"[\*\U00010000-\U0010ffff]|#", "", script_text)
        script_text = re.sub(r'\n{3,}', '\n\n', script_text)
        return script_text.strip()