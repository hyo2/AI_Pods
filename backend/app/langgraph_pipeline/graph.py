import os
from dotenv import load_dotenv
load_dotenv()

import logging
from langgraph.graph import StateGraph, END
from .state import PipelineState

# PostgreSQL Checkpointing - 일단 주석 처리
# from langgraph_checkpoint_postgres import PostgresSaver
# import psycopg

# DATABASE_URL = os.environ.get("DATABASE_URL")

# PostgresSaver 초기화
# if DATABASE_URL:
#     checkpointer = PostgresSaver.from_conn_string(DATABASE_URL)
# else:
#     checkpointer = None

checkpointer = None  # 일단 체크포인터 없이 사용

# Podcast nodes
from app.langgraph_pipeline.podcast.orchestrator import (
    extract_texts_node,
    combine_texts_node,
    generate_script_node,
    generate_audio_node,
    merge_audio_node,
    generate_transcript_node,
)

# Vision nodes
from app.langgraph_pipeline.vision.script_parser_node import ScriptParserNode
from app.langgraph_pipeline.vision.metadata_extraction_node import MetadataExtractionNode
from app.langgraph_pipeline.vision.image_planning_node import ImagePlanningNode
from app.langgraph_pipeline.vision.prompt_generation_node import PromptGenerationNode
from app.langgraph_pipeline.vision.timestamp_mapper import TimestampMapper
from app.langgraph_pipeline.vision.image_generation_node import ImageGenerationNode

logger = logging.getLogger(__name__)


# Wrapper nodes
def read_transcript_node(state: PipelineState):
    """transcript_path → script_text"""
    path = state.get("transcript_path")
    if not path:
        return {"errors": state.get("errors", []) + ["No transcript_path"]}

    try:
        with open(path, "r", encoding="utf-8") as f:
            txt = f.read()
        return {"script_text": txt}
    except Exception as e:
        return {"errors": state.get("errors", []) + [str(e)]}


def script_parser_node(state: PipelineState):
    """타임스탬프 있는 스크립트 → scenes(list[PodcastScene])"""
    parser = ScriptParserNode()
    scenes = parser.parse_from_text(state["script_text"])
    return {"scenes": scenes}


def metadata_node(state: PipelineState):
    """
    scenes(list[PodcastScene]) → metadata(PodcastMetadata)
    MetadataExtractionNode.__call__은 dict state를 받고
    { **state, "metadata": PodcastMetadata } 를 리턴
    """
    node = MetadataExtractionNode(
        project_id=state["project_id"],
        location=state["region"],
    )
    out = node({"scenes": state["scenes"]})
    return {"metadata": out["metadata"]}


def image_planning_node(state: PipelineState):
    """
    script_text + metadata → image_plans(list[ImagePlan])
    ImagePlanningNode.__call__은 dict state를 받고
    { **state, "image_plans": [...] } 를 리턴
    """
    node = ImagePlanningNode(
        project_id=state["project_id"],
        location=state["region"],
    )
    out = node({
        "full_script": state["script_text"],
        "metadata": state["metadata"],
    })
    return {"image_plans": out["image_plans"]}


def prompt_generation_node(state: PipelineState):
    """
    image_plans + metadata → image_prompts(list[dict])
    PromptGenerationNode.__call__은 dict state를 받고
    { **state, "image_prompts": [...] } 를 리턴
    """
    node = PromptGenerationNode(
        project_id=state["project_id"],
        location=state["region"],
    )
    out = node({
        "image_plans": state["image_plans"],
        "metadata": state["metadata"],
    })
    return {"image_prompts": out["image_prompts"]}


def timestamp_mapper_node(state: PipelineState):
    """
    image_prompts(list[dict]) → timeline(list[TimelineEntry])
    TimestampMapper.__call__은 dict state를 받고
    { **state, "timeline": [...] } 를 리턴
    """
    node = TimestampMapper()
    out = node({
        "image_prompts": state["image_prompts"],
    })
    return {"timeline": out["timeline"]}


def image_generation_node(state: PipelineState):
    """
    image_prompts(list[dict]) → image_paths(dict[image_id → path])
    ImageGenerationNode.__call__은 dict state를 받고 
    { **state, "image_paths": {...} } 를 리턴
    """
    node = ImageGenerationNode(
        project_id=state["project_id"],
        location=state["region"],
        output_dir="outputs/images",
    )
    out = node({
        "image_prompts": state["image_prompts"],
    })
    
    # image_prompts 정보를 image_paths와 연결
    # 혹시 다른 노드에서 title을 찾는다면 여기서 매핑 제공
    image_metadata = {}
    for prompt_data in state.get("image_prompts", []):
        image_id = prompt_data.get("image_id")
        if image_id:
            image_metadata[image_id] = {
                "title": prompt_data.get("image_title", ""),
                "timestamp": prompt_data.get("primary_timestamp", ""),
                "duration": prompt_data.get("duration", 0),
            }
    
    return {
        "image_paths": out["image_paths"],
        "image_metadata": image_metadata,  # 추가 정보 제공
    }


# Create LangGraph Pipeline
def create_full_graph():
    graph = StateGraph(PipelineState)

    # Podcast part
    graph.add_node("extract_texts", extract_texts_node)
    graph.add_node("combine_texts", combine_texts_node)
    graph.add_node("generate_script", generate_script_node)
    graph.add_node("generate_audio", generate_audio_node)
    graph.add_node("merge_audio", merge_audio_node)
    graph.add_node("generate_transcript", generate_transcript_node)

    # Bridge
    graph.add_node("read_transcript", read_transcript_node)

    # Vision part
    graph.add_node("parse_script", script_parser_node)
    graph.add_node("extract_metadata", metadata_node)
    graph.add_node("plan_images", image_planning_node)
    graph.add_node("generate_prompts", prompt_generation_node)
    graph.add_node("map_timestamps", timestamp_mapper_node)
    graph.add_node("generate_images", image_generation_node)

    # Flow
    graph.set_entry_point("extract_texts")

    graph.add_edge("extract_texts", "combine_texts")
    graph.add_edge("combine_texts", "generate_script")
    graph.add_edge("generate_script", "generate_audio")
    graph.add_edge("generate_audio", "merge_audio")
    graph.add_edge("merge_audio", "generate_transcript")

    graph.add_edge("generate_transcript", "read_transcript")
    graph.add_edge("read_transcript", "parse_script")
    graph.add_edge("parse_script", "extract_metadata")
    graph.add_edge("extract_metadata", "plan_images")
    graph.add_edge("plan_images", "generate_prompts")
    graph.add_edge("generate_prompts", "map_timestamps")
    graph.add_edge("map_timestamps", "generate_images")
    graph.add_edge("generate_images", END)

    return graph.compile(checkpointer=checkpointer)
