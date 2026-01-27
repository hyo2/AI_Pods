import json
import re
import logging 
logger = logging.getLogger(__name__)

def extract_json_from_llm(text: str) -> dict:
    """
    LLM 출력에서 JSON만 안전하게 추출
    - 코드블록 제거
    - 제어 문자 제거
    - 이중 JSON 구조 방지
    """
    # 0) 모델이 종종 ```json ... ``` 또는 설명문 + JSON 형태로 주므로,
    #    최대한 "망가진 JSON"도 복구해서 파싱 성공률을 올린다.

    # 1) 코드블록 마크다운 제거 (```json / ``` 등)
    cleaned = re.sub(r"```(?:json|JSON)?", "", text, flags=re.IGNORECASE)
    cleaned = cleaned.replace("```", "").strip()
    
    # ✅ 1.5) 제어 문자 제거 (0x00-0x1F, 0x7F-0x9F) - "Invalid control character" 에러 방지
    cleaned = re.sub(r'[\x00-\x1f\x7f-\x9f]', '', cleaned)

    # 2) 가장 바깥쪽 중괄호 블록 추출: 첫 '{' ~ 마지막 '}'
    #    (기존처럼 정규식 {.*}는 텍스트가 섞이면 실패/과매칭 위험이 있어 인덱스로 처리)
    first = cleaned.find("{")
    last = cleaned.rfind("}")

    # ✅ 추가: JSON이 잘린 경우 복구 시도
    if first != -1 and (last == -1 or last <= first):
        logger.warning("[JSON 복구 시도] 닫는 괄호 누락 - 강제 추가")
        truncated = cleaned[first:].rstrip().rstrip(',')
        json_text = truncated + "\n}"
        
        try:
            recovered = json.loads(json_text)
            
            # ✅ 복구 성공 시 검증: script가 너무 짧거나 중간에 끊긴 것 같으면 실패 처리
            script_content = recovered.get('script', '')
            
            # 1) script가 너무 짧음 (200자 미만)
            if len(script_content) < 200:
                logger.warning(f"[JSON 복구 실패] script가 너무 짧음: {len(script_content)}자")
                raise ValueError("Recovered script too short")
            
            # 2) 마지막 문장이 비정상적으로 끊김 (한글 단어 중간에서 끊김)
            last_line = script_content.strip().split('\n')[-1]
            if last_line and not last_line[-1] in '.!?다요죠':
                logger.warning(f"[JSON 복구 실패] script 마지막이 비정상: '{last_line[-30:]}'")
                raise ValueError("Recovered script appears truncated")
            
            logger.info("[JSON 복구 성공] 검증 통과")
            return recovered
            
        except Exception as e:
            logger.warning(f"[JSON 복구 실패] {e}")
            pass  # 기존 로직으로 fallback

    if first == -1 or last == -1 or last <= first:
        # 그래도 없으면 전체를 그대로 json.loads 시도
        try:
            return json.loads(cleaned)
        except Exception as e:
            raise ValueError("LLM 출력에서 JSON 블록을 찾을 수 없습니다.") from e

    json_text = cleaned[first:last + 1].strip()

    # 3) 1차 파싱
    try:
        return json.loads(json_text)
    except json.JSONDecodeError as e:
        logger.warning(f"JSON 파싱 1차 실패: {e}")

        # 4) 2차 복구 파싱:
        # - JSON 문자열 내부에 실제 개행이 들어가거나(불법), \n 이스케이프가 섞이는 경우가 있음
        # - 최소한 script/title 키를 살릴 수 있게 보수적으로 복구
        repaired = json_text
        
        # ✅ 제어 문자 추가 제거 (혹시 모를 경우 대비)
        repaired = re.sub(r'[\x00-\x1f\x7f-\x9f]', '', repaired)
        
        repaired = repaired.replace("\\r\\n", "\\n")
        repaired = repaired.replace("\\r", "\\n")
        # 문자열 내부에 들어간 실제 개행을 \n 로 바꾸는 시도(완전한 처리는 아니지만 성공률 상승)
        repaired = re.sub(r'"\s*\n\s*"', '"\\n"', repaired)
        
        # ✅ 추가: 쉼표 문제 복구 - "Expecting ',' delimiter" 에러 방지
        # 패턴: "..." "..." → "...", "..."
        repaired = re.sub(r'"\s+(")', r'", \1', repaired)

        # 가장 흔한 케이스: 따옴표 이스케이프가 과하게 들어간 경우
        repaired2 = repaired.replace('\\"', '"')

        for candidate in (repaired, repaired2):
            try:
                data = json.loads(candidate)
                # ✅ 이중 JSON 구조 감지 및 수정 시도
                if isinstance(data.get('script'), str) and data['script'].lstrip().startswith('{'):
                    try:
                        logger.warning("이중 JSON 구조 감지 - script 필드 재파싱 시도")
                        data['script'] = json.loads(data['script'])
                    except Exception:
                        pass
                return data
            except Exception:
                continue

        raise ValueError(f"JSON 파싱 실패: {e}")
 
def extract_title_fallback(text: str) -> str | None:
    """JSON 파싱 실패 시 title만 정규식으로 추출"""
    match = re.search(r'"title"\s*:\s*"([^"]+)"', text)
    if match:
        return match.group(1).strip()
    return None