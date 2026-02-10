"""재무/세무 에이전트 모듈.

세무, 회계, 재무 도메인을 담당하는 전문 에이전트입니다.
"""

from agents.base import ActionRule, BaseAgent
from schemas.response import ActionSuggestion
from utils.prompts import FINANCE_TAX_PROMPT


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

    ACTION_RULES = [
        ActionRule(
            keywords=["부가세", "부가가치세", "매입세액", "매출세액"],
            action=ActionSuggestion(
                type="schedule_alert",
                label="부가세 신고 알림 등록",
                description="부가세 신고 기한 알림을 등록합니다",
                params={"schedule_type": "vat_report"},
            ),
        ),
        ActionRule(
            keywords=["법인세", "법인 세금"],
            action=ActionSuggestion(
                type="schedule_alert",
                label="법인세 신고 알림 등록",
                description="법인세 신고 기한 알림을 등록합니다",
                params={"schedule_type": "corporate_tax_report"},
            ),
        ),
        ActionRule(
            keywords=["계산", "얼마", "세액", "세금 얼마"],
            action=ActionSuggestion(
                type="calculator",
                label="세금 계산기",
                description="세금 계산기를 사용합니다",
                params={"calculator_type": "tax"},
            ),
            match_response=False,
        ),
        ActionRule(
            keywords=["신고", "납부", "홈택스", "전자신고"],
            action=ActionSuggestion(
                type="external_link",
                label="홈택스 바로가기",
                description="세금 신고/납부는 홈택스에서 가능합니다",
                params={"url": "https://www.hometax.go.kr"},
            ),
        ),
    ]

    def get_system_prompt(self) -> str:
        """재무/세무 에이전트 시스템 프롬프트를 반환합니다."""
        return FINANCE_TAX_PROMPT
