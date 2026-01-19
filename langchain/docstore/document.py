# backend/langchain/docstore/document.py
from dataclasses import dataclass
from typing import Any, Dict, Optional

@dataclass
class Document:
    page_content: str
    metadata: Optional[Dict[str, Any]] = None