# app/langgraph_pipeline/podcast/graph.py

import logging
import json
import os
import uuid
from typing import List, Dict, Any
from langgraph.graph import StateGraph, END
from langgraph.checkpoint.memory import MemorySaver

from .state import PodcastState
from .metadata_generator_node import MetadataGenerator 
from .script_generator import ScriptGenerator
from .tts_service import TTSService
from .audio_processor import AudioProcessor

logger = logging.getLogger(__name__)


def get_temp_output_dir() -> str:
    """환경에 맞는 임시 출력 디렉토리 반환"""
    base = os.getenv("BASE_OUTPUT_DIR", "outputs")
    return base


def extract_texts_node(state: PodcastState) -> PodcastState:
    """노드 1: MetadataGenerator를 사용하여 텍스트와 이미지 설명 추출"""
    logger.info("메타데이터 생성 및 텍스트 추출 시작...")
    
    main_sources = state.get('main_sources', [])
    aux_sources = state.get('aux_sources', [])
    
    if not main_sources:
        return {
            **state,
            "errors": ["처리할 주 소스 파일이 없습니다."],
            "current_step": "error"
        }

    try:
        primary_file = main_sources[0]
        supplementary_files = main_sources[1:] + aux_sources
        
        logger.info(f"Primary: {primary_file}, Supp: {len(supplementary_files)}개")

        generator = MetadataGenerator()
        
        #  환경 변수 기반 경로 사용
        output_dir = get_temp_output_dir()
        temp_json_path = os.path.join(output_dir, f"temp_metadata_{uuid.uuid4().hex[:8]}.json")
        
        generated_path = generator.generate(
            primary_file=primary_file,
            supplementary_files=supplementary_files,
            output_path=temp_json_path
        )
        
        with open(generated_path, 'r', encoding='utf-8') as f:
            source_data = json.load(f)
            
        if os.path.exists(generated_path):
            os.remove(generated_path)
        
        main_texts = []
        aux_texts = []
        
        primary = source_data.get("primary_source", {}) 
        if primary and "content" in primary:
            text = primary["content"].get("full_text", "")
            if text:
                images = primary.get("filtered_images", [])
                if images:
                    text += "\n\n=== [VISUAL CONTEXT] (Images in the document) ===\n"
                    for img in images:
                        desc = img.get("description", "")
                        page = img.get("page_number", "?")
                        text += f"- Page {page}: {desc}\n"
                
                main_texts.append(text)

        supp_list = source_data.get("supplementary_sources", [])
        for supp in supp_list:
            text = supp.get("content", {}).get("full_text", "")
            if text:
                aux_texts.append(text)

        logger.info(f"파싱 완료 - Main: {len(main_texts)}개, Aux: {len(aux_texts)}개")
        
        return {
            **state,
            "source_data": source_data,
            "main_texts": main_texts,
            "aux_texts": aux_texts,
            "errors": [],
            "current_step": "extract_complete"
        }

    except Exception as e:
        logger.error(f"메타데이터 생성 실패: {e}", exc_info=True)
        return {
            **state,
            "errors": state.get('errors', []) + [f"추출 오류: {str(e)}"],
            "current_step": "error"
        }


def combine_texts_node(state: PodcastState) -> PodcastState:
    """노드 2: 텍스트 구조화 및 결합"""
    logger.info("텍스트 구조화 및 결합 중...")
    
    if not state['main_texts']:
        return {
            **state,
            "errors": state.get('errors', []) + ["주 소스 텍스트가 없습니다."],
            "current_step": "error"
        }
    
    formatted_text = "=== [MAIN SOURCE] (Core Content) ===\n"
    formatted_text += "The following content is the primary topic. Focus the script on this.\n\n"
    formatted_text += "\n\n---\n\n".join(state['main_texts'])
    
    if state['aux_texts']:
        formatted_text += "\n\n\n=== [AUXILIARY SOURCE] (Reference/Context) ===\n"
        formatted_text += "Use the following content only for supporting details.\n\n"
        formatted_text += "\n\n---\n\n".join(state['aux_texts'])
    
    return {
        **state,
        "combined_text": formatted_text,
        "current_step": "combine_complete"
    }


def generate_script_node(state: PodcastState) -> PodcastState:
    """노드 3: 스크립트 생성"""
    logger.info("스크립트 생성 중...")
    try:
        generator = ScriptGenerator(
            project_id=state['project_id'],
            region=state['region'],
            sa_file=state['sa_file'],
            style=state.get('style', 'explain')
        )
        
        #  [수정] difficulty 파라미터 전달 추가
        result = generator.generate_script(
            combined_text=state['combined_text'],
            host_name=state['host_name'],
            guest_name=state['guest_name'],
            duration=state.get('duration', 5),
            difficulty=state.get('difficulty', 'intermediate'), # <--- 여기 추가됨
            user_prompt=state.get('user_prompt', "")
        )
        
        return {
            **state,
            "title": result.get("title", "Untitled"),
            "script": result.get("script", ""),
            "current_step": "script_complete"
        }
    except Exception as e:
        logger.error(f"스크립트 생성 오류: {e}")
        return {**state, "errors": state.get('errors', []) + [str(e)], "current_step": "error"}


