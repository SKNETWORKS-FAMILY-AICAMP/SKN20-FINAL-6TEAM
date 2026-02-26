"""창업/지원 에이전트 모듈.

창업, 지원사업, 마케팅 도메인을 담당하는 전문 에이전트입니다.
"""

from agents.base import ActionRule, BaseAgent
from schemas.response import ActionSuggestion
from utils.prompts import STARTUP_FUNDING_PROMPT


class StartupFundingAgent(BaseAgent):
    """창업/지원 에이전트.

    담당 도메인:
    - 창업 절차 (사업자등록, 법인설립, 인허가)
    - 지원사업 (보조금, 정책자금, 공고)
    - 마케팅 (홍보, 브랜딩, 광고)

    데이터 소스:
    - startup_funding_db (창업/지원 전용)
    - law_common_db (공통 법령)

    Attributes:
        domain: startup_funding
    """

    domain = "startup_funding"

    ACTION_RULES = [
        ActionRule(
            keywords=["지원사업", "보조금", "정책자금", "공고", "지원금"],
            action=ActionSuggestion(
                type="funding_search",
                label="맞춤 지원사업 검색",
                description="기업 조건에 맞는 지원사업을 검색합니다",
                params={},
            ),
            dynamic_query_param=True,
        ),
        ActionRule(
            keywords=["사업계획서", "사업 계획", "창업 계획"],
            action=ActionSuggestion(
                type="document_generation",
                label="사업계획서 템플릿",
                description="사업계획서 작성 템플릿을 제공합니다",
                params={"document_type": "business_plan"},
            ),
        ),
        ActionRule(
            keywords=["사업자등록", "사업자 등록", "등록 신청"],
            action=ActionSuggestion(
                type="external_link",
                label="홈택스 바로가기",
                description="사업자등록 신청은 홈택스에서 가능합니다",
                params={"url": "https://www.hometax.go.kr"},
            ),
        ),
        ActionRule(
            keywords=["공동창업", "공동 창업", "동업", "동업계약"],
            action=ActionSuggestion(
                type="document_generation",
                label="공동 창업 계약서 생성",
                description="공동 창업자 간 계약서를 생성합니다",
                params={"document_type": "cofounder_agreement"},
            ),
        ),
        ActionRule(
            keywords=["투자", "투자유치", "투자의향서", "LOI", "텀시트"],
            action=ActionSuggestion(
                type="document_generation",
                label="투자 의향서(LOI) 생성",
                description="투자 의향서를 생성합니다",
                params={"document_type": "investment_loi"},
            ),
        ),
        ActionRule(
            keywords=["MOU", "업무협약", "양해각서", "협약서"],
            action=ActionSuggestion(
                type="document_generation",
                label="업무 협약서(MOU) 생성",
                description="업무 협약서(MOU)를 생성합니다",
                params={"document_type": "mou"},
            ),
        ),
    ]

    def get_system_prompt(self) -> str:
        """창업/지원 에이전트 시스템 프롬프트를 반환합니다."""
        return STARTUP_FUNDING_PROMPT
