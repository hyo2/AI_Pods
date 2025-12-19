"""
Metadata Generator Node
=======================

입력:
- main_file: 주강의자료 (1개, 필수)
- aux_files: 보조자료 (0~3개, 선택)

출력:
- metadata.json (이미지 설명 포함, 파일 저장 안 함)

통합:
- DocumentConverterNode: PDF 변환
- ImprovedHybridFilterPipeline: 이미지 필터링
- TextExtractor: 페이지별 텍스트 추출
- ImageDescriptionGenerator: 이미지 상세 설명
"""

import os
import json
import tempfile
from pathlib import Path
from typing import List, Optional, Dict, Any
from datetime import datetime
import pdfplumber

# 기존 노드 임포트
from .document_converter_node import DocumentConverterNode
from .improved_hybrid_filter import (
    ImprovedHybridFilterPipeline,
    UniversalImageExtractor,
    ImageMetadata,
    model
)

from vertexai.generative_models import Part


class TextExtractor:
    """PDF에서 페이지별 텍스트 추출 + 마커 삽입"""
    
    def extract_with_markers(
        self, 
        pdf_path: str, 
        prefix: str = "MAIN"
    ) -> Dict[str, Any]:
        """
        PDF에서 페이지별 텍스트 추출 + 마커 삽입
        
        Args:
            pdf_path: PDF 파일 경로
            prefix: 페이지 마커 접두사 (MAIN, SUPP1, SUPP2, SUPP3)
        
        Returns:
            {
                "full_text": "[MAIN-PAGE 1: 제목]\n내용...",
                "total_pages": 21
            }
        """
        pages_text = []
        total_pages = 0
        
        with pdfplumber.open(pdf_path) as pdf:
            total_pages = len(pdf.pages)
            
            for page_num, page in enumerate(pdf.pages, 1):
                # 페이지 텍스트 추출
                text = page.extract_text() or ""
                
                # 페이지 제목 추출 (첫 줄 또는 처음 50자)
                lines = text.split('\n')
                title = lines[0][:50] if lines and lines[0].strip() else f"Page {page_num}"
                
                # 페이지 마커 + 내용
                pages_text.append(f"[{prefix}-PAGE {page_num}: {title}]")
                pages_text.append(text)
                pages_text.append("")  # 페이지 간 구분
        
        return {
            "full_text": "\n".join(pages_text),
            "total_pages": total_pages
        }


class ImageDescriptionGenerator:
    """통과된 이미지에 대한 상세 설명 생성 (2-4문장)"""
    
    def generate_description(
        self, 
        image_bytes: bytes, 
        adjacent_text: str,
        keywords: List[str]
    ) -> str:
        """
        Vision API로 이미지 상세 설명 생성
        
        Args:
            image_bytes: 이미지 바이트 데이터
            adjacent_text: 주변 텍스트
            keywords: 문서 키워드
        
        Returns:
            2-4문장의 상세 설명
        """
        try:
            # MIME 타입 감지
            mime_type = self._get_mime_type(image_bytes)
            image_part = Part.from_data(data=image_bytes, mime_type=mime_type)
            
            keyword_context = ', '.join(keywords[:10]) if keywords else "일반 학습 내용"
            
            prompt = f"""
이 이미지를 2-4문장으로 설명하세요.

강의 주제: {keyword_context}
주변 텍스트: "{adjacent_text}"

설명에 포함할 내용:
1. 이미지가 나타내는 주제/개념 (1문장)
2. 주요 구성 요소 2-3개 (1-2문장)
3. 핵심 정보나 패턴 (1문장)

제외할 내용:
- 세부 요소 전체 나열
- 불필요한 추측이나 해석

출력: 명확하고 간결한 2-4문장만.
"""
            
            response = model.generate_content([image_part, prompt])
            return response.text.strip()
            
        except Exception as e:
            return f"이미지 설명 생성 실패: {str(e)}"
    
    def _get_mime_type(self, image_bytes: bytes) -> str:
        """이미지 바이너리에서 MIME 타입 감지"""
        if image_bytes.startswith(b'\xff\xd8'):
            return "image/jpeg"
        elif image_bytes.startswith(b'\x89PNG\r\n\x1a\n'):
            return "image/png"
        elif image_bytes.startswith(b'GIF87a') or image_bytes.startswith(b'GIF89a'):
            return "image/gif"
        elif image_bytes.startswith(b'RIFF') and image_bytes[8:12] == b'WEBP':
            return "image/webp"
        return "image/png"


