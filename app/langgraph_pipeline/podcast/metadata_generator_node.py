"""
Metadata Generator Node
=======================

입력:
- primary_file: 주강의자료 (1개, 필수)
- supplementary_files: 보조자료 (0~3개, 선택)

출력:
- metadata.json (이미지 설명 포함, 파일 저장 안 함)

통합:
- DocumentConverterNode: PDF 변환 + TXT/URL 처리
- ImprovedHybridFilterPipeline: 이미지 필터링
- TextExtractor: 페이지별 텍스트 추출
- ImageDescriptionGenerator: 이미지 상세 설명
"""

import os
import json
import tempfile
import hashlib
from pathlib import Path
from typing import List, Optional, Dict, Any
from datetime import datetime

# OCR 로그 억제 (import 전에 설정)
os.environ['FLAGS_log_level'] = '3'  # PaddlePaddle 로그 레벨
os.environ['PPOCR_SHOW_LOG'] = 'False'  # PaddleOCR 로그 억제

try:
    import fitz  # PyMuPDF
    PYMUPDF_AVAILABLE = True
except ImportError:
    import pdfplumber
    PYMUPDF_AVAILABLE = False

# OCR 라이브러리
try:
    from paddleocr import PaddleOCR
    OCR_AVAILABLE = True
    ocr_engine = PaddleOCR(lang='korean', use_textline_orientation=True)
except ImportError:
    OCR_AVAILABLE = False
    ocr_engine = None
except Exception as e:
    print(f"⚠️  PaddleOCR 초기화 실패: {e}")
    OCR_AVAILABLE = False
    ocr_engine = None

# 기존 노드 임포트
from .document_converter_node import DocumentConverterNode, DocumentType
from .improved_hybrid_filter import (
    ImprovedHybridFilterPipeline,
    UniversalImageExtractor,
    ImageMetadata,
    get_global_model
)

from vertexai.generative_models import Part


