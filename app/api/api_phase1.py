"""
FastAPI 엔드포인트: 문서 분석 API
Phase 1: 텍스트 기반 분석
"""

from fastapi import FastAPI, HTTPException, Body
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
from dataclasses import asdict
import vertexai

from app.nodes.document_analysis_node import (
    DocumentAnalysisNode,
    SourceDocument,
    CompleteAnalysis
)


# ============================================================================
# Pydantic 모델 (Request/Response)
# ============================================================================

class TextSourceRequest(BaseModel):
    """텍스트 소스 입력"""
    id: Optional[str] = Field(None, description="문서 ID (자동 생성 가능)")
    content: str = Field(..., description="문서 텍스트 내용")
    doc_type: Optional[str] = Field("text", description="문서 유형")
    metadata: Optional[Dict[str, Any]] = Field(None, description="추가 메타데이터")


class AnalysisRequest(BaseModel):
    """문서 분석 요청"""
    sources: List[TextSourceRequest] = Field(..., description="분석할 문서 리스트")
    model_name: Optional[str] = Field(
        "gemini-2.0-flash-exp", 
        description="사용할 Gemini 모델"
    )
    generation_config: Optional[Dict[str, Any]] = Field(
        None,
        description="Gemini 생성 설정"
    )


class AnalysisResponse(BaseModel):
    """문서 분석 응답"""
    success: bool
    message: str
    data: Optional[Dict[str, Any]] = None
    error: Optional[str] = None


# ============================================================================
# FastAPI 앱
# ============================================================================

app = FastAPI(
    title="Alan Document Lab - 문서 분석 API",
    description="텍스트 기반 문서 분석 및 팟캐스트 정보 구조화",
    version="1.0.0 (Phase 1)"
)

# CORS 설정
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # 프로덕션에서는 제한 필요
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ============================================================================
# 엔드포인트
# ============================================================================

@app.on_event("startup")
async def startup_event():
    """서버 시작 시 Vertex AI 초기화"""
    vertexai.init(
        project="alan-document-lab",
        location="us-central1"
    )
    print("✅ Vertex AI 초기화 완료")


@app.get("/")
async def root():
    """API 루트"""
    return {
        "name": "Alan Document Lab - 문서 분석 API",
        "version": "1.0.0",
        "phase": "Phase 1: 텍스트 분석",
        "endpoints": {
            "analyze": "/api/v1/analyze",
            "health": "/health"
        }
    }


@app.get("/health")
async def health_check():
    """헬스 체크"""
    return {
        "status": "healthy",
        "service": "document-analysis",
        "phase": "1"
    }


@app.post("/api/v1/analyze", response_model=AnalysisResponse)
async def analyze_documents(request: AnalysisRequest):
    """
    문서 분석 엔드포인트
    
    ## 사용 예제
    
    ### 단일 문서
    ```json
    {
      "sources": [
        {
          "content": "AI 기술의 발전과 미래 전망...",
          "doc_type": "text"
        }
      ]
    }
    ```
    
    ### 멀티 문서
    ```json
    {
      "sources": [
        {
          "id": "doc_1",
          "content": "첫 번째 문서 내용...",
          "doc_type": "text"
        },
        {
          "id": "doc_2",
          "content": "두 번째 문서 내용...",
          "doc_type": "text"
        }
      ]
    }
    ```
    """
    try:
        # 입력 검증
        if not request.sources:
            raise HTTPException(
                status_code=400,
                detail="최소 1개 이상의 문서가 필요합니다"
            )
        
        # SourceDocument 변환
        sources = []
        for i, source_req in enumerate(request.sources):
            source_id = source_req.id or f"doc_{i+1}"
            
            source = SourceDocument(
                id=source_id,
                content=source_req.content,
                doc_type=source_req.doc_type,
                metadata=source_req.metadata
            )
            sources.append(source)
        
        # 분석 실행
        analyzer = DocumentAnalysisNode(model_name=request.model_name)
        
        generation_config = request.generation_config or {}
        result = analyzer.analyze_documents(sources, **generation_config)
        
        # 응답 생성
        return AnalysisResponse(
            success=True,
            message=f"{len(sources)}개 문서 분석 완료",
            data=asdict(result)
        )
    
    except HTTPException as he:
        raise he
    
    except Exception as e:
        print(f"❌ 분석 에러: {str(e)}")
        import traceback
        traceback.print_exc()
        
        raise HTTPException(
            status_code=500,
            detail=f"문서 분석 중 오류 발생: {str(e)}"
        )


@app.post("/api/v1/analyze/quick")
async def quick_analyze(
    content: str = Body(..., embed=True),
    model_name: str = Body("gemini-2.0-flash-exp", embed=True)
):
    """
    빠른 단일 문서 분석
    
    ## 사용 예제
    ```json
    {
      "content": "분석할 텍스트 내용..."
    }
    ```
    """
    try:
        # 단일 문서 생성
        source = SourceDocument(
            id="quick_analysis",
            content=content,
            doc_type="text"
        )
        
        # 분석 실행
        analyzer = DocumentAnalysisNode(model_name=model_name)
        result = analyzer.analyze_documents([source])
        
        return AnalysisResponse(
            success=True,
            message="빠른 분석 완료",
            data=asdict(result)
        )
    
    except Exception as e:
        print(f"❌ 분석 에러: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"문서 분석 중 오류 발생: {str(e)}"
        )


@app.post("/api/v1/analyze/raw")
async def raw_analysis(request: AnalysisRequest):
    """
    원본 출력만 반환 (파싱 없이)
    
    빠른 테스트용
    """
    try:
        if not request.sources:
            raise HTTPException(
                status_code=400,
                detail="최소 1개 이상의 문서가 필요합니다"
            )
        
        # SourceDocument 변환
        sources = []
        for i, source_req in enumerate(request.sources):
            source_id = source_req.id or f"doc_{i+1}"
            source = SourceDocument(
                id=source_id,
                content=source_req.content,
                doc_type=source_req.doc_type,
                metadata=source_req.metadata
            )
            sources.append(source)
        
        # 분석 실행
        analyzer = DocumentAnalysisNode(model_name=request.model_name)
        result = analyzer.analyze_documents(sources)
        
        # 원본만 반환
        return {
            "success": True,
            "source_count": len(sources),
            "raw_output": result.metadata['raw_output']
        }
    
    except Exception as e:
        print(f"❌ 분석 에러: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"문서 분석 중 오류 발생: {str(e)}"
        )


# ============================================================================
# 개발용 실행
# ============================================================================

if __name__ == "__main__":
    import uvicorn
    
    print("="*80)
    print("🚀 Alan Document Lab - 문서 분석 API 서버")
    print("="*80)
    print("\nPhase 1: 텍스트 기반 분석")
    print("\n엔드포인트:")
    print("  - POST /api/v1/analyze       : 전체 분석")
    print("  - POST /api/v1/analyze/quick : 빠른 분석")
    print("  - POST /api/v1/analyze/raw   : 원본 출력만")
    print("\n문서:")
    print("  - http://localhost:8000/docs")
    print("\n" + "="*80)
    
    uvicorn.run(
        app,
        host="0.0.0.0",
        port=8000,
        reload=True
    )
