# app/langgraph_pipeline/podcast/improved_hybrid_filter.py

import os
import vertexai
import textwrap
import json
from dataclasses import dataclass
from typing import List, Tuple, Optional
from pathlib import Path

# PPTX 처리
from pptx import Presentation
from pptx.enum.shapes import MSO_SHAPE_TYPE

# PDF 처리
import pdfplumber
from pdf2image import convert_from_path

# Vertex AI
from vertexai.generative_models import GenerativeModel, Part

# [절대 경로 유지]
SERVICE_ACCOUNT_FILE = r"C:\Users\USER\Desktop\securityKey\persokey\vertex-ai-service-account.json"
os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = SERVICE_ACCOUNT_FILE

# 프로젝트 ID 로드
try:
    with open(SERVICE_ACCOUNT_FILE, 'r') as f:
        creds = json.load(f)
        PROJECT_ID = creds.get("project_id", "alan-document-lab") 
except Exception:
    PROJECT_ID = "alan-document-lab"

# Vertex AI 초기화
try:
    vertexai.init(project=PROJECT_ID, location="us-central1")
    model = GenerativeModel("gemini-1.5-flash-001")
except Exception as e:
    print(f"⚠️ Vertex AI 초기화 경고: {e}")
    model = None

@dataclass
class ImageMetadata:
    image_id: str
    slide_number: int
    area_percentage: float
    left: float
    top: float
    adjacent_text: str
    slide_title: str
    image_bytes: bytes = None
    is_core_content: bool = False
    filter_reason: str = ""

class UniversalImageExtractor:
    """
    모든 형식(PPTX, PDF)에서 이미지 메타데이터 추출
    """
    def extract(self, file_path: str) -> List[ImageMetadata]:
        ext = Path(file_path).suffix.lower()
        
        if ext == '.pptx':
            return self._extract_from_pptx(file_path)
        elif ext == '.pdf' or ext == '.docx':
            return self._extract_from_pdf(file_path)
        return []

    def _extract_from_pptx(self, pptx_path: str) -> List[ImageMetadata]:
        images = []
        try:
            prs = Presentation(pptx_path)
            for i, slide in enumerate(prs.slides):
                slide_num = i + 1
                
                # 텍스트 추출
                slide_text = []
                slide_title = ""
                if slide.shapes.title:
                    slide_title = slide.shapes.title.text
                
                for shape in slide.shapes:
                    if hasattr(shape, "text"):
                        slide_text.append(shape.text)
                full_text = " ".join(slide_text)

                # 이미지 추출
                for shape in slide.shapes:
                    if shape.shape_type == MSO_SHAPE_TYPE.PICTURE:
                        slide_width = prs.slide_width
                        slide_height = prs.slide_height
                        img_area = shape.width * shape.height
                        total_area = slide_width * slide_height
                        area_ratio = img_area / total_area

                        images.append(ImageMetadata(
                            image_id=f"P{slide_num:02d}_{id(shape)}",
                            slide_number=slide_num,
                            area_percentage=area_ratio,
                            left=shape.left / slide_width,
                            top=shape.top / slide_height,
                            adjacent_text=full_text[:500],
                            slide_title=slide_title,
                            image_bytes=shape.image.blob
                        ))
        except Exception as e:
            print(f"PPTX 이미지 추출 실패: {e}")
        return images

    def _extract_from_pdf(self, pdf_path: str) -> List[ImageMetadata]:
        # PDF 이미지 추출은 복잡도가 높아 일단 빈 리스트 반환 (텍스트 위주 처리)
        # 필요 시 pdf2image 구현 추가 가능
        return []


class ImprovedHybridFilterPipeline:
    """
    하이브리드 필터링 파이프라인 (규칙 + AI)
    """
    # [수정된 부분] 변수명 오타 수정
    def __init__(self, auto_extract_keywords: bool = True):
        self.auto_extract = auto_extract_keywords  # <-- 여기가 수정되었습니다
        self.document_keywords = []

    def extract_keywords_from_document(self, file_path: str):
        """문서 내용을 바탕으로 키워드 자동 추출 (Gemini 사용)"""
        if not self.auto_extract:
            self.document_keywords = ["일반 강의", "핵심 내용"]
            return

        if not model:
            print("⚠️ 모델 초기화 실패로 범용 키워드 사용")
            self.document_keywords = ["강의 자료", "학습 내용"]
            return

        try:
            text_preview = ""
            ext = Path(file_path).suffix.lower()
            
            if ext == '.pptx':
                prs = Presentation(file_path)
                for slide in prs.slides[:3]: 
                    for shape in slide.shapes:
                        if hasattr(shape, "text"):
                            text_preview += shape.text + "\n"
            else:
                text_preview = "문서 내용 분석 필요"

            prompt = f"""
            다음 문서의 앞부분을 보고 핵심 키워드 5개를 추출해줘. 
            콤마로 구분해서 출력해.
            
            문서 내용:
            {text_preview[:1000]}
            """
            response = model.generate_content(prompt)
            self.document_keywords = [k.strip() for k in response.text.split(',')]
            print(f"✅ 자동 키워드 추출 성공: {self.document_keywords}")

        except Exception as e:
            print(f"⚠️ 자동 추출 실패 ({e}), 범용 패턴만 사용")
            self.document_keywords = ["학습 자료", "중요 개념"]

    def step1_rule_check(self, img: ImageMetadata) -> Tuple[str, str]:
        """1차 필터링: 규칙 기반"""
        if img.area_percentage < 0.05:
            return "EXCLUDE", "Too small (Icon/Logo)"
        if img.area_percentage > 0.9:
            return "PENDING", "Full slide (Check content)"
        return "PENDING", "Passed Rule Check"

    def step2_gemini_check(self, img: ImageMetadata) -> str:
        """2차 필터링: Gemini Vision"""
        if not model or img.image_bytes is None:
            return "KEEP (AI Unavailable)"

        try:
            image_part = Part.from_data(data=img.image_bytes, mime_type="image/png")
            
            prompt = f"""
            이 이미지가 교육용 팟캐스트 대본을 작성할 때 설명할 가치가 있는 '핵심 시각 자료'인지 판단해.
            단순 배경, 장식, 아이콘, 의미 없는 사진이면 'DELETE'라고 답해.
            도표, 그래프, 핵심 구조도, 중요한 예시 사진이면 'KEEP'이라고 답하고 이유를 짧게 적어.
            
            문맥: {img.adjacent_text[:200]}
            형식: KEEP | 이유  또는  DELETE | 이유
            """
            
            response = model.generate_content([image_part, prompt])
            return response.text.strip()
        except Exception:
            return "KEEP (Error)"