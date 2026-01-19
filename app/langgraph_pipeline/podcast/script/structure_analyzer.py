# app/langgraph_pipeline/podcast/script/structure_analyzer.py
import re
import logging
from typing import Dict, List
from .validation import is_script_truncated

logger = logging.getLogger(__name__)

def analyze_script_structure(script_text: str, is_dialogue: bool) -> Dict:
    """
    스크립트의 구조를 분석하여 보강 전략 결정에 활용
    
    Returns:
        {
            'is_complete': bool,           # 완결 여부
            'has_closing': bool,           # 마무리 인사 있는지
            'closing_start_idx': int,      # 마무리 시작 지점 (라인 인덱스)
            'main_content_ratio': float,   # 본론 비율
            'structure_quality': str       # 'good', 'needs_expansion', 'truncated', 'incomplete'
        }
    """
    if not script_text or not script_text.strip():
        return {
            'is_complete': False,
            'has_closing': False,
            'closing_start_idx': 0,
            'main_content_ratio': 0.0,
            'structure_quality': 'truncated',
            'total_lines': 0
        }
    
    lines = [l.strip() for l in script_text.strip().split('\n') if l.strip()]
    
    # 마무리 키워드 패턴
    closing_keywords = [
        r'감사합니다', r'수고하셨습니다', r'다음\s*시간',
        r'여기서\s*마치', r'안녕', r'마무리', r'이만\s*마무리',
        r'다음.*?뵙겠습니다', r'건강하게.*?지내세요'
    ]
    
    # 역순으로 마무리 구간 찾기 (마지막 10줄 내에서)
    closing_start_idx = len(lines)
    has_closing = False
    
    search_range = max(0, len(lines) - 10)
    for i in range(len(lines) - 1, search_range - 1, -1):
        line = lines[i]
        if any(re.search(kw, line) for kw in closing_keywords):
            closing_start_idx = i
            has_closing = True
            break
    
    # 끊김 확인
    is_truncated, reason = is_script_truncated(script_text)
    
    # 본론 비율 계산
    if has_closing and closing_start_idx > 0:
        main_content_ratio = closing_start_idx / len(lines)
    else:
        main_content_ratio = 1.0 if not has_closing else 0.0
    
    # 구조 품질 판단
    if is_truncated:
        structure_quality = 'truncated'
    elif has_closing and main_content_ratio >= 0.7:
        # 본론이 70% 이상이면 구조 양호
        structure_quality = 'good'
    elif has_closing and main_content_ratio < 0.7:
        # 마무리는 있지만 본론이 빈약 (전체의 70% 미만)
        structure_quality = 'needs_expansion'
    else:
        # 마무리 없음
        structure_quality = 'incomplete'
    
    result = {
        'is_complete': has_closing and not is_truncated,
        'has_closing': has_closing,
        'closing_start_idx': closing_start_idx,
        'main_content_ratio': main_content_ratio,
        'structure_quality': structure_quality,
        'total_lines': len(lines)
    }
    
    logger.debug(f"[구조 분석 결과] {result}")
    return result