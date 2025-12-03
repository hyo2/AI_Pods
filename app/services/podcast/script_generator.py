# app/services/podcast/script_generator.py
import os
import re
import logging
from google.oauth2 import service_account
from vertexai.generative_models import GenerativeModel
import vertexai

from .prompt_service import PromptTemplateService

logger = logging.getLogger(__name__)


class ScriptGenerator:
    """LLM을 사용한 팟캐스트 스크립트 생성"""
    
    def __init__(self, project_id: str, region: str, sa_file: str, style: str = "explain"):
        self.project_id = project_id
        self.region = region
        self.sa_file = sa_file
        self.style = style
        self._init_vertex_ai()
        self._load_prompt_template()
    
    def _init_vertex_ai(self):
        """Vertex AI 초기화"""
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
        """프롬프트 템플릿 로드"""
        template = PromptTemplateService.get_template(self.style)
        
        if template:
            self.system_prompt = template["system_prompt"]
            self.user_prompt_template = template["user_prompt_template"]
            logger.info(f"프롬프트 템플릿 로드: {template['style_name']}")
        else:
            logger.warning(f"템플릿을 찾을 수 없어 기본 템플릿 사용: {self.style}")
            default_template = PromptTemplateService.get_default_template()
            self.system_prompt = default_template["system_prompt"]
            self.user_prompt_template = default_template["user_prompt_template"]
    
    def generate_script(
        self, 
        combined_text: str, 
        host_name: str, 
        guest_name: str
    ) -> str:
        """팟캐스트 스크립트 생성"""
        model_name = os.getenv("VERTEX_AI_MODEL_TEXT", "gemini-2.0-flash-exp")
        
        logger.info(f"모델 사용: {model_name}")
        
        # 시스템 프롬프트와 함께 모델 초기화
        model = GenerativeModel(
            model_name,
            system_instruction=self.system_prompt  # 여기서 시스템 프롬프트 설정
        )
        
        # 사용자 프롬프트 생성
        user_prompt = self._create_prompt(combined_text, host_name, guest_name)
        
        # GenerationConfig에는 system_instruction을 포함하지 않음
        config = {
            "max_output_tokens": 8192,
            "temperature": 0.7,
        }
        
        try:
            logger.info("LLM 스크립트 생성 요청 중...")
            response = model.generate_content(user_prompt, generation_config=config)
            script_text = getattr(response, "text", "")
            
            if not script_text:
                raise RuntimeError("모델이 텍스트를 반환하지 않았습니다")
            
            # 스크립트 정리
            script_text = self._clean_script(script_text)
            
            logger.info(f"스크립트 생성 완료 (스타일: {self.style}, 길이: {len(script_text)}자)")
            
            return script_text.strip()
            
        except Exception as e:
            logger.error(f"스크립트 생성 오류: {e}", exc_info=True)
            raise RuntimeError(f"스크립트 생성 실패: {str(e)}") from e
    
    def _create_prompt(self, combined_text: str, host_name: str, guest_name: str) -> str:
        """템플릿을 사용해 프롬프트 생성"""
        # 텍스트 길이 제한 (너무 길면 잘라냄)
        max_text_length = 50000
        if len(combined_text) > max_text_length:
            logger.warning(f"텍스트가 너무 깁니다 ({len(combined_text)}자). {max_text_length}자로 제한합니다.")
            combined_text = combined_text[:max_text_length] + "\n\n[... 텍스트가 너무 길어 일부만 포함되었습니다 ...]"
        
        return self.user_prompt_template.format(
            combined_text=combined_text,
            host_name=host_name,
            guest_name=guest_name
        )
    
    def _clean_script(self, script_text: str) -> str:
        """스크립트 텍스트 정리"""
        # 코드 블록 마커 제거
        script_text = re.sub(
            r"```python|```json|```text|```|```markdown", 
            "", 
            script_text, 
            flags=re.IGNORECASE
        )
        
        # 특수 문자 제거 (이모지 등)
        script_text = re.sub(r"[\*\U00010000-\U0010ffff]|#", "", script_text)
        
        # 연속된 공백 정리
        script_text = re.sub(r'\n{3,}', '\n\n', script_text)
        
        return script_text.strip()