"""파일 텍스트 추출 유틸리티.

업로드된 DOCX/PDF 파일에서 텍스트를 추출합니다.
"""

import base64
import logging
from io import BytesIO
from pathlib import PurePosixPath

logger = logging.getLogger(__name__)

SUPPORTED_EXTENSIONS = {".docx", ".pdf"}


def extract_text_from_base64(file_content: str, file_name: str) -> str:
    """base64 인코딩된 파일에서 텍스트를 추출합니다.

    Args:
        file_content: base64 인코딩된 파일 바이너리
        file_name: 원본 파일명 (확장자 판별용)

    Returns:
        추출된 텍스트

    Raises:
        ValueError: 지원하지 않는 파일 형식이거나 텍스트 추출 실패 시
    """
    ext = PurePosixPath(file_name).suffix.lower()
    if ext not in SUPPORTED_EXTENSIONS:
        raise ValueError(
            f"지원하지 않는 파일 형식입니다: {ext} (DOCX, PDF만 지원)"
        )

    try:
        decoded = base64.b64decode(file_content)
    except Exception as e:
        raise ValueError(f"파일 디코딩 실패: {e}") from e

    buffer = BytesIO(decoded)

    if ext == ".docx":
        text = _extract_from_docx(buffer)
    else:
        text = _extract_from_pdf(buffer)

    if not text.strip():
        raise ValueError("문서에서 텍스트를 추출할 수 없습니다.")

    return text


def _extract_from_docx(buffer: BytesIO) -> str:
    """DOCX 파일에서 텍스트를 추출합니다."""
    from docx import Document

    doc = Document(buffer)
    paragraphs = [p.text for p in doc.paragraphs]
    return "\n".join(paragraphs)


def _extract_from_pdf(buffer: BytesIO) -> str:
    """PDF 파일에서 텍스트를 추출합니다."""
    import pdfplumber

    texts: list[str] = []
    with pdfplumber.open(buffer) as pdf:
        for page in pdf.pages:
            page_text = page.extract_text()
            if page_text:
                texts.append(page_text)
    return "\n".join(texts)
