"""파일 텍스트 추출 유틸리티.

업로드된 DOCX/PDF/HWP/HWPX 파일에서 텍스트를 추출합니다.
HWP/HWPX는 Upstage Document Parse API를 사용합니다.
"""

import base64
import logging
import os
import re
from io import BytesIO
from pathlib import PurePosixPath

logger = logging.getLogger(__name__)

# 로컬 파서 지원 확장자
_LOCAL_EXTENSIONS = {".docx", ".pdf"}
# Upstage API 지원 확장자
_UPSTAGE_EXTENSIONS = {".hwp", ".hwpx"}

SUPPORTED_EXTENSIONS = _LOCAL_EXTENSIONS | _UPSTAGE_EXTENSIONS


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
            f"지원하지 않는 파일 형식입니다: {ext} (DOCX, PDF, HWP, HWPX 지원)"
        )

    try:
        decoded = base64.b64decode(file_content)
    except Exception as e:
        raise ValueError(f"파일 디코딩 실패: {e}") from e

    buffer = BytesIO(decoded)

    if ext == ".docx":
        text = _extract_from_docx(buffer)
    elif ext == ".pdf":
        text = _extract_from_pdf(buffer)
    elif ext in _UPSTAGE_EXTENSIONS:
        text = _extract_from_hwp_via_upstage(decoded, file_name)
    else:
        raise ValueError(f"지원하지 않는 파일 형식입니다: {ext}")

    if not text.strip():
        raise ValueError("문서에서 텍스트를 추출할 수 없습니다.")

    return text


def extract_text_from_bytes(file_bytes: bytes, file_name: str) -> str:
    """바이트 데이터에서 텍스트를 추출합니다.

    S3에서 다운로드한 파일 등 base64 인코딩 없이 바이트로 전달되는 경우 사용합니다.

    Args:
        file_bytes: 파일 바이너리 데이터
        file_name: 원본 파일명 (확장자 판별용)

    Returns:
        추출된 텍스트

    Raises:
        ValueError: 지원하지 않는 파일 형식이거나 텍스트 추출 실패 시
    """
    b64 = base64.b64encode(file_bytes).decode()
    return extract_text_from_base64(b64, file_name)


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


def _extract_from_hwp_via_upstage(file_bytes: bytes, file_name: str) -> str:
    """Upstage Document Parse API로 HWP/HWPX 파일에서 텍스트를 추출합니다.

    Args:
        file_bytes: HWP/HWPX 파일 바이너리
        file_name: 파일명

    Returns:
        추출된 텍스트

    Raises:
        ValueError: API 키 미설정 또는 API 호출 실패 시
    """
    import httpx

    api_key = os.getenv("UPSTAGE_API_KEY")
    if not api_key:
        raise ValueError("UPSTAGE_API_KEY가 설정되지 않아 HWP 파일을 처리할 수 없습니다.")

    url = "https://api.upstage.ai/v1/document-digitization"
    headers = {"Authorization": f"Bearer {api_key}"}

    try:
        with httpx.Client(timeout=60.0) as client:
            response = client.post(
                url,
                headers=headers,
                files={"document": (file_name, file_bytes)},
                data={"model": "document-parse", "output_formats": '["text"]'},
            )
            response.raise_for_status()

        result = response.json()
        # Upstage API 응답에서 텍스트 추출
        content = result.get("content", {})
        if isinstance(content, dict):
            text = content.get("text", "")
        elif isinstance(content, str):
            text = content
        else:
            text = ""

        # HTML 태그 제거 (markdown/html 응답인 경우)
        if "<" in text and ">" in text:
            text = re.sub(r"<[^>]+>", "", text)

        if not text.strip():
            # elements에서 텍스트 추출 시도
            elements = result.get("elements", [])
            texts = [e.get("text", "") for e in elements if e.get("text")]
            text = "\n".join(texts)

        logger.info("Upstage Document Parse 완료: %s (%d자)", file_name, len(text))
        return text

    except httpx.HTTPStatusError as e:
        logger.error("Upstage API 호출 실패: %s %s", e.response.status_code, e.response.text[:200])
        raise ValueError(f"HWP 파일 파싱 실패 (HTTP {e.response.status_code})") from e
    except Exception as e:
        logger.error("Upstage API 호출 오류: %s", e)
        raise ValueError(f"HWP 파일 파싱 실패: {e}") from e