def generate_audio_node(state: PodcastState) -> PodcastState:
    """노드 4: TTS 변환"""
    logger.info("TTS 변환 중...")
    try:
        tts = TTSService()
        metadata, files = tts.generate_audio(state['script'], state['host_name'], state['guest_name'])
        return {**state, "audio_metadata": metadata, "wav_files": files, "current_step": "audio_complete"}
    except Exception as e:
        logger.error(f"TTS 오류: {e}")
        return {**state, "errors": state.get('errors', []) + [str(e)], "current_step": "error"}


def merge_audio_node(state: PodcastState) -> PodcastState:
    """노드 5: 오디오 병합"""
    logger.info("오디오 병합 중...")
    if not state.get('wav_files'):
         return {**state, "errors": state.get('errors', []) + ["오디오 파일 없음"], "current_step": "error"}
    try:
        processor = AudioProcessor()
        path = processor.merge_audio_files(state['wav_files'])
        return {**state, "final_podcast_path": path, "current_step": "merge_complete"}
    except Exception as e:
        logger.error(f"병합 오류: {e}")
        return {**state, "errors": state.get('errors', []) + [str(e)], "current_step": "error"}


def generate_transcript_node(state: PodcastState) -> PodcastState:
    """노드 6: 트랜스크립트 생성"""
    logger.info("트랜스크립트 생성 중...")
    try:
        processor = AudioProcessor()
        path = processor.generate_transcript(state['audio_metadata'], state['final_podcast_path'])
        return {**state, "transcript_path": path, "current_step": "complete"}
    except Exception as e:
        logger.error(f"트랜스크립트 오류: {e}")
        return {**state, "errors": state.get('errors', []) + [str(e)], "current_step": "error"}


def create_podcast_graph():
    """LangGraph 그래프 정의"""
    workflow = StateGraph(PodcastState)
    
    workflow.add_node("extract_texts", extract_texts_node)
    workflow.add_node("combine_texts", combine_texts_node)
    workflow.add_node("generate_script", generate_script_node)
    workflow.add_node("generate_audio", generate_audio_node)
    workflow.add_node("merge_audio", merge_audio_node)
    workflow.add_node("generate_transcript", generate_transcript_node)

    workflow.set_entry_point("extract_texts")
    workflow.add_edge("extract_texts", "combine_texts")
    workflow.add_edge("combine_texts", "generate_script")
    workflow.add_edge("generate_script", "generate_audio")
    workflow.add_edge("generate_audio", "merge_audio")
    workflow.add_edge("merge_audio", "generate_transcript")
    workflow.add_edge("generate_transcript", END)

    return workflow.compile(checkpointer=MemorySaver())


def run_podcast_generation(
    main_sources: List[str],       
    aux_sources: List[str],        
    project_id: str,
    region: str,
    sa_file: str,
    host_name: str = None,
    guest_name: str = None,
    style: str = "explain",
    duration: int = 5,
    difficulty: str = "intermediate", # [수정] 인자 추가됨!
    user_prompt: str = ""
) -> Dict[str, Any]:
    """팟캐스트 생성 메인 실행 함수"""
    if not project_id:
        raise ValueError("Google Cloud Project ID를 지정해야 합니다")

    host = host_name if host_name else "진행자"
    guest = guest_name if guest_name else "게스트"

    logger.info(f"진행자: {host}, 게스트: {guest}")
    logger.info(f"설정 - 스타일: {style}, 시간: {duration}분, 난이도: {difficulty}")

    initial_state = {
        "main_sources": main_sources,
        "aux_sources": aux_sources,
        "source_data": {}, 
        "main_texts": [],
        "aux_texts": [],
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
        "style": style,
        "duration": duration,
        "difficulty": difficulty, #  [수정] State에 난이도 전달
        "user_prompt": user_prompt
    }

    app = create_podcast_graph()
    config = {"configurable": {"thread_id": f"podcast_generation_{id(initial_state)}"}}

    logger.info("LangGraph 워크플로우 시작...")

    try:
        final_state = app.invoke(initial_state, config)
        
        if final_state.get('errors'):
            logger.warning(f"오류 발생: {final_state['errors']}")
        
        if final_state.get('final_podcast_path'):
            return {
                "final_podcast_path": final_state['final_podcast_path'],
                "transcript_path": final_state.get('transcript_path', ''),
                "errors": final_state.get('errors', []),
                "host_name": host,
                "guest_name": guest
            }
        else:
            raise RuntimeError(f"실패: {final_state.get('errors')}")
            
    except Exception as e:
        logger.error(f"실행 오류: {e}", exc_info=True)
        raise