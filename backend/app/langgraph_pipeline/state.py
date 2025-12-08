# app/langgraph_pipeline/state.py
from typing import TypedDict, List, Dict, Any, Optional
from typing_extensions import Annotated
from operator import add

class PipelineState(TypedDict, total=False):
    # Environment
    project_id: str
    region: str
    sa_file: str
    host_name: str
    guest_name: str
    style: str

    # Podcast stage
    sources: List[str]
    extracted_texts: Annotated[List[str], add]
    combined_text: str
    script: str
    audio_metadata: List[Dict[str, Any]]
    wav_files: List[str]
    final_podcast_path: str
    transcript_path: str

    # Vision stage
    script_text: str
    scenes: List[Dict[str, Any]]
    metadata: Dict[str, Any]
    image_plans: List[Dict[str, Any]]
    image_prompts: List[Dict[str, Any]]
    timeline: List[Dict[str, Any]]
    image_paths: Dict[str, str]

    # 오류 관리
    errors: Annotated[List[str], add]