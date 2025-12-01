from typing import TypedDict, List, Optional, Dict, Any
from langgraph.graph import StateGraph, END

# State 정의
class PodcastState(TypedDict, total=False):
    user_sources: List[Any]
    user_options: Dict[str, Any]

    merged_source: Optional[str]
    cleaned_source: Optional[str] # 전처리된 소스

    draft_script: Optional[str] # 초안 스크립트(타임스탬프 X)
    summary: Optional[str]

    audio_file: Optional[str]
    timestamped_script: Optional[str] # 타임스탬프가 포함된 스크립트
    images: Optional[List[str]]
    final_script: Optional[str]

    route: Optional[str]   # 분기 결과 저장용


# Node 정의
def ingest_inputs(state: PodcastState):
    return state

def decide_merge_needed(state: PodcastState):
    # user_sources 개수에 따라 분기
    if len(state.get("user_sources", [])) <= 1:
        state["route"] = "skip_merge" # 단일 소스
    else:
        state["route"] = "merge_needed" # 멀티 소스
    return state

def merge_sources(state: PodcastState):
    return state

def preprocess_sources(state: PodcastState):
    return state

def generate_draft_script(state: PodcastState):
    return state

def generate_summary(state: PodcastState):
    return state

def generate_audio(state: PodcastState):
    return state

def generate_timestamped_script(state: PodcastState):
    return state

def generate_images(state: PodcastState):
    return state

def assemble_final_script(state: PodcastState):
    return state

def return_output(state: PodcastState):
    return state


# Graph 생성
graph = (
    StateGraph(PodcastState)
    .add_node("ingest_inputs", ingest_inputs)
    .add_node("decide_merge_needed", decide_merge_needed) # 조건부 노드 추가
    .add_node("merge_sources", merge_sources)
    .add_node("preprocess_sources", preprocess_sources)
    .add_node("generate_draft_script", generate_draft_script)
    .add_node("generate_summary", generate_summary)
    .add_node("generate_audio", generate_audio)
    .add_node("generate_timestamped_script", generate_timestamped_script) # 타임스탬프 노드 추가
    .add_node("generate_images", generate_images)
    .add_node("assemble_final_script", assemble_final_script)
    .add_node("return_output", return_output)


    # EDGE 정의
    .add_edge("__start__", "ingest_inputs")

    # 조건부 edge 정의
    .add_edge("ingest_inputs", "decide_merge_needed")
    .add_conditional_edges(
        "decide_merge_needed",
        lambda state: state["route"],  # route 값에 따라 분기
        {
            "skip_merge": "preprocess_sources",
            "merge_needed": "merge_sources",
        }
    )

    # 소스 통합 후 전처리로 이동
    .add_edge("merge_sources", "preprocess_sources")

    # 이후 노드들 간의 일반적인 흐름 정의
    .add_edge("preprocess_sources", "generate_draft_script")
    .add_edge("preprocess_sources", "generate_summary")
    .add_edge("generate_draft_script", "generate_audio")
    .add_edge("generate_summary", "generate_images")
    .add_edge("generate_draft_script", "generate_timestamped_script")
    .add_edge("generate_audio", "generate_timestamped_script")

    # 최종 스크립트 생성
    .add_edge("generate_timestamped_script", "assemble_final_script")
    .add_edge("generate_images", "assemble_final_script")

    # 최종 반환 콘텐츠 - 팟캐스트 오디오 및 스크립트
    .add_edge("generate_audio", "return_output")
    .add_edge("assemble_final_script", "return_output")
    .add_edge("return_output", "__end__")

    # 컴파일
    .compile()
)

# # Export graph
# __all__ = ["graph"] 