class MetadataGenerator:
    """
    메타데이터 생성 노드
    
    주강의자료 + 보조자료 → metadata.json
    """
    
    def __init__(self):
        self.converter = None
        self.text_extractor = TextExtractor()
        self.image_filter = ImprovedHybridFilterPipeline(auto_extract_keywords=True)
        self.image_describer = ImageDescriptionGenerator()
    
    def _extract_page_title(self, slide_title: str, adjacent_text: str) -> str:
        """
        의미있는 페이지 제목 추출
        
        1순위: slide.title (있고 의미있으면)
        2순위: adjacent_text 첫 줄
        3순위: "페이지 제목 없음"
        
        Args:
            slide_title: PPTX의 slide.title
            adjacent_text: 슬라이드 전체 텍스트
        
        Returns:
            추출된 페이지 제목 (최대 50자)
        """
        # 1. slide.title이 있고 의미있으면
        if slide_title and slide_title.strip() and slide_title.lower() != "no title":
            return slide_title.strip()[:50]
        
        # 2. adjacent_text에서 첫 번째 의미있는 줄 추출
        if adjacent_text:
            lines = adjacent_text.strip().split('\n')
            for line in lines:
                line = line.strip()
                # 의미있는 줄: 3자 이상, ☞로 시작 안 함, 너무 짧지 않음
                if len(line) > 3 and not line.startswith('☞'):
                    return line[:50]
        
        # 3. 그래도 없으면
        return "페이지 제목 없음"
    
    def generate(
        self,
        main_file: str,
        aux_files: Optional[List[str]] = None,
        output_path: str = "output/metadata.json"
    ) -> str:
        """
        메타데이터 생성
        
        Args:
            main_file: 주강의자료 경로
            aux_files: 보조자료 경로 리스트 (0~3개)
            output_path: 출력 JSON 경로
        
        Returns:
            생성된 metadata.json 경로
        """
        print(f"\n{'='*120}")
        print(f"🎯 메타데이터 생성 시작")
        print(f"{'='*120}")
        print(f"주강의자료: {main_file}")
        if aux_files:
            print(f"보조자료: {len(aux_files)}개")
            for i, supp in enumerate(aux_files, 1):
                print(f"  {i}. {supp}")
        print(f"{'='*120}\n")
        
        # 임시 디렉토리 사용
        with tempfile.TemporaryDirectory() as temp_dir:
            self.converter = DocumentConverterNode(output_dir=temp_dir)
            
            # 1. 주강의자료 처리
            print("📄 [1/3] 주강의자료 처리 중...")
            main_metadata = self._process_main_source(main_file)
            
            # 2. 보조자료 처리
            print("\n📚 [2/3] 보조자료 처리 중...")
            aux_metadata = []
            if aux_files:
                for i, supp_file in enumerate(aux_files[:3], 1):  # 최대 3개
                    supp_meta = self._process_aux_source(supp_file, i)
                    aux_metadata.append(supp_meta)
            else:
                print("   ⚠️  보조자료 없음 (선택 사항)")
            
            # 3. 최종 메타데이터 구성
            print("\n🔧 [3/3] 메타데이터 통합 중...")
            metadata = {
                "metadata_version": "1.0",
                "created_at": datetime.now().isoformat(),
                "main_source": main_metadata,
                "aux_sources": aux_metadata
            }
            
            # 4. JSON 저장
            output_path = Path(output_path)
            output_path.parent.mkdir(parents=True, exist_ok=True)
            
            with open(output_path, 'w', encoding='utf-8') as f:
                json.dump(metadata, f, ensure_ascii=False, indent=2)
            
            print(f"\n{'='*120}")
            print(f"✅ 메타데이터 생성 완료!")
            print(f"{'='*120}")
            print(f"📁 출력 파일: {output_path}")
            print(f"📊 주강의자료 페이지: {main_metadata['total_pages']}개")
            print(f"🖼️  필터링된 이미지: {len(main_metadata['filtered_images'])}개")
            if aux_metadata:
                total_supp_pages = sum(s['total_pages'] for s in aux_metadata)
                print(f"📚 보조자료 페이지: {total_supp_pages}개")
            print(f"{'='*120}\n")
            
            return str(output_path)
    
    def _process_main_source(self, file_path: str) -> Dict[str, Any]:
        """
        주강의자료 처리
        - PDF 변환
        - 텍스트 추출
        - 이미지 필터링
        - 이미지 설명 생성
        """
        file_path = Path(file_path)
        file_type = file_path.suffix.lower().replace('.', '')
        
        print(f"   📄 파일: {file_path.name} ({file_type})")
        
        # 1. PDF 변환 (텍스트 추출용)
        print(f"   🔄 PDF 변환 중... (텍스트 추출용)")
        pdf_path = self.converter.convert(str(file_path))
        
        # 2. 텍스트 추출 (페이지 마커 포함)
        print(f"   📝 텍스트 추출 중...")
        text_data = self.text_extractor.extract_with_markers(pdf_path, prefix="MAIN")
        
        # 3. 이미지 필터링 (형식별 처리)
        print(f"   🖼️  이미지 필터링 중...")
        
        if file_type == 'pptx':
            # ✅ PPTX: 원본에서 직접 추출 (품질 최상)
            print(f"      → PPTX 원본에서 직접 추출")
            
            # 키워드 추출
            self.image_filter.extract_keywords_from_document(str(file_path))
            keywords = self.image_filter.document_keywords
            
            # 이미지 메타데이터 추출 (python-pptx)
            all_images = self._extract_images_from_pptx(str(file_path))
            
        elif file_type in ['docx', 'pdf']:
            # ✅ DOCX/PDF: PDF에서 추출
            print(f"      → PDF에서 이미지 추출 (pdfplumber + pdf2image)")
            
            # 키워드 추출 (변환된 PDF 사용)
            self.image_filter.extract_keywords_from_document(pdf_path)
            keywords = self.image_filter.document_keywords
            
            # 이미지 메타데이터 추출 (PDF)
            extractor = UniversalImageExtractor()
            all_images = extractor.extract(pdf_path)
        
        else:
            print(f"   ⚠️  지원하지 않는 형식: {file_type}")
            all_images = []
            keywords = []
        
        # 4. 필터링 실행
        filtered_images = []
        if all_images:
            print(f"   🔍 {len(all_images)}개 이미지 발견, 필터링 시작...")
            
            for img_meta in all_images:
                decision, reason = self.image_filter.step1_rule_check(img_meta)
                
                if decision == "INCLUDE":
                    img_meta.is_core_content = True
                    img_meta.filter_reason = reason
                    filtered_images.append(img_meta)
                    
                elif decision == "PENDING":
                    ai_result = self.image_filter.step2_gemini_check(img_meta)
                    if ai_result.upper().startswith("KEEP"):
                        img_meta.is_core_content = True
                        img_meta.filter_reason = ai_result
                        filtered_images.append(img_meta)
            
            print(f"   ✅ 필터링 완료: {len(filtered_images)}개 선택 ({len(all_images) - len(filtered_images)}개 제외)")
        
        # 5. 통과된 이미지 상세 설명 생성
        filtered_image_metadata = []
        if filtered_images:
            print(f"   📝 이미지 설명 생성 중... (0/{len(filtered_images)})", end='', flush=True)
            
            for i, img_meta in enumerate(filtered_images, 1):
                # 이미지 설명 생성
                description = self.image_describer.generate_description(
                    img_meta.image_bytes,
                    img_meta.adjacent_text,
                    keywords
                )
                
                # 페이지 제목 추출 (개선된 로직)
                page_title = self._extract_page_title(
                    img_meta.slide_title,
                    img_meta.adjacent_text
                )
                
                filtered_image_metadata.append({
                    "image_id": img_meta.image_id.replace("S", "MAIN_P").replace("P", "MAIN_P"),  # S02 or P02 → MAIN_P02
                    "page_number": img_meta.slide_number,
                    "page_title": page_title,
                    "description": description,
                    "filter_stage": "1차 (Rule)" if "Rule" in img_meta.filter_reason else "2차 (AI)",
                    "area_percentage": img_meta.area_percentage
                })
                
                print(f"\r   📝 이미지 설명 생성 중... ({i}/{len(filtered_images)})", end='', flush=True)
            
            print()  # 줄바꿈
        
        # 6. 통계 생성
        total_images = len(all_images)
        passed_images = len(filtered_images)
        
        return {
            "role": "main",
            "filename": file_path.name,
            "file_type": file_type,
            "total_pages": text_data['total_pages'],
            "content": {
                "full_text": text_data['full_text']
            },
            "filtered_images": filtered_image_metadata,
            "statistics": {
                "total_images_found": total_images,
                "images_passed": passed_images,
                "filter_rate": passed_images / total_images if total_images > 0 else 0
            }
        }
    
    def _process_aux_source(self, file_path: str, order: int) -> Dict[str, Any]:
        """
        보조자료 처리
        - PDF 변환
        - 텍스트만 추출 (이미지 무시)
        """
        file_path = Path(file_path)
        file_type = file_path.suffix.lower().replace('.', '')
        
        print(f"   📚 보조자료 {order}: {file_path.name} ({file_type})")
        
        # 1. PDF 변환
        print(f"      🔄 PDF 변환 중...")
        pdf_path = self.converter.convert(str(file_path))
        
        # 2. 텍스트만 추출
        print(f"      📝 텍스트 추출 중...")
        text_data = self.text_extractor.extract_with_markers(pdf_path, prefix=f"SUPP{order}")
        
        print(f"      ✅ 완료 ({text_data['total_pages']}페이지)")
        
        return {
            "order": order,
            "filename": file_path.name,
            "file_type": file_type,
            "total_pages": text_data['total_pages'],
            "content": {
                "full_text": text_data['full_text']
            }
        }
    
    def _extract_images_from_pptx(self, pptx_path: str) -> List[ImageMetadata]:
        """PPTX에서 이미지 메타데이터 추출 (UniversalImageExtractor 사용)"""
        extractor = UniversalImageExtractor()
        return extractor.extract(pptx_path)


