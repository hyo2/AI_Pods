# app/services/podcast/extractors.py
import os
import re
import logging
import requests
from bs4 import BeautifulSoup
from docx import Document
import pdfplumber
from typing import List

logger = logging.getLogger(__name__)


class TextExtractor:
    """다양한 소스에서 텍스트 추출"""
    
    @staticmethod
    def extract_from_web(url: str) -> str:
        """웹 URL에서 텍스트 추출"""
        try:
            resp = requests.get(url, timeout=10)
            resp.raise_for_status()
            soup = BeautifulSoup(resp.text, 'html.parser')
            
            for script_or_style in soup(['script', 'style']):
                script_or_style.decompose()
            
            text = soup.get_text(separator='\n', strip=True)
            return re.sub(r'\n{3,}', '\n\n', text)
        except Exception as e:
            logger.error(f"웹 URL 처리 실패: {e}")
            return ""
    
    @staticmethod
    def extract_from_docx(file_path: str) -> str:
        """DOCX 파일에서 텍스트 추출"""
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"DOCX 파일을 찾을 수 없습니다: {file_path}")
        try:
            doc = Document(file_path)
            return "\n".join([p.text for p in doc.paragraphs if p.text.strip()])
        except Exception as e:
            logger.error(f"DOCX 처리 실패: {e}")
            return ""
    
    @staticmethod
    def extract_from_pdf(pdf_path: str) -> str:
        """PDF에서 텍스트 추출"""
        text = ""
        try:
            with pdfplumber.open(pdf_path) as pdf:
                for page in pdf.pages:
                    page_text = page.extract_text() or ""
                    text += page_text + "\n"
        except FileNotFoundError:
            raise FileNotFoundError(f"PDF 파일을 찾을 수 없습니다: {pdf_path}")
        except Exception as e:
            logger.error(f"PDF 처리 실패: {e}")
            return ""
        
        text = re.sub(r"[\*\U00010000-\U0010ffff]|#", "", text)
        return text.strip()
    
    @classmethod
    def extract(cls, source: str) -> str:
        """소스 타입에 따라 자동으로 추출"""
        source = source.strip()
        
        if source.startswith("http://") or source.startswith("https://"):
            return cls.extract_from_web(source)
        elif source.lower().endswith(".docx"):
            return cls.extract_from_docx(source)
        elif source.lower().endswith(".pdf"):
            return cls.extract_from_pdf(source)
        else:
            raise ValueError(f"지원하지 않는 소스 타입: {source}")


def extract_all_sources(sources: List[str]) -> tuple[List[str], List[str]]:
    """모든 소스에서 텍스트 추출"""
    extracted_texts = []
    errors = []
    
    for i, source in enumerate(sources):
        source_name = os.path.basename(source) if not source.startswith('http') else source
        logger.info(f"소스 {i+1}/{len(sources)} ({source_name}) 처리 중...")
        
        try:
            text = TextExtractor.extract(source)
            
            if text:
                extracted_texts.append(text)
            else:
                errors.append(f"소스 {source_name}에서 텍스트 추출 실패")
        except Exception as e:
            errors.append(f"소스 {source_name} 처리 오류: {str(e)}")
    
    return extracted_texts, errors