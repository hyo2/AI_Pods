# app/services/langgraph_service.py
import os
import logging
from typing import List, Dict, Any, Callable

from app.langgraph_pipeline.podcast.graph import create_podcast_graph
from app.langgraph_pipeline.podcast.state import PodcastState
from app.utils.output_helpers import output_exists

LANGGRAPH_URL = os.getenv("LANGGRAPH_URL")
logger = logging.getLogger(__name__)


class CancelledException(Exception):
    """Output이 삭제되어 작업이 취소된 경우"""
    pass


async def run_langgraph(
    main_sources: List[str],
    aux_sources: List[str],
    project_id: str,
    region: str,
    sa_file: str,
    host1: str,
    host2: str,
    style: str = "explain",
    duration: int = 5,
    difficulty: str = "intermediate",
    user_prompt: str = "",
    output_id: int | None = None,
    step_callback: Callable[[str], None] | None = None
) -> Dict[str, Any]:
    """
    Podcast 전용 LangGraph 실행
    output_id가 삭제되면 CancelledException을 발생시켜 조기 종료
    """
    graph = create_podcast_graph()

    initial_state: PodcastState = {
        "main_sources": main_sources,
        "aux_sources": aux_sources,
        "source_data": {},
        "main_texts": [],
        "aux_texts": [],
        "combined_text": "",
        "title": "",
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
        "host_name": host1,
        "guest_name": host2,
        "style": style,
        "duration": duration,
        "difficulty": difficulty,
        "user_prompt": user_prompt,
    }

    logger.info("🚀 Podcast LangGraph 실행 시작")

    # 시작 전 output 존재 확인
    if output_id and not output_exists(output_id):
        logger.info(f"⚠️ Output {output_id}가 이미 삭제됨 - 실행 취소")
        raise CancelledException(f"Output {output_id} was deleted before execution")

    thread_id = f"output_{output_id}" if output_id else f"run_{id(initial_state)}"
    config = {"configurable": {"thread_id": thread_id}}
    
    last_step = "start"
    final_state = None
    
    async for event in graph.astream(initial_state, config=config):
        for node_name, node_state in event.items():
            # 🔥 각 노드 완료 시점마다 output 존재 확인
            if output_id and not output_exists(output_id):
                logger.info(f"⚠️ Output {output_id}가 삭제됨 - 실행 중단")
                raise CancelledException(f"Output {output_id} was deleted during execution")
            
            final_state = node_state
            current_step = node_state.get("current_step", last_step)
            
            if current_step != last_step and step_callback:
                step_callback(current_step)
                last_step = current_step
                logger.info(f"📍 Step updated: {current_step}")

    # 최종 상태 검증
    if not final_state:
        raise RuntimeError("LangGraph 실행 중 상태를 받지 못했습니다.")

    # 🔥 최종 완료 전에도 한 번 더 확인
    if output_id and not output_exists(output_id):
        logger.info(f"⚠️ Output {output_id}가 완료 직전에 삭제됨")
        raise CancelledException(f"Output {output_id} was deleted before completion")

    if final_state.get("errors"):
        logger.warning(f"LangGraph errors: {final_state['errors']}")

    if not final_state.get("final_podcast_path"):
        raise RuntimeError(
            f"Podcast generation failed: {final_state.get('errors')}"
        )

    return {
        "source_data" : final_state["source_data"],
        "final_podcast_path": final_state["final_podcast_path"],
        "transcript_path": final_state.get("transcript_path", ""),
        "script": final_state.get("script", ""),
        "title": final_state.get("title", ""),
        "errors": final_state.get("errors", []),
    }