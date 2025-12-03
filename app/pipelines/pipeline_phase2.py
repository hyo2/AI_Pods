"""
Phase 2 파이프라인: 텍스트 → 분석 → 토픽 → 이미지
"""

from typing import List, Dict, Any, Optional
from dataclasses import asdict
import os
import json

from app.nodes.document_analysis_node import (
    DocumentAnalysisNode,
    SourceDocument,
    CompleteAnalysis
)
from app.nodes.topic_extraction_node import (
    TopicExtractionNode,
    ImageTopic
)
from app.nodes.image_generation_node import (
    ImageGenerationNode,
    GeneratedImage
)


class DocumentToImagePipeline:
    """문서에서 이미지까지 전체 파이프라인"""
    
    def __init__(
        self,
        output_dir: str = "./pipeline_output",
        analysis_model: str = "gemini-2.5-flash",
        topic_model: str = "gemini-2.5-flash",
        image_default_method: str = "gemini",
        credentials_path: str = "./vertex-ai-service-account.json"
    ):
        """
        Args:
            output_dir: 출력 디렉토리
            analysis_model: 분석용 Gemini 모델
            topic_model: 토픽 추출용 Gemini 모델
            image_default_method: 기본 이미지 생성 방법
            credentials_path: Vertex AI credentials
        """
        self.output_dir = output_dir
        self.credentials_path = credentials_path
        
        # 출력 디렉토리 생성
        os.makedirs(output_dir, exist_ok=True)
        os.makedirs(os.path.join(output_dir, "images"), exist_ok=True)
        os.makedirs(os.path.join(output_dir, "json"), exist_ok=True)
        
        # 노드 초기화
        print("🔧 파이프라인 초기화 중...")
        
        self.analysis_node = DocumentAnalysisNode(model_name=analysis_model)
        print("  ✅ 분석 노드")
        
        self.topic_node = TopicExtractionNode(model_name=topic_model)
        print("  ✅ 토픽 추출 노드")
        
        # ImagenService 초기화 (기존 서비스 사용)
        try:
            from app.services.imagen_service import ImagenService
            # 기존 ImagenService는 default_model 파라미터가 없을 수 있음
            imagen_service = ImagenService(
                project_id="alan-document-lab",
                credentials_path=credentials_path
            )
        except Exception as e:
            print(f"  ⚠️  ImagenService 초기화 실패: {e}")
            print(f"  ℹ️  기본 설정으로 계속 진행...")
            imagen_service = None
        
        self.image_node = ImageGenerationNode(
            imagen_service=imagen_service,
            output_dir=os.path.join(output_dir, "images"),
            default_method=image_default_method
        )
        print("  ✅ 이미지 생성 노드")
        
        print("✨ 파이프라인 준비 완료\n")
    
    def run(
        self,
        sources: List[SourceDocument],
        min_topics: int = 5,
        max_topics: int = 20,
        generation_strategy: str = "auto",
        save_intermediate: bool = True
    ) -> Dict[str, Any]:
        """
        전체 파이프라인 실행
        
        Args:
            sources: 입력 문서 리스트
            min_topics: 최소 토픽 개수
            max_topics: 최대 토픽 개수
            generation_strategy: 이미지 생성 전략
            save_intermediate: 중간 결과 저장 여부
        
        Returns:
            {
                "analysis": CompleteAnalysis,
                "topics": List[ImageTopic],
                "images": List[GeneratedImage],
                "paths": {
                    "analysis_json": str,
                    "topics_json": str,
                    "images_json": str,
                    "gallery_html": str
                }
            }
        """
        print("="*80)
        print("🚀 파이프라인 시작")
        print("="*80)
        print(f"\n입력 문서: {len(sources)}개")
        print(f"토픽 범위: {min_topics} ~ {max_topics}개")
        print(f"생성 전략: {generation_strategy}")
        print()
        
        # ====================================================================
        # Step 1: 문서 분석
        # ====================================================================
        print("\n" + "="*80)
        print("📊 Step 1: 문서 분석")
        print("="*80)
        
        analysis_result = self.analysis_node.analyze_documents(sources)
        
        if save_intermediate:
            analysis_path = os.path.join(self.output_dir, "json", "01_analysis.json")
            with open(analysis_path, 'w', encoding='utf-8') as f:
                json.dump(asdict(analysis_result), f, ensure_ascii=False, indent=2)
            print(f"💾 분석 결과 저장: {analysis_path}")
        
        # ====================================================================
        # Step 2: 토픽 추출
        # ====================================================================
        print("\n" + "="*80)
        print("🔍 Step 2: 토픽 추출")
        print("="*80)
        
        topics = self.topic_node.extract_topics_from_analysis(
            asdict(analysis_result),
            min_topics=min_topics,
            max_topics=max_topics
        )
        
        if not topics:
            print("⚠️  토픽이 추출되지 않았습니다. 파이프라인 중단.")
            return {
                "analysis": analysis_result,
                "topics": [],
                "images": [],
                "paths": {}
            }
        
        # 토픽 요약 출력
        from app.nodes.topic_extraction_node import print_topics_summary
        print_topics_summary(topics)
        
        if save_intermediate:
            topics_path = os.path.join(self.output_dir, "json", "02_topics.json")
            with open(topics_path, 'w', encoding='utf-8') as f:
                topics_dict = [asdict(t) for t in topics]
                json.dump(topics_dict, f, ensure_ascii=False, indent=2)
            print(f"\n💾 토픽 저장: {topics_path}")
        
        # ====================================================================
        # Step 3: 이미지 생성
        # ====================================================================
        print("\n" + "="*80)
        print("🎨 Step 3: 이미지 생성")
        print("="*80)
        
        images = self.image_node.generate_images_from_topics(
            topics,
            strategy=generation_strategy
        )
        
        if not images:
            print("⚠️  이미지가 생성되지 않았습니다.")
            
            paths = {
                "analysis_json": os.path.join(self.output_dir, "json", "01_analysis.json") if save_intermediate else None,
                "topics_json": os.path.join(self.output_dir, "json", "02_topics.json") if save_intermediate else None,
                "images_json": None,
                "gallery_html": None
            }
            
            return {
                "analysis": analysis_result,
                "topics": topics,
                "images": [],
                "paths": paths
            }
        
        # 이미지 요약 출력
        from app.nodes.image_generation_node import print_generation_summary
        print_generation_summary(images)
        
        if save_intermediate:
            images_path = os.path.join(self.output_dir, "json", "03_images.json")
            with open(images_path, 'w', encoding='utf-8') as f:
                images_dict = [asdict(img) for img in images]
                json.dump(images_dict, f, ensure_ascii=False, indent=2)
            print(f"\n💾 이미지 정보 저장: {images_path}")
        
        # ====================================================================
        # Step 4: 갤러리 생성
        # ====================================================================
        print("\n" + "="*80)
        print("🌐 Step 4: 갤러리 생성")
        print("="*80)
        
        from app.nodes.image_generation_node import create_image_gallery_html
        
        gallery_path = os.path.join(self.output_dir, "gallery.html")
        create_image_gallery_html(images, gallery_path)
        
        # ====================================================================
        # 최종 결과
        # ====================================================================
        print("\n" + "="*80)
        print("✨ 파이프라인 완료!")
        print("="*80)
        
        paths = {
            "analysis_json": os.path.join(self.output_dir, "json", "01_analysis.json") if save_intermediate else None,
            "topics_json": os.path.join(self.output_dir, "json", "02_topics.json") if save_intermediate else None,
            "images_json": os.path.join(self.output_dir, "json", "03_images.json") if save_intermediate else None,
            "gallery_html": gallery_path
        }
        
        print(f"\n📁 출력 폴더: {self.output_dir}")
        print(f"  - 이미지: {os.path.join(self.output_dir, 'images')}/")
        print(f"  - JSON: {os.path.join(self.output_dir, 'json')}/")
        print(f"  - 갤러리: {gallery_path}")
        
        print(f"\n📊 결과 요약:")
        print(f"  - 분석된 문서: {len(sources)}개")
        print(f"  - 추출된 토픽: {len(topics)}개")
        print(f"  - 생성된 이미지: {len(images)}개")
        
        return {
            "analysis": analysis_result,
            "topics": topics,
            "images": images,
            "paths": paths
        }
    
    def run_from_texts(
        self,
        texts: List[str],
        **kwargs
    ) -> Dict[str, Any]:
        """
        텍스트 리스트에서 직접 실행
        
        Args:
            texts: 텍스트 리스트
            **kwargs: run() 메서드 인자
        
        Returns:
            run() 결과
        """
        sources = []
        for i, text in enumerate(texts):
            source = SourceDocument(
                id=f"doc_{i+1}",
                content=text,
                doc_type="text"
            )
            sources.append(source)
        
        return self.run(sources, **kwargs)


