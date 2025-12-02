# app/services/podcast/script_generator.py
import os
import re
import logging
from google.oauth2 import service_account
from vertexai.generative_models import GenerativeModel
import vertexai

logger = logging.getLogger(__name__)


class ScriptGenerator:
    """LLM을 사용한 팟캐스트 스크립트 생성"""
    
    def __init__(self, project_id: str, region: str, sa_file: str):
        self.project_id = project_id
        self.region = region
        self.sa_file = sa_file
        self._init_vertex_ai()
    
    def _init_vertex_ai(self):
        """Vertex AI 초기화"""
        credentials = self._load_credentials()
        vertexai.init(
            project=self.project_id, 
            location=self.region, 
            credentials=credentials
        )
    
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
    
    def generate_script(
        self, 
        combined_text: str, 
        host_name: str, 
        guest_name: str
    ) -> str:
        """팟캐스트 스크립트 생성"""
        model_name = os.getenv("VERTEX_AI_MODEL_TEXT", "gemini-2.5-flash")
        model = GenerativeModel(model_name)
        
        prompt = self._create_prompt(combined_text, host_name, guest_name)
        
        config = {
            "max_output_tokens": 8192,
            "temperature": 0.7,
        }
        
        try:
            response = model.generate_content(prompt, generation_config=config)
            script_text = getattr(response, "text", "")
            
            if not script_text:
                raise RuntimeError("모델이 텍스트를 반환하지 않았습니다")
            
            # 스크립트 정리
            script_text = self._clean_script(script_text)
            
            logger.info(f"스크립트 생성 완료 (길이: {len(script_text)}자)")
            
            return script_text.strip()
            
        except Exception as e:
            logger.error(f"스크립트 생성 오류: {e}")
            raise
    
    def _create_prompt(self, combined_text: str, host_name: str, guest_name: str) -> str:
        """LLM 프롬프트 생성"""
        return f"""
당신은 청취자를 사로잡는 전문적인 팟캐스트 스크립트 작가입니다.
아래 텍스트를 분석하여 두 명의 화자(진행자, 게스트)가 대화하는 형식의 팟캐스트 스크립트를 한국어로 작성해 주세요.

**[중요: 화자 태그 규칙]**
- 화자를 구분할 때는 반드시 "[진행자]"와 "[게스트]" 태그만 사용하세요.
- 절대로 "[박지우]", "[이하은]" 같은 이름 태그를 사용하지 마세요.
- 대화 내용 안에서 이름을 언급할 때만 "{host_name}", "{guest_name}"을 사용하세요.

**올바른 예시:**
[진행자] 안녕하세요, 저는 진행자 {host_name}입니다!
[게스트] 안녕하세요, {guest_name}입니다.
[진행자] {guest_name} 님, 오늘 주제가 흥미롭네요.

**잘못된 예시 (절대 금지):**
[{host_name}] 안녕하세요!
[박지우] 안녕하세요!

**[필수 지침: 인간적인 대화를 위한 구성]**
1. **톤 앤 매너:** 편안하고, 친근하며, 청취자와 눈높이를 맞추는 대화체로 작성해 주세요.
2. **흐름:** 자연스러운 대화의 흐름을 위해 추임새나 감탄사를 적절히 사용해 주세요.
3. **구조:** 도입부, 본론, 마무리의 세 부분으로 명확하게 구분되어야 합니다.
4. **화자 역할:**
   - **[진행자]:** 청취자를 대표하여 질문하고 대화를 이끕니다. (이름: {host_name})
   - **[게스트]:** 전문가적인 지식을 전달합니다. (이름: {guest_name})

원본 텍스트:
---
{combined_text}
---
"""
    
    def _clean_script(self, script_text: str) -> str:
        """스크립트 텍스트 정리"""
        # 코드 블록 마커 제거
        script_text = re.sub(
            r"```python|```json|```text|```|```markdown", 
            "", 
            script_text, 
            flags=re.IGNORECASE
        )
        
        # 특수 문자 제거
        script_text = re.sub(r"[\*\U00010000-\U0010ffff]|#", "", script_text)
        
        return script_text