# app/services/podcast/models.py
from typing import TypedDict, List, Dict, Any
from typing_extensions import Annotated
from operator import add

class PodcastState(TypedDict):
    """팟캐스트 생성 워크플로우의 상태"""
    sources: List[str]
    extracted_texts: Annotated[List[str], add]
    combined_text: str
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