# ============================================================================
# 편의 함수
# ============================================================================

def quick_pipeline(
    text: str,
    output_dir: str = "./quick_output",
    generation_strategy: str = "auto"
) -> Dict[str, Any]:
    """
    빠른 단일 텍스트 파이프라인
    
    Args:
        text: 입력 텍스트
        output_dir: 출력 디렉토리
        generation_strategy: 생성 전략
    
    Returns:
        파이프라인 결과
    """
    import vertexai
    
    # Vertex AI 초기화
    vertexai.init(
        project="alan-document-lab",
        location="us-central1"
    )
    
    # 파이프라인 실행
    pipeline = DocumentToImagePipeline(output_dir=output_dir)
    
    sources = [SourceDocument(id="quick_doc", content=text, doc_type="text")]
    
    return pipeline.run(sources, generation_strategy=generation_strategy)


def batch_pipeline(
    texts: List[str],
    output_dir: str = "./batch_output",
    generation_strategy: str = "auto"
) -> Dict[str, Any]:
    """
    배치 텍스트 파이프라인
    
    Args:
        texts: 텍스트 리스트
        output_dir: 출력 디렉토리
        generation_strategy: 생성 전략
    
    Returns:
        파이프라인 결과
    """
    import vertexai
    
    vertexai.init(
        project="alan-document-lab",
        location="us-central1"
    )
    
    pipeline = DocumentToImagePipeline(output_dir=output_dir)
    
    return pipeline.run_from_texts(texts, generation_strategy=generation_strategy)
