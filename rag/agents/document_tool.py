"""문서 자동생성 툴.

도메인 에이전트가 문서 생성이 필요할 때 호출하는 tool 인터페이스입니다.
LLM 의도 판별로 문서 생성 필요 여부와 문서 유형을 판단합니다.
"""

import logging
from typing import Any

from agents.executor import ActionExecutor
from schemas.response import ActionSuggestion, DocumentResponse

logger = logging.getLogger(__name__)

# LLM 응답 검증용 허용 문서 유형 키 집합
_VALID_DOC_TYPES: set[str] = {
    "labor_contract", "business_plan", "nda", "service_agreement",
    "cofounder_agreement", "investment_loi", "mou", "privacy_consent",
    "shareholders_agreement",
}

# 문서 유형 키 → 한글 라벨 (LLM 프롬프트용)
_DOC_TYPE_LABELS: dict[str, str] = {
    "labor_contract": "근로계약서",
    "business_plan": "사업계획서",
    "nda": "비밀유지계약서(NDA)",
    "service_agreement": "용역계약서",
    "cofounder_agreement": "공동창업계약서",
    "investment_loi": "투자의향서(LOI)",
    "mou": "업무협약서(MOU)",
    "privacy_consent": "개인정보동의서",
    "shareholders_agreement": "주주간계약서",
}


class DocumentTool:
    """문서 자동생성 툴.

    도메인 에이전트의 응답 생성 과정에서 문서 생성이 필요할 때 호출됩니다.
    should_invoke()로 필요 여부를 판단하고, invoke()로 실행합니다.
    """

    def __init__(self) -> None:
        self.executor = ActionExecutor()

    # ---------- 탐지 ----------

    def should_invoke(
        self,
        query: str,
        context: dict[str, Any] | None = None,
    ) -> tuple[bool, str | None]:
        """문서 생성이 필요한지 판단합니다 (LLM 의도 분류).

        LLM이 직접 문서 생성 의도와 문서 유형을 동시에 판별합니다.

        Args:
            query: 사용자 질문
            context: 추가 컨텍스트

        Returns:
            (호출 여부, 탐지된 문서 유형 키)
        """
        intent, doc_type = self._llm_intent_classify(query)
        if intent == "GENERATE" and doc_type:
            return True, doc_type
        return False, None

    def _llm_intent_classify(self, query: str) -> tuple[str, str | None]:
        """LLM으로 문서 생성 의도와 문서 유형을 분류합니다.

        Args:
            query: 사용자 질문

        Returns:
            (intent, document_type_key): ("GENERATE", "nda") 또는 ("INFO", None)
        """
        from utils.config.llm import create_llm
        from utils.prompts import DOCUMENT_INTENT_CLASSIFICATION_PROMPT

        prompt = DOCUMENT_INTENT_CLASSIFICATION_PROMPT.format(query=query)

        try:
            llm = create_llm(label="문서의도판별", temperature=0.0, max_tokens=32)
            response = llm.invoke([{"role": "user", "content": prompt}])
            result = response.content.strip().upper()

            # "GENERATE <type_key>" 파싱
            if "GENERATE" in result:
                parts = result.split()
                for i, part in enumerate(parts):
                    if part == "GENERATE" and i + 1 < len(parts):
                        doc_type = parts[i + 1].lower()
                        if doc_type in _VALID_DOC_TYPES:
                            return "GENERATE", doc_type
                        logger.warning("LLM 의도 분류: 알 수 없는 문서 유형 '%s'", doc_type)
                        return "INFO", None
                # GENERATE만 있고 타입이 없는 경우
                logger.warning("LLM 의도 분류: GENERATE이나 문서 유형 없음 (원문: %s)", result)
                return "INFO", None

            return "INFO", None
        except Exception:
            logger.error("LLM 의도 분류 호출 실패, INFO 기본값", exc_info=True)
            return "INFO", None

    # ---------- 액션 필터링 ----------

    def detect_from_actions(
        self,
        actions: list[ActionSuggestion],
    ) -> list[ActionSuggestion]:
        """수집된 액션에서 document_generation 유형만 필터링합니다."""
        return [a for a in actions if a.type == "document_generation"]

    # ---------- 실행 ----------

    async def invoke(
        self,
        document_type: str,
        params: dict[str, Any],
        format: str = "docx",
        user_id: int | None = None,
        company_id: int | None = None,
    ) -> DocumentResponse:
        """문서 생성을 실행합니다.

        Args:
            document_type: 문서 유형 키
            params: 문서 필드 값
            format: 출력 형식 (pdf, docx)
            user_id: 사용자 ID (있으면 S3/DB 저장)
            company_id: 회사 ID (선택)

        Returns:
            문서 생성 응답
        """
        return self.executor.generate_document(
            document_type=document_type,
            params=params,
            format=format,
            user_id=user_id,
            company_id=company_id,
        )
