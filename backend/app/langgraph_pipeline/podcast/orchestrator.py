import logging
from typing import List, Dict, Any
from langgraph.graph import StateGraph, END
from langgraph.checkpoint.memory import MemorySaver

from .models import PodcastState
from .extractors import extract_all_sources
from .script_generator import ScriptGenerator
from .tts_service import TTSService
from .audio_processor import AudioProcessor
from .utils import generate_korean_names

logger = logging.getLogger(__name__)


def extract_texts_node(state: PodcastState) -> PodcastState:
    """노드 1: 모든 소스에서 텍스트 추출"""
    logger.info(f"텍스트 추출 시작: {len(state['sources'])}개 소스")
    
    extracted_texts, errors = extract_all_sources(state['sources'])
    
    return {
        **state,
        "extracted_texts": extracted_texts,
        "errors": state.get('errors', []) + errors,
        "current_step": "extract_complete"
    }


def combine_texts_node(state: PodcastState) -> PodcastState:
    """노드 2: 추출된 텍스트들을 결합"""
    logger.info("텍스트 결합 중...")
    
    if not state['extracted_texts']:
        return {
            **state,
            "errors": state.get('errors', []) + ["추출된 텍스트가 없습니다"],
            "current_step": "error"
        }
    
    combined = "\n\n---\n\n".join(state['extracted_texts'])
    
    return {
        **state,
        "combined_text": combined,
        "current_step": "combine_complete"
    }



def generate_script_node(state: PodcastState) -> PodcastState:
    """노드 3: LLM을 사용하여 팟캐스트 스크립트 생성"""
    logger.info("팟캐스트 스크립트 생성 중...")
    logger.info(f"진행자: {state['host_name']}, 게스트: {state['guest_name']}")
    logger.info(f"스타일: {state.get('style', 'explain')}")  # 스타일 로깅
    
    try:
        generator = ScriptGenerator(
            project_id=state['project_id'],
            region=state['region'],
            sa_file=state['sa_file'],
            style=state.get('style', 'explain')  #  스타일 전달
        )
        
        script = generator.generate_script(
            combined_text=state['combined_text'],
            host_name=state['host_name'],
            guest_name=state['guest_name']
        )
        
        return {
            **state,
            "script": script,
            "current_step": "script_complete"
        }
        
    except Exception as e:
        return {
            **state,
            "errors": state.get('errors', []) + [f"스크립트 생성 오류: {str(e)}"],
            "current_step": "error"
        }


def generate_audio_node(state: PodcastState) -> PodcastState:
    """노드 4: TTS를 사용하여 오디오 생성"""
    logger.info("Multi-Speaker TTS 변환 중...")
    
    try:
        tts_service = TTSService()
        
        audio_metadata, wav_files = tts_service.generate_audio(
            script=state['script'],
            host_name=state['host_name'],
            guest_name=state['guest_name']
        )
        
        return {
            **state,
            "audio_metadata": audio_metadata,
            "wav_files": wav_files,
            "current_step": "audio_complete"
        }
        
    except Exception as e:
        return {
            **state,
            "errors": state.get('errors', []) + [f"오디오 생성 오류: {str(e)}"],
            "current_step": "error"
        }


def merge_audio_node(state: PodcastState) -> PodcastState:
    """노드 5: 오디오 파일들을 병합"""
    logger.info("오디오 파일 병합 중...")
    
    if not state['wav_files']:
        return {
            **state,
            "errors": state.get('errors', []) + ["병합할 오디오 파일이 없습니다"],
            "current_step": "error"
        }
    try:
        processor = AudioProcessor()
        
        final_path = processor.merge_audio_files(state['wav_files'])
        
        return {
            **state,
            "final_podcast_path": final_path,
            "current_step": "merge_complete"
        }
        
    except Exception as e:
        return {
            **state,
            "errors": state.get('errors', []) + [f"병합 오류: {str(e)}"],
            "current_step": "error"
        }

def generate_transcript_node(state: PodcastState) -> PodcastState:
    """노드 6: 타임스탬프 스크립트 생성"""
    logger.info("타임스탬프 스크립트 생성 중...")
    try:
        processor = AudioProcessor()
        
        transcript_path = processor.generate_transcript(
            audio_metadata=state['audio_metadata'],
            output_path=state['final_podcast_path']
        )
        
        return {
            **state,
            "transcript_path": transcript_path,
            "current_step": "complete"
        }
        
    except Exception as e:
        return {
            **state,
            "errors": state.get('errors', []) + [f"스크립트 생성 오류: {str(e)}"],
            "current_step": "error"
        }
        
