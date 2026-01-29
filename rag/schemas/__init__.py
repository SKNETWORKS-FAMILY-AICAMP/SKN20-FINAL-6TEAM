"""RAG 서비스 스키마 모듈.

요청/응답 Pydantic 모델을 정의합니다.
"""

from schemas.request import (
    CompanyContext,
    UserContext,
    ChatRequest,
    DocumentRequest,
    ContractRequest,
)
from schemas.response import (
    ActionSuggestion,
    EvaluationResult,
    SourceDocument,
    ChatResponse,
    DocumentResponse,
    StreamResponse,
)

__all__ = [
    # Request
    "CompanyContext",
    "UserContext",
    "ChatRequest",
    "DocumentRequest",
    "ContractRequest",
    # Response
    "ActionSuggestion",
    "EvaluationResult",
    "SourceDocument",
    "ChatResponse",
    "DocumentResponse",
    "StreamResponse",
]
