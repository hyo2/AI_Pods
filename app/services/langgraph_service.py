# app/services/langgraph_service.py
import os
import logging
from typing import List, Dict, Any

from app.langgraph_pipeline.podcast.graph import create_podcast_graph
from app.langgraph_pipeline.podcast.state import PodcastState

LANGGRAPH_URL = os.getenv("LANGGRAPH_URL")
logger = logging.getLogger(__name__)

async def run_langgraph(
    main_sources: List[str],
    aux_sources: List[str],
    project_id: str,
    region: str,
    sa_file: str,
    host1: str,
    host2: str, # 없애는 방향으로 수정하기
    style: str = "explain",
    duration: int = 5,
    user_prompt: str = "",
    output_id: int | None = None
) -> Dict[str, Any]:
    """
    Podcast 전용 LangGraph 실행
    """
    graph = create_podcast_graph()

    initial_state: PodcastState = {
        "main_sources": main_sources,
        "aux_sources": aux_sources,
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
        "user_prompt": user_prompt,
    }

    logger.info("🚀 Podcast LangGraph 실행 시작")

    thread_id = f"output_{output_id}" if output_id else f"run_{id(initial_state)}"
    config = {"configurable": {"thread_id": thread_id}}
    final_state = await graph.ainvoke(initial_state, config=config)

    if final_state.get("errors"):
        logger.warning(f"LangGraph errors: {final_state['errors']}")

    if not final_state.get("final_podcast_path"):
        raise RuntimeError(
            f"Podcast generation failed: {final_state.get('errors')}"
        )

    return {
        "final_podcast_path": final_state["final_podcast_path"],
        "transcript_path": final_state.get("transcript_path", ""),
        "script": final_state.get("script", ""),
        "title": final_state.get("title", ""),
        "errors": final_state.get("errors", []),
    }