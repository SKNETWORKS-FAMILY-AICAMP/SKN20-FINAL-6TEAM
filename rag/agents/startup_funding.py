"""창업/지원 에이전트 모듈.

창업, 지원사업, 마케팅 도메인을 담당하는 전문 에이전트입니다.
"""

from schemas.response import ActionSuggestion
from utils.prompts import STARTUP_FUNDING_PROMPT
from agents.base import BaseAgent


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

    def get_system_prompt(self) -> str:
        """창업/지원 에이전트 시스템 프롬프트를 반환합니다."""
        return STARTUP_FUNDING_PROMPT

    def suggest_actions(
        self,
        query: str,
        response: str,
    ) -> list[ActionSuggestion]:
        """추천 액션을 생성합니다.

        지원사업, 사업계획서 관련 키워드가 있으면 해당 액션을 제안합니다.

        Args:
            query: 사용자 질문
            response: 에이전트 응답

        Returns:
            추천 액션 리스트
        """
        actions = []
        query_lower = query.lower()
        response_lower = response.lower()

        # 지원사업 관련 키워드
        funding_keywords = ["지원사업", "보조금", "정책자금", "공고", "지원금"]
        if any(kw in query_lower or kw in response_lower for kw in funding_keywords):
            actions.append(
                ActionSuggestion(
                    type="funding_search",
                    label="맞춤 지원사업 검색",
                    description="기업 조건에 맞는 지원사업을 검색합니다",
                    params={"query": query},
                )
            )

        # 사업계획서 관련 키워드
        plan_keywords = ["사업계획서", "사업 계획", "창업 계획"]
        if any(kw in query_lower or kw in response_lower for kw in plan_keywords):
            actions.append(
                ActionSuggestion(
                    type="document_generation",
                    label="사업계획서 템플릿",
                    description="사업계획서 작성 템플릿을 제공합니다",
                    params={"document_type": "business_plan"},
                )
            )

        # 사업자등록 관련 키워드
        registration_keywords = ["사업자등록", "사업자 등록", "등록 신청"]
        if any(kw in query_lower or kw in response_lower for kw in registration_keywords):
            actions.append(
                ActionSuggestion(
                    type="external_link",
                    label="홈택스 바로가기",
                    description="사업자등록 신청은 홈택스에서 가능합니다",
                    params={"url": "https://www.hometax.go.kr"},
                )
            )

        return actions