class TextExtractor:
    """PDF에서 페이지별 텍스트 추출 + 마커 삽입 (OCR 지원)"""
    
    def __init__(self):
        """TextExtractor 초기화"""
        self.ocr_enabled = OCR_AVAILABLE
        self.min_text_length = 100  # OCR 트리거 기준 (문자 수)
    
    def _perform_ocr(self, page) -> str:
        """
        페이지에 OCR 수행 (PaddleOCR / PaddleX 계열 호환)
        """
        if not self.ocr_enabled or ocr_engine is None:
            return ""

        try:
            pix = page.get_pixmap(dpi=220)  # 150 -> 220 권장(스캔본)
            img_data = pix.tobytes("png")

            import numpy as np
            from PIL import Image, ImageOps
            from io import BytesIO

            img = Image.open(BytesIO(img_data)).convert("RGB")
            img = ImageOps.autocontrast(img)
            img_array = np.array(img)

            result = None

            # 1) PaddleOCR 표준 API (cls 지원/미지원 모두 대응)
            try:
                # 일부 버전은 cls 인자를 받음
                result = ocr_engine.ocr(img_array, cls=True)
            except TypeError:
                # 일부 버전은 cls를 안 받음
                result = ocr_engine.ocr(img_array)

            # 2) 혹시 ocr() 자체가 없거나 내부에서 predict 라우팅 문제면 predict로 폴백 (cls 없이)
            if result is None and hasattr(ocr_engine, "predict"):
                result = ocr_engine.predict(img_array)

            # -------- 결과 파싱(버전별 포맷 대응) --------
            lines: list[str] = []

            # PaddleOCR 일반 포맷: result[0] = [ [box, (text, score)], ... ]
            if isinstance(result, list) and result:
                first = result[0] if isinstance(result[0], list) else result

                if isinstance(first, list):
                    for item in first:
                        if not item or len(item) < 2:
                            continue
                        # item[1] could be (text, score)
                        meta = item[1]
                        if isinstance(meta, (list, tuple)) and meta:
                            text = meta[0]
                            if isinstance(text, str):
                                text = text.strip()
                                # ✅ 한 글자 잡음 제거
                                if len(text) <= 1:
                                    continue
                                lines.append(text)

            # PaddleX predict 포맷이 dict/list로 오는 경우도 대비
            if not lines and isinstance(result, dict):
                # 예: {"rec_texts": [...]} 같은 형태
                rec_texts = result.get("rec_texts") or result.get("texts")
                if isinstance(rec_texts, list):
                    for t in rec_texts:
                        if isinstance(t, str):
                            t = t.strip()
                            if len(t) <= 1:
                                continue
                            lines.append(t)

            return "\n".join(lines).strip()

        except Exception as e:
            print(f"      ⚠️  OCR 실패: {e}")
            return ""

    
    def extract_with_markers(
        self, 
        pdf_path: str, 
        prefix: str = "MAIN"
    ) -> Dict[str, Any]:
        """
        PDF에서 페이지별 텍스트 추출 + 마커 삽입
        PyMuPDF 우선, 없으면 pdfplumber 사용
        텍스트 부족 시 OCR 자동 수행
        
        Args:
            pdf_path: PDF 파일 경로
            prefix: 페이지 마커 접두사 (MAIN, SUPP1, SUPP2, SUPP3)
        
        Returns:
            {
                "full_text": "[MAIN-PAGE 1: 제목]\n내용...",
                "total_pages": 21
            }
        """
        if PYMUPDF_AVAILABLE:
            return self._extract_with_pymupdf(pdf_path, prefix)
        else:
            return self._extract_with_pdfplumber(pdf_path, prefix)
    
    def _extract_with_pymupdf(self, pdf_path: str, prefix: str) -> Dict[str, Any]:
        """PyMuPDF로 텍스트 추출 (OCR 지원)"""
        pages_text = []
        total_pages = 0
        ocr_count = 0
        
        try:
            doc = fitz.open(pdf_path)
            total_pages = len(doc)
            
            print(f"   📄 텍스트 추출 중... (OCR {'활성화' if self.ocr_enabled else '비활성화'})")
            
            for page_num in range(total_pages):
                page = doc[page_num]
                text = page.get_text()
                text_length = len(text.strip())
                
                if text_length < self.min_text_length and self.ocr_enabled:
                    print(f"      → 페이지 {page_num + 1}: 텍스트 부족 ({text_length}자) → OCR 수행")
                    ocr_text = self._perform_ocr(page)
                    
                    if ocr_text:
                        text = ocr_text
                        ocr_count += 1
                        print(f"         ✅ OCR 완료 ({len(ocr_text)}자 추출)")
                    else:
                        print(f"         ⚠️  OCR 실패, 원본 텍스트 사용")
                
                lines = text.split('\n')
                title = lines[0][:50] if lines and lines[0].strip() else f"Page {page_num + 1}"
                
                pages_text.append(f"[{prefix}-PAGE {page_num + 1}: {title}]")
                pages_text.append(text)
                pages_text.append("")
            
            doc.close()
            
            if ocr_count > 0:
                print(f"   ✅ OCR 처리 완료: {ocr_count}개 페이지")
        
        except Exception as e:
            print(f"   ❌ PDF 텍스트 추출 실패: {e}")
            return {"full_text": "", "total_pages": 0}
        
        return {
            "full_text": "\n".join(pages_text),
            "total_pages": total_pages
        }
    
    def _extract_with_pdfplumber(self, pdf_path: str, prefix: str) -> Dict[str, Any]:
        """pdfplumber로 텍스트 추출 (fallback)"""
        pages_text = []
        total_pages = 0
        
        try:
            with pdfplumber.open(pdf_path) as pdf:
                total_pages = len(pdf.pages)
                
                for page_num, page in enumerate(pdf.pages, 1):
                    text = page.extract_text() or ""
                    
                    lines = text.split('\n')
                    title = lines[0][:50] if lines and lines[0].strip() else f"Page {page_num}"
                    
                    pages_text.append(f"[{prefix}-PAGE {page_num}: {title}]")
                    pages_text.append(text)
                    pages_text.append("")
        
        except Exception as e:
            print(f"   ❌ PDF 텍스트 추출 실패: {e}")
            return {"full_text": "", "total_pages": 0}
        
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
        keywords: List[str],
        max_retries=3
    ) -> str:
        """
        Vision API로 이미지 상세 설명 생성
        재시도 로직 포함 (429 Rate Limit 대응)
        """
        import time
        
        for attempt in range(max_retries):
            try:
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
                model = get_global_model()
                if model is None:
                    return "이미지 설명 생성 실패: Gemini unavailable (no credentials)"

                response = model.generate_content([image_part, prompt])
                description = response.text.strip()
                return description
                
            except Exception as e:
                error_msg = str(e)
                
                if "429" in error_msg or "Resource exhausted" in error_msg:
                    if attempt < max_retries - 1:
                        wait_time = (attempt + 1) * 3
                        print(f"      ⚠️  Rate Limit, {wait_time}초 대기 중...", end='', flush=True)
                        time.sleep(wait_time)
                        print(" 재시도")
                        continue
                    else:
                        return "이미지 설명 생성 실패: API rate limit exceeded"
                else:
                    return f"이미지 설명 생성 실패: {error_msg}"
        
        return "이미지 설명 생성 실패: Failed after all retries"
    
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

        # 이미지 캡션 캐시 (메모리)
        self._caption_cache: Dict[str, str] = {}

    # ----------------------------
    # 이미지 캡션 최적화 유틸
    # ----------------------------
    def _cache_key(self, image_bytes: bytes) -> str:
        """이미지 바이트 기반의 안정적 캐시 키(SHA256)."""
        return hashlib.sha256(image_bytes).hexdigest()

    def _load_caption_cache(self, cache_path: Path) -> None:
        """디스크 캐시 로드(선택)."""
        try:
            if cache_path.exists():
                with open(cache_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                if isinstance(data, dict):
                    # value는 str만
                    self._caption_cache.update({k: str(v) for k, v in data.items()})
        except Exception as e:
            print(f"   ⚠️  캡션 캐시 로드 실패(무시): {e}")

    def _save_caption_cache(self, cache_path: Path) -> None:
        """디스크 캐시 저장(선택)."""
        try:
            cache_path.parent.mkdir(parents=True, exist_ok=True)
            with open(cache_path, "w", encoding="utf-8") as f:
                json.dump(self._caption_cache, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"   ⚠️  캡션 캐시 저장 실패(무시): {e}")

    def _score_image(self, img_meta: ImageMetadata, keywords: List[str]) -> float:
        """캡션 생성 우선순위 점수(높을수록 우선)."""
        area = float(getattr(img_meta, "area_percentage", 0.0) or 0.0)
        adj = getattr(img_meta, "adjacent_text", "") or ""
        adj_len = min(len(adj.strip()), 800)

        # rule 단계 통과는 신뢰도가 높으므로 가산
        reason = getattr(img_meta, "filter_reason", "") or ""
        stage_bonus = 12.0 if "Rule" in reason or "INCLUDE" in reason else 0.0

        # 주변 텍스트가 많을수록(설명할 소재가 많을수록) 가산
        text_bonus = (adj_len / 800.0) * 10.0

        # 키워드가 실제로 주변 텍스트에 등장하면 약간 가산
        kw_bonus = 0.0
        if keywords and adj:
            hits = 0
            lower = adj.lower()
            for kw in keywords[:8]:
                if kw and kw.lower() in lower:
                    hits += 1
            kw_bonus = min(hits * 2.0, 8.0)

        # 면적 기반이 기본(0~100)
        return area + stage_bonus + text_bonus + kw_bonus

    def _get_image_policy(
        self,
        total_images: int,
        filtered_images: int,
        total_pages: int,
    ) -> Dict[str, Any]:
        """UI 변경 없이 자동 FAST 전환을 위한 정책."""
        auto_fast = (total_images >= 500) or (filtered_images >= 30)

        # 페이지당 제한 (PPT→PDF에서 폭발 방지)
        per_page_limit = 1 if auto_fast else 2

        # 최종 캡션 생성 상한 (full에서도 안전장치로 상한 유지)
        # - 페이지 수가 매우 많으면 약간 늘리되, 무제한은 금지
        base_max = 18 if auto_fast else 30
        if total_pages >= 120:
            base_max += 4
        max_caption_images = min(base_max, 40)

        return {
            "auto_fast": auto_fast,
            "per_page_limit": per_page_limit,
            "max_caption_images": max_caption_images,
        }

    def _select_images_for_caption(
        self,
        images: List[ImageMetadata],
        keywords: List[str],
        per_page_limit: int,
        max_caption_images: int,
    ) -> List[ImageMetadata]:
        """페이지 분산 + 스코어링 기반으로 캡션 생성 대상을 선별."""
        if not images:
            return []

        # 1) 페이지별로 스코어 계산 후 상위 per_page_limit만 남김
        by_page: Dict[int, List[ImageMetadata]] = {}
        for img in images:
            page = int(getattr(img, "slide_number", 0) or 0)
            by_page.setdefault(page, []).append(img)

        pruned: List[ImageMetadata] = []
        for page, imgs in by_page.items():
            imgs_sorted = sorted(imgs, key=lambda x: self._score_image(x, keywords), reverse=True)
            pruned.extend(imgs_sorted[:per_page_limit])

        if len(pruned) <= max_caption_images:
            # 이미 충분히 작으면 그대로 (단, 점수순 정렬)
            return sorted(pruned, key=lambda x: self._score_image(x, keywords), reverse=True)

        # 2) 페이지 분산을 위해 라운드로빈으로 상위 선택
        page_queues: Dict[int, List[ImageMetadata]] = {}
        for img in pruned:
            page = int(getattr(img, "slide_number", 0) or 0)
            page_queues.setdefault(page, []).append(img)

        for page in list(page_queues.keys()):
            page_queues[page] = sorted(page_queues[page], key=lambda x: self._score_image(x, keywords), reverse=True)

        selected: List[ImageMetadata] = []
        page_selected_count: Dict[int, int] = {p: 0 for p in page_queues}

        while len(selected) < max_caption_images and any(page_queues.values()):
            # 아직 선택이 적은 페이지를 우선
            pages = sorted(page_queues.keys(), key=lambda p: page_selected_count.get(p, 0))
            picked_any = False
            for p in pages:
                q = page_queues.get(p) or []
                if q:
                    selected.append(q.pop(0))
                    page_selected_count[p] = page_selected_count.get(p, 0) + 1
                    picked_any = True
                    if len(selected) >= max_caption_images:
                        break
            if not picked_any:
                break

        # 최종은 점수순으로 재정렬하지 않음(분산 유지)
        return selected
    
    def _extract_page_title(self, slide_title: str, adjacent_text: str) -> str:
        """의미있는 페이지 제목 추출"""
        if slide_title and slide_title.strip() and slide_title.lower() != "no title":
            return slide_title.strip()[:50]
        
        if adjacent_text:
            lines = adjacent_text.strip().split('\n')
            for line in lines:
                line = line.strip()
                if len(line) > 3 and not line.startswith('☞'):
                    return line[:50]
        
        return "페이지 제목 없음"
    
    def generate(
        self,
        primary_file: str,
        supplementary_files: Optional[List[str]] = None,
        output_path: str = "output/metadata.json"
    ) -> str:
        """메타데이터 생성"""
        print(f"\n{'='*120}")
        print(f"🎯 메타데이터 생성 시작")
        print(f"{'='*120}")
        print(f"주강의자료: {primary_file}")
        if supplementary_files:
            print(f"보조자료: {len(supplementary_files)}개")
            for i, supp in enumerate(supplementary_files, 1):
                print(f"  {i}. {supp}")
        print(f"{'='*120}\n")
        
        # (선택) 이미지 캡션 캐시를 디스크에 유지하여 데모 반복 시연 성능을 확보
        output_path_obj = Path(output_path)
        caption_cache_path = output_path_obj.parent / "image_caption_cache.json"
        self._load_caption_cache(caption_cache_path)

        with tempfile.TemporaryDirectory() as temp_dir:
            self.converter = DocumentConverterNode(output_dir=temp_dir)
            
            print("📄 [1/3] 주강의자료 처리 중...")
            primary_metadata = self._process_primary_source(primary_file)
            
            print("\n📚 [2/3] 보조자료 처리 중...")
            supplementary_metadata = []
            if supplementary_files:
                for i, supp_file in enumerate(supplementary_files[:3], 1):
                    try:
                        supp_meta = self._process_supplementary_source(supp_file, i)
                        supplementary_metadata.append(supp_meta)
                        print(f"   ✅ 보조자료 {i} 처리 성공")
                    except Exception as e:
                        print(f"   ⚠️ 보조자료 {i} 처리 실패 (계속 진행): {e}")
                        # 실패해도 다음 보조자료로 넘어감
            else:
                print("   ⚠️  보조자료 없음 (선택 사항)")
            
            print("\n🔧 [3/3] 메타데이터 통합 중...")
            metadata = {
                "metadata_version": "1.0",
                "created_at": datetime.now().isoformat(),
                "primary_source": primary_metadata,
                "supplementary_sources": supplementary_metadata
            }
            
            output_path = Path(output_path)
            output_path.parent.mkdir(parents=True, exist_ok=True)
            
            with open(output_path, 'w', encoding='utf-8') as f:
                json.dump(metadata, f, ensure_ascii=False, indent=2)

            # 캐시 저장 (실패해도 전체 결과에는 영향 없음)
            self._save_caption_cache(caption_cache_path)
            
            print(f"\n{'='*120}")
            print(f"✅ 메타데이터 생성 완료!")
            print(f"{'='*120}")
            print(f"📁 출력 파일: {output_path}")
            print(f"📊 주강의자료 페이지: {primary_metadata['total_pages']}개")
            print(f"🖼️  필터링된 이미지: {len(primary_metadata['filtered_images'])}개")
            if supplementary_metadata:
                total_supp_pages = sum(s['total_pages'] for s in supplementary_metadata)
                print(f"📚 보조자료 페이지: {total_supp_pages}개")
            print(f"{'='*120}\n")
            
            return str(output_path)
    
    def _process_primary_source(self, file_path: str) -> Dict[str, Any]:

        """
        주강의자료 처리
        ✅ TXT/URL 지원 추가 (수정됨)
        """
        file_path_str = str(file_path)
        # file_path = Path(file_path)
        
        # ✅ 원본 파일 타입 감지 (변환 전)
        if file_path_str.startswith(('http://', 'https://')):
            original_file_type = 'url'
            file_path_obj = None  # URL은 Path 객체 만들지 않음
            display_name = file_path_str[:50]
        else:
            file_path_obj = Path(file_path)
            original_file_type = file_path_obj.suffix.lower().replace('.', '')
            display_name = file_path_obj.name
        
        print(f"   📄 파일: {display_name} ({original_file_type})")
        
        # 1. 파일 변환 (TXT/URL도 PDF로 변환됨)
        print(f"   🔄 파일 처리 중...")
        processed_path = self.converter.convert(file_path_str)
        
        # ✅ 변환 후 파일은 항상 PDF임!
        processed_file_type = Path(processed_path).suffix.lower().replace('.', '')
        
        # 2. 텍스트 추출
        print(f"   📝 텍스트 추출 중...")
        
        # ✅ TXT/URL이었어도 이제는 PDF가 되었으므로 PDF 처리 로직 사용
        if original_file_type in ['txt', 'url']:
            # TXT/URL → PDF 변환됨 → PDF에서 텍스트 추출
            text_data = self.text_extractor.extract_with_markers(processed_path, prefix="MAIN")
            print(f"   ✅ 텍스트 추출 완료: {len(text_data['full_text'])}자")
        else:
            # 기존 PDF/PPTX/DOCX 처리
            text_data = self.text_extractor.extract_with_markers(processed_path, prefix="MAIN")
        
        # 3. 이미지 필터링
        print(f"   🖼️  이미지 처리 중...")
        
        filtered_images = []
        keywords = []
        
        # ✅ TXT/URL은 이미지 없음
        if original_file_type in ['txt', 'url']:
            print(f"      → TXT/URL은 이미지 없음, 건너뛰기")
            all_images = []
        
        elif original_file_type == 'pptx':
            print(f"      → PPTX 원본에서 직접 추출")
            self.image_filter.extract_keywords_from_document(file_path_str)
            keywords = self.image_filter.document_keywords
            all_images = self._extract_images_from_pptx(file_path_str)
            
        elif original_file_type in ['docx', 'pdf']:
            print(f"      → PDF에서 이미지 추출")
            self.image_filter.extract_keywords_from_document(processed_path)
            keywords = self.image_filter.document_keywords
            extractor = UniversalImageExtractor()
            all_images = extractor.extract(processed_path)
        
        else:
            print(f"   ⚠️  지원하지 않는 형식: {original_file_type}")
            all_images = []
        
        # 4. 필터링 실행
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

                    # step2_gemini_check가 (text, tokens, cost) 튜플을 반환하는 경우 대응
                    if isinstance(ai_result, tuple):
                        ai_result = ai_result[0]

                    if ai_result.upper().startswith("KEEP"):
                        img_meta.is_core_content = True
                        img_meta.filter_reason = ai_result
                        filtered_images.append(img_meta)
            
            print(f"   ✅ 필터링 완료: {len(filtered_images)}개 선택")

        # ✅ 이미지가 많은 자료(특히 PPT→PDF)에서 시간 폭발 방지용 자동 FAST 정책
        policy = self._get_image_policy(
            total_images=len(all_images),
            filtered_images=len(filtered_images),
            total_pages=int(text_data.get('total_pages', 0) or 0),
        )
        if filtered_images:
            mode_label = "FAST" if policy["auto_fast"] else "FULL"
            print(
                f"   ⚙️  이미지 캡션 정책: {mode_label} / "
                f"page_limit={policy['per_page_limit']} / "
                f"max_captions={policy['max_caption_images']}"
            )
        
        # 5. 이미지 설명 생성
        filtered_image_metadata = []
        
        if filtered_images:
            # 5-1) 캡션 생성 대상 선별(상한 + 페이지당 제한 + 스코어링)
            caption_targets = self._select_images_for_caption(
                images=filtered_images,
                keywords=keywords,
                per_page_limit=policy["per_page_limit"],
                max_caption_images=policy["max_caption_images"],
            )

            if len(caption_targets) < len(filtered_images):
                print(
                    f"   🧹 캡션 대상 축소: {len(filtered_images)} → {len(caption_targets)} "
                    f"(상한/페이지 제한 적용)"
                )

            print(f"   📝 이미지 설명 생성 중... (0/{len(caption_targets)})", end='', flush=True)

            for i, img_meta in enumerate(caption_targets, 1):
                # 5-2) 이미지 설명 캐시 재사용
                key = self._cache_key(img_meta.image_bytes)
                if key in self._caption_cache:
                    description = self._caption_cache[key]
                else:
                    description = self.image_describer.generate_description(
                        img_meta.image_bytes,
                        img_meta.adjacent_text,
                        keywords
                    )
                    # 항상 str만 저장
                    self._caption_cache[key] = str(description)
                
                page_title = self._extract_page_title(
                    img_meta.slide_title,
                    img_meta.adjacent_text
                )
                
                filtered_image_metadata.append({
                    "image_id": img_meta.image_id.replace("S", "MAIN_P").replace("P", "MAIN_P"),
                    "page_number": img_meta.slide_number,
                    "page_title": page_title,
                    "description": description,
                    "filter_stage": "1차 (Rule)" if "Rule" in img_meta.filter_reason else "2차 (AI)",
                    "area_percentage": img_meta.area_percentage
                })
                
                print(f"\r   📝 이미지 설명 생성 중... ({i}/{len(caption_targets)})", end='', flush=True)
            
            print()  # 줄바꿈
            
            # ✅ 최종 집계 출력
            print(f"\n   {'='*80}")
            print(f"   📊 이미지 설명 생성 완료")
            print(f"      - 처리된 이미지: {len(caption_targets)}개")
            print(f"   {'='*80}\n")

        # 6. 통계
        total_images = len(all_images)
        passed_images = len(filtered_images)
        
        return {
            "role": "main",
            "filename": display_name if original_file_type == 'url' else file_path_obj.name,
            "file_type": original_file_type,  # ✅ 원본 타입 저장
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
    
    def _process_supplementary_source(self, file_path: str, order: int) -> Dict[str, Any]:
        file_path_str = str(file_path)
        
        # ✅ URL과 파일 구분
        if file_path_str.startswith(('http://', 'https://')):
            file_type = 'url'
            display_name = 'Web Content'
        else:
            file_path_obj = Path(file_path)
            file_type = file_path_obj.suffix.lower().replace('.', '')
            display_name = file_path_obj.name
        
        print(f"   📚 보조자료 {order}: {display_name} ({file_type})")
        
        print(f"      🔄 PDF 변환 중...")
        pdf_path = self.converter.convert(file_path_str)  # ✅ 원본 문자열 그대로 전달
        
        print(f"      📝 텍스트 추출 중...")
        text_data = self.text_extractor.extract_with_markers(pdf_path, prefix=f"SUPP{order}")
        
        print(f"      ✅ 완료 ({text_data['total_pages']}페이지)")
        
        return {
            "order": order,
            "filename": display_name,
            "file_type": file_type,
            "total_pages": text_data['total_pages'],
            "content": {
                "full_text": text_data['full_text']
            }
        }
    
    def _extract_images_from_pptx(self, pptx_path: str) -> List[ImageMetadata]:
        """PPTX에서 이미지 메타데이터 추출"""
        extractor = UniversalImageExtractor()
        return extractor.extract(pptx_path)


# CLI 인터페이스
if __name__ == "__main__":
    import sys
    
    print("\n" + "="*120)
    print("🎯 Metadata Generator Node")
    print("="*120)
    
    if len(sys.argv) < 2:
        print("\n사용법:")
        print("  python metadata_generator_node.py <주강의자료> [보조1] [보조2] [보조3]")
        print("\n예시:")
        print("  python metadata_generator_node.py 중등국어1.pptx")
        print("  python metadata_generator_node.py notes.txt")
        print("  python metadata_generator_node.py https://example.com/article")
        print("\n✅ 지원 형식: PPTX, DOCX, PDF, TXT, URL")
        print("="*120 + "\n")
        sys.exit(1)
    
    primary_file = sys.argv[1]
    supplementary_files = sys.argv[2:5] if len(sys.argv) > 2 else None
    
    if not primary_file.startswith('http') and not os.path.exists(primary_file):
        print(f"\n❌ 주강의자료를 찾을 수 없습니다: {primary_file}")
        sys.exit(1)
    
    if supplementary_files:
        for supp in supplementary_files:
            if not supp.startswith('http') and not os.path.exists(supp):
                print(f"\n❌ 보조자료를 찾을 수 없습니다: {supp}")
                sys.exit(1)
    
    try:
        generator = MetadataGenerator()
        output_path = generator.generate(
            primary_file=primary_file,
            supplementary_files=supplementary_files,
            output_path="output/metadata.json"
        )
        
        print(f"✅ 성공!")
        print(f"📁 {output_path}")
        
    except Exception as e:
        print(f"\n❌ 에러 발생: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)