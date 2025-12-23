# app/services/podcast/state.py

from typing import TypedDict, List, Dict, Any
from typing_extensions import Annotated
from operator import add

class PodcastState(TypedDict):
    """팟캐스트 생성 워크플로우의 State"""
    
    # 1. 입력 (파일 경로)
    main_sources: List[str]       # 주 소스 파일 경로들
    aux_sources: List[str]        # 보조 소스 파일 경로들
    
    # 2. 구조화된 메타데이터
    source_data: Dict[str, Any]   # 각 소스 파일에서 추출된 메타데이터
    
    # 3. 텍스트 데이터 (LLM 프롬프트용)
    main_texts: List[str]         # 주 소스 텍스트
    aux_texts: List[str]          # 보조 소스 텍스트
    
    # 4. 생성 결과물
    combined_text: str            # 최종 결합 텍스트
    title: str                    # 생성된 팟캐스트 제목
    script: str                   # 생성된 팟캐스트 스크립트
    audio_metadata: List[Dict[str, Any]] # 오디오 메타데이터 리스트
    wav_files: List[str]          # 생성된 WAV 파일 경로 리스트
    final_podcast_path: str       # 최종 팟캐스트 파일 경로
    transcript_path: str          # 전사 파일 경로
    
    # 5. 설정 및 상태
    errors: Annotated[List[str], add] # 오류 메시지 리스트
    current_step: str             # 현재 처리 단계
    project_id: str               # Vertex AI 프로젝트 ID
    region: str                   # Vertex AI 리전
    sa_file: str                  # 서비스 계정 파일 경로
    host_name: str                # 호스트 이름
    guest_name: str               # 게스트 이름
    style: str                    # 팟캐스트 스타일
    duration: int                 # 예상 지속 시간 (분)
    difficulty: str               #  [추가됨] 난이도 (basic, intermediate, advanced)
    user_prompt: str              # 사용자 지정 프롬프트
    usage: Dict[str, Any]   # ✅ 토큰/비용 메타데이터