"""BM25 한국어 토크나이징 공통 모듈.

builder.py와 BM25Index가 공유하는 토크나이징 함수를 제공합니다.
"""

import logging
import re

logger = logging.getLogger(__name__)

_kiwi_instance = None
_kiwi_available: bool | None = None  # None = 미확인


def _get_kiwi() -> object | None:
    """Kiwi 인스턴스를 모듈 수준 싱글톤으로 반환합니다."""
    global _kiwi_instance, _kiwi_available
    if _kiwi_instance is None and _kiwi_available is not False:
        try:
            from kiwipiepy import Kiwi
            _kiwi_instance = Kiwi()
            _kiwi_available = True
        except ImportError:
            logger.warning("[BM25] kiwipiepy 미설치, 정규식 토크나이저로 fallback")
            _kiwi_available = False
    return _kiwi_instance


def tokenize_korean(text: str, kiwi: object | None = None) -> list[str]:
    """kiwipiepy 기반 한국어 토크나이징 (BM25용).

    Args:
        text: 토크나이징할 텍스트
        kiwi: Kiwi 인스턴스 (None이면 모듈 싱글톤 사용)

    Returns:
        토큰 리스트 (최소 2자 이상)
    """
    if kiwi is None:
        kiwi = _get_kiwi()

    if kiwi:
        tokens = kiwi.tokenize(text)
        result = []
        for token in tokens:
            if token.tag.startswith("NN") or token.tag == "SL":
                result.append(token.form)
            elif token.tag.startswith("VV") or token.tag.startswith("VA"):
                result.append(token.form + "다")
        return [t for t in result if len(t) >= 2]

    # fallback: 정규식 토크나이저
    tokens = re.findall(r'[가-힣]+|[a-zA-Z]+|[0-9]+', text.lower())
    return [t for t in tokens if len(t) >= 2]
