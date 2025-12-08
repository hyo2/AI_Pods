"""스크립트 파서 (이미지 생성을 위한 토픽 추출)"""
import logging
import re
from typing import List, Dict, Any

logger = logging.getLogger(__name__)


class ScriptParser:
    """스크립트를 분석하여 이미지 생성용 프롬프트 추출"""

    def __init__(self):
        """파서 초기화"""
        pass

    def extract_topics(self, script: str) -> List[Dict[str, Any]]:
        """
        스크립트에서 주요 토픽 추출
        
        Args:
            script: 팟캐스트 스크립트
        
        Returns:
            토픽 리스트
        """
        topics = []
        
        # 마크다운 헤더 찾기
        headers = re.findall(r'^#{1,3}\s+(.+)$', script, re.MULTILINE)
        
        for i, header in enumerate(headers):
            topics.append({
                "id": f"topic_{i}",
                "title": header.strip(),
                "timestamp": f"00:{i*2:02d}:00",
                "order": i
            })
        
        # 헤더가 없으면 단락으로 나누기
        if not topics:
            paragraphs = [p.strip() for p in script.split('\n\n') if p.strip()]
            for i, para in enumerate(paragraphs[:5]):  # 최대 5개 이미지
                # 첫 문장만 추출
                first_sentence = para.split('.')[0] + '.'
                topics.append({
                    "id": f"topic_{i}",
                    "title": first_sentence[:100],  # 100자 제한
                    "timestamp": f"00:{i*2:02d}:00",
                    "order": i
                })
        
        logger.info(f"Extracted {len(topics)} topics from script")
        return topics

    def extract_key_terms(self, script: str) -> List[str]:
        """주요 용어 추출"""
        # 간단한 구현: 특수문자 제거 후 단어 추출
        words = re.findall(r'\b[가-힣]{2,}\b', script)
        # 빈도순 정렬
        from collections import Counter
        word_freq = Counter(words)
        return [word for word, _ in word_freq.most_common(10)]
