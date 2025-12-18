# app/services/podcast/models.py
from typing import TypedDict, List, Dict, Any
from typing_extensions import Annotated
from operator import add

class PodcastState(TypedDict):
    """팟캐스트 생성 워크플로우의 State"""
    # 소스와 추출 텍스트를 주/보조로 분리
    main_sources: List[str]       # 주 소스 파일 경로들
    aux_sources: List[str]        # 보조 소스 파일 경로들
    
    main_texts: List[str]         # 주 소스에서 추출된 텍스트
    aux_texts: List[str]          # 보조 소스에서 추출된 텍스트
    
    combined_text: str            # LLM에 들어갈 최종 결합 텍스트 (태그 포함)
    
    title: str
    script: str
    audio_metadata: List[Dict[str, Any]]
    wav_files: List[str]
    final_podcast_path: str
    transcript_path: str
    errors: Annotated[List[str], add]
    current_step: str
    project_id: str
    region: str
    sa_file: str
    host_name: str
    guest_name: str
    style: str
    duration: int # 목표 시간 (분)
    user_prompt: str # 사용자 추가 요청사항

    # Error handling
    errors: Annotated[List[str], add]