"""문서 자동생성 툴.

도메인 에이전트가 문서 생성이 필요할 때 호출하는 tool 인터페이스입니다.
BM25 키워드 1차 필터 + LLM 의도 2차 판별 하이브리드 방식으로 문서 생성 필요 여부를 판단합니다.
"""

import logging
from typing import Any

from agents.executor import ActionExecutor
from schemas.response import ActionSuggestion, DocumentResponse

logger = logging.getLogger(__name__)

# 문서 유형별 트리거 키워드 사전
DOCUMENT_TRIGGER_KEYWORDS: dict[str, list[str]] = {
    "labor_contract": [
        "근로계약서", "근로계약", "고용계약서", "계약서 작성", "근로계약 작성",
    ],
    "business_plan": [
        "사업계획서", "사업계획", "사업 계획서 작성", "비즈니스 플랜",
    ],
    "nda": [
        "비밀유지계약서", "NDA", "비밀유지", "기밀유지",
    ],
    "service_agreement": [
        "용역계약서", "용역계약", "외주계약", "프리랜서 계약",
    ],
    "cofounder_agreement": [
        "공동창업계약서", "공동창업", "동업계약",
    ],
    "investment_loi": [
        "투자의향서", "LOI", "투자유치",
    ],
    "mou": [
        "업무협약서", "MOU", "양해각서",
    ],
    "privacy_consent": [
        "개인정보동의서", "개인정보 수집", "개인정보 처리",
    ],
    "shareholders_agreement": [
        "주주간계약서", "주주간 계약", "주주 계약",
    ],
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
        domain: str,
        context: dict[str, Any] | None = None,
    ) -> tuple[bool, str | None]:
        """문서 생성이 필요한지 판단합니다 (BM25 + LLM 하이브리드).

        1차: 키워드 매칭으로 문서 유형 탐지 (빠름, 저비용)
        2차: LLM 의도 분류로 GENERATE 여부 확인 (1차 통과 시에만)

        Args:
            query: 사용자 질문
            domain: 분류된 도메인
            context: 추가 컨텍스트

        Returns:
            (호출 여부, 탐지된 문서 유형 키)
        """
        # 1차: 키워드 기반 문서 유형 탐지
        detected_type = self._keyword_detect(query)
        if not detected_type:
            return False, None

        # 2차: LLM 의도 판별
        intent = self._llm_intent_classify(query, detected_type)
        if intent == "GENERATE":
            return True, detected_type
        return False, None

    def _keyword_detect(self, query: str) -> str | None:
        """키워드 매칭으로 문서 유형을 탐지합니다.

        kiwipiepy 형태소 분석으로 lemma를 추출한 뒤,
        각 문서 유형의 키워드와 매칭합니다.

        Args:
            query: 사용자 질문

        Returns:
            매칭된 문서 유형 키 또는 None
        """
        from utils.domain_classifier import extract_lemmas

        query_lower = query.lower()
        lemmas = extract_lemmas(query)

        best_type: str | None = None
        best_score = 0

        for doc_type, keywords in DOCUMENT_TRIGGER_KEYWORDS.items():
            score = 0
            for kw in keywords:
                kw_lower = kw.lower()
                # 원본 쿼리에서 직접 매칭 (복합어 대응)
                if kw_lower in query_lower:
                    score += 2
                # lemma 집합에서 매칭 (형태소 분석 결과)
                elif kw_lower in lemmas:
                    score += 1

            if score > best_score:
                best_score = score
                best_type = doc_type

        # 최소 1점 이상이어야 유효
        if best_score >= 1:
            return best_type
        return None

    def _llm_intent_classify(self, query: str, detected_type: str) -> str:
        """LLM으로 문서 생성 의도를 분류합니다.

        Args:
            query: 사용자 질문
            detected_type: 1차 탐지된 문서 유형 키

        Returns:
            "GENERATE", "INFO", 또는 "UNRELATED"
        """
        from utils.config.llm import create_llm
        from utils.prompts import DOCUMENT_INTENT_CLASSIFICATION_PROMPT

        label = _DOC_TYPE_LABELS.get(detected_type, detected_type)
        prompt = DOCUMENT_INTENT_CLASSIFICATION_PROMPT.format(
            query=query,
            detected_type=label,
        )

        try:
            llm = create_llm(label="문서의도판별", temperature=0.0, max_tokens=16)
            response = llm.invoke([{"role": "user", "content": prompt}])
            result = response.content.strip().upper()

            # 응답에서 키워드 추출 (여러 줄 응답 대비)
            for intent in ("GENERATE", "INFO", "UNRELATED"):
                if intent in result:
                    return intent

            logger.warning("LLM 의도 분류 파싱 실패 (원문: %s), INFO 기본값", result)
            return "INFO"
        except Exception:
            logger.error("LLM 의도 분류 호출 실패, INFO 기본값", exc_info=True)
            return "INFO"

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