# 

def create_podcast_graph():
    """팟캐스트 생성 워크플로우 그래프 생성"""
    workflow = StateGraph(PodcastState)
    # 노드 추가
    workflow.add_node("extract_texts", extract_texts_node)
    workflow.add_node("combine_texts", combine_texts_node)
    workflow.add_node("generate_script", generate_script_node)
    workflow.add_node("generate_audio", generate_audio_node)
    workflow.add_node("merge_audio", merge_audio_node)
    workflow.add_node("generate_transcript", generate_transcript_node)

    # 엣지 정의
    workflow.set_entry_point("extract_texts")
    workflow.add_edge("extract_texts", "combine_texts")
    workflow.add_edge("combine_texts", "generate_script")
    workflow.add_edge("generate_script", "generate_audio")
    workflow.add_edge("generate_audio", "merge_audio")
    workflow.add_edge("merge_audio", "generate_transcript")
    workflow.add_edge("generate_transcript", END)

    # 메모리 체크포인터 추가
    memory = MemorySaver()
    app = workflow.compile(checkpointer=memory)

    return app

def run_podcast_generation(
    sources: List[str],
    project_id: str,
    region: str,
    sa_file: str,
    host_name: str = None,
    guest_name: str = None,
    style: str = "explain"
) -> Dict[str, Any]:
    """
    팟캐스트 생성 메인 함수
    Args:
        sources: 파일 경로 또는 URL 리스트
        project_id: Google Cloud Project ID
        region: Vertex AI 리전
        sa_file: 서비스 계정 파일 경로
        host_name: 진행자 이름 (선택)
        guest_name: 게스트 이름 (선택)

    Returns:
        {
            "final_podcast_path": str,
            "transcript_path": str,
            "host_name": str,
            "guest_name": str,
            "errors": List[str]
        }
    """
    if not project_id:
        raise ValueError("Google Cloud Project ID를 지정해야 합니다")

    # 이름 생성 또는 사용자 지정 이름 사용
    if host_name and guest_name:
        host = host_name
        guest = guest_name
        logger.info("사용자 지정 이름 사용")
    else:
        host, guest = generate_korean_names()
        logger.info("자동 생성된 이름 사용")

    logger.info(f"진행자: {host}, 게스트: {guest}")

    # 초기 상태 설정
    initial_state = {
        "sources": sources,
        "extracted_texts": [],
        "combined_text": "",
        "script": "",
        "audio_metadata": [],
        "wav_files": [],
        "final_podcast_path": "",
        "transcript_path": "",
        "errors": [],
        "current_step": "start",
        "project_id": project_id,
        "region": region,
        "sa_file": sa_file,
        "host_name": host,
        "guest_name": guest,
        "style": style
    }

    # 그래프 생성 및 실행
    app = create_podcast_graph()
    # LangGraph 스레드 ID는 고유해야 합니다.
    config = {"configurable": {"thread_id": f"podcast_generation_{id(initial_state)}"}}

    logger.info("LangGraph 기반 팟캐스트 생성 시작")

    try:
        final_state = app.invoke(initial_state, config)
        
        if final_state.get('errors'):
            logger.warning(f"경고: {len(final_state['errors'])}개의 오류 발생")
            for error in final_state['errors']:
                logger.warning(f"  - {error}")
        
        if final_state.get('final_podcast_path'):
            logger.info("성공적으로 변환 완료!")
            logger.info(f"최종 팟캐스트: {final_state['final_podcast_path']}")
            logger.info(f"스크립트: {final_state.get('transcript_path', 'N/A')}")
            
            return {
                "final_podcast_path": final_state['final_podcast_path'],
                "transcript_path": final_state.get('transcript_path', ''),
                "errors": final_state.get('errors', []),
                "host_name": host,
                "guest_name": guest
            }
        else:
            # 최종 경로가 없으면 오류로 간주
            raise RuntimeError(f"팟캐스트 생성에 실패했습니다. 오류 목록: {final_state.get('errors', ['알 수 없는 오류'])}")
            
    except Exception as e:
        logger.error(f"실행 오류: {e}", exc_info=True)
        raise