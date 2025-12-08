# app/services/langgraph_service.py
import os
import logging
from app.langgraph_pipeline.graph import create_full_graph
from app.langgraph_pipeline.state import PipelineState

LANGGRAPH_URL = os.getenv("LANGGRAPH_URL")
logger = logging.getLogger(__name__)

async def run_langgraph(
    sources: list[str],
    project_id: str,
    region: str,
    sa_file: str,
    host1: str,
    host2: str,
    style: str = "explain",
):
    """파이프라인 실행"""
    try:
        """
        LangGraph 전체 파이프라인 실행
        Return: FastAPI에서 DB 저장에 필요한 모든 최종 데이터
        """

        graph = create_full_graph()

        initial_state: PipelineState = {
            "sources": sources,
            "project_id": project_id,
            "region": region,
            "sa_file": sa_file,
            "host_name": host1,
            "guest_name": host2,
            "style": style,
            "errors": [],
        }

        logger.info("🚀 LangGraph 파이프라인 실행 시작")

        final_state = await graph.ainvoke(initial_state)
        
        # 최종 state 확인
        print("\n" + "="*80)
        print("✅ 파이프라인 완료 - 최종 State")
        print("="*80)

        # 모든 키 출력
        print("\n📋 사용 가능한 키:")
        for key in sorted(final_state.keys()):
            value = final_state[key]
            
            # 값 타입과 간단한 정보 출력
            if isinstance(value, list):
                print(f"  - {key}: List[{len(value)}개]")
            elif isinstance(value, dict):
                print(f"  - {key}: Dict[{len(value)}개 키]")
            elif isinstance(value, str):
                preview = value[:50] + "..." if len(value) > 50 else value
                print(f"  - {key}: str = {preview}")
            else:
                print(f"  - {key}: {type(value).__name__}")
        
        # 중요 필드 상세 출력
        print("\n" + "="*80)
        print("📦 주요 결과물")
        print("="*80)
        
        # Podcast 결과
        if "final_podcast_path" in final_state:
            print(f"\n🎙️  팟캐스트:")
            print(f"   경로: {final_state['final_podcast_path']}")
        
        if "transcript_path" in final_state:
            print(f"   스크립트: {final_state['transcript_path']}")
        
        # Vision 결과
        if "image_paths" in final_state:
            print(f"\n🖼️  이미지:")
            for img_id, path in final_state["image_paths"].items():
                print(f"   {img_id}: {path}")
        
        if "timeline" in final_state:
            print(f"\n⏰ 타임라인: {len(final_state['timeline'])}개 항목")
        
        # 에러 확인
        if "errors" in final_state and final_state["errors"]:
            print(f"\n⚠️  에러: {len(final_state['errors'])}개")
            for err in final_state["errors"]:
                print(f"   - {err}")
        
        # title_line = final_state["script"].split("\n")[0]
        # title_text = title_line.replace("팟캐스트:", "").replace("\"", "").strip()
        title_sub = final_state["image_plans"][0].title

        # print("추출된 title text :", title_text)
        print("팟캐스트 title : ", title_sub)
        # print("추출된 summary : ", final_state["metadata"].content.summary)
        print("추출된 detailed_summary : ", final_state["metadata"].content.detailed_summary)
        return final_state
        
    except Exception as e:
        # 전체 스택 트레이스 출력
        import traceback
        print("\n" + "="*80)
        print("❌ 파이프라인 오류 발생")
        print("="*80)
        print(traceback.format_exc())
        print("="*80)
        raise