# CLI 인터페이스
if __name__ == "__main__":
    import sys
    
    print("\n" + "="*120)
    print("🎯 Metadata Generator Node")
    print("="*120)
    
    # 사용법
    if len(sys.argv) < 2:
        print("\n사용법:")
        print("  python metadata_generator_node.py <주강의자료> [보조1] [보조2] [보조3]")
        print("\n예시:")
        print("  # 주자료만")
        print("  python metadata_generator_node.py 중등국어1.pptx")
        print("\n  # 주자료 + 보조 1개")
        print("  python metadata_generator_node.py 중등국어1.pptx 보조자료.docx")
        print("\n  # 주자료 + 보조 3개 (최대)")
        print("  python metadata_generator_node.py 중등국어1.pptx 보조1.docx 보조2.pdf 보조3.docx")
        print("\n✅ 지원 형식: PPTX, DOCX, PDF")
        print("="*120 + "\n")
        sys.exit(1)
    
    # 파일 경로 파싱
    main_file = sys.argv[1]
    aux_files = sys.argv[2:5] if len(sys.argv) > 2 else None  # 최대 3개
    
    # 파일 존재 확인
    if not os.path.exists(main_file):
        print(f"\n❌ 주강의자료를 찾을 수 없습니다: {main_file}")
        sys.exit(1)
    
    if aux_files:
        for supp in aux_files:
            if not os.path.exists(supp):
                print(f"\n❌ 보조자료를 찾을 수 없습니다: {supp}")
                sys.exit(1)
    
    # 메타데이터 생성
    try:
        generator = MetadataGenerator()
        output_path = generator.generate(
            main_file=main_file,
            aux_files=aux_files,
            output_path="output/metadata.json"
        )
        
        print(f"✅ 성공!")
        print(f"📁 {output_path}")
        
    except Exception as e:
        print(f"\n❌ 에러 발생: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)