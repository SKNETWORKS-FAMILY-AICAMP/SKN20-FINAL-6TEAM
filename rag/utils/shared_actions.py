"""여러 에이전트에서 공유하는 ActionRule 정의."""

from agents.base import ActionRule
from schemas.response import ActionSuggestion

SERVICE_AGREEMENT_RULE = ActionRule(
    keywords=["용역", "용역계약", "외주", "아웃소싱", "프리랜서 계약"],
    action=ActionSuggestion(
        type="document_generation",
        label="용역 계약서 생성",
        description="용역(외주) 계약서를 생성합니다",
        params={"document_type": "service_agreement"},
    ),
)
