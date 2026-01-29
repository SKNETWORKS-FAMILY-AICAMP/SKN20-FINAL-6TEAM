"""재무/세무 에이전트 모듈.

세무, 회계, 재무 도메인을 담당하는 전문 에이전트입니다.
"""

from schemas.response import ActionSuggestion
from utils.prompts import FINANCE_TAX_PROMPT
from agents.base import BaseAgent


class FinanceTaxAgent(BaseAgent):
    """재무/세무 에이전트.

    담당 도메인:
    - 세무 (부가세, 법인세, 소득세, 원천징수)
    - 회계 (재무제표, 결산, 회계처리)
    - 재무 (자금관리, 투자, 대출)

    데이터 소스:
    - finance_tax_db (재무/세무 전용)
    - law_common_db (공통 법령)

    Attributes:
        domain: finance_tax
    """

    domain = "finance_tax"

    def get_system_prompt(self) -> str:
        """재무/세무 에이전트 시스템 프롬프트를 반환합니다."""
        return FINANCE_TAX_PROMPT

    def suggest_actions(
        self,
        query: str,
        response: str,
    ) -> list[ActionSuggestion]:
        """추천 액션을 생성합니다.

        세금 신고, 계산 관련 키워드가 있으면 해당 액션을 제안합니다.

        Args:
            query: 사용자 질문
            response: 에이전트 응답

        Returns:
            추천 액션 리스트
        """
        actions = []
        query_lower = query.lower()
        response_lower = response.lower()

        # 부가세 관련 키워드
        vat_keywords = ["부가세", "부가가치세", "매입세액", "매출세액"]
        if any(kw in query_lower or kw in response_lower for kw in vat_keywords):
            actions.append(
                ActionSuggestion(
                    type="schedule_alert",
                    label="부가세 신고 알림 등록",
                    description="부가세 신고 기한 알림을 등록합니다",
                    params={"schedule_type": "vat_report"},
                )
            )

        # 법인세 관련 키워드
        corporate_tax_keywords = ["법인세", "법인 세금"]
        if any(kw in query_lower or kw in response_lower for kw in corporate_tax_keywords):
            actions.append(
                ActionSuggestion(
                    type="schedule_alert",
                    label="법인세 신고 알림 등록",
                    description="법인세 신고 기한 알림을 등록합니다",
                    params={"schedule_type": "corporate_tax_report"},
                )
            )

        # 세금 계산 관련 키워드
        calc_keywords = ["계산", "얼마", "세액", "세금 얼마"]
        if any(kw in query_lower for kw in calc_keywords):
            actions.append(
                ActionSuggestion(
                    type="calculator",
                    label="세금 계산기",
                    description="세금 계산기를 사용합니다",
                    params={"calculator_type": "tax"},
                )
            )

        # 홈택스 관련 키워드
        hometax_keywords = ["신고", "납부", "홈택스", "전자신고"]
        if any(kw in query_lower or kw in response_lower for kw in hometax_keywords):
            actions.append(
                ActionSuggestion(
                    type="external_link",
                    label="홈택스 바로가기",
                    description="세금 신고/납부는 홈택스에서 가능합니다",
                    params={"url": "https://www.hometax.go.kr"},
                )
            )

        return actions
