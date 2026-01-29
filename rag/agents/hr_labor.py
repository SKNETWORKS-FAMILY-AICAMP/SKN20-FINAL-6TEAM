"""인사/노무 에이전트 모듈.

인사, 노무, 법률 도메인을 담당하는 전문 에이전트입니다.
"""

from schemas.response import ActionSuggestion
from utils.prompts import HR_LABOR_PROMPT
from agents.base import BaseAgent


class HRLaborAgent(BaseAgent):
    """인사/노무 에이전트.

    담당 도메인:
    - 인사 (채용, 근로계약, 해고, 퇴직)
    - 노무 (근로시간, 연차, 급여, 4대보험)
    - 법률 (노동법, 분쟁, 지식재산권)

    데이터 소스:
    - hr_labor_db (인사/노무 전용)
    - law_common_db (공통 법령)

    Attributes:
        domain: hr_labor
    """

    domain = "hr_labor"

    def get_system_prompt(self) -> str:
        """인사/노무 에이전트 시스템 프롬프트를 반환합니다."""
        return HR_LABOR_PROMPT

    def suggest_actions(
        self,
        query: str,
        response: str,
    ) -> list[ActionSuggestion]:
        """추천 액션을 생성합니다.

        근로계약서, 퇴직금 계산 등 관련 키워드가 있으면 해당 액션을 제안합니다.

        Args:
            query: 사용자 질문
            response: 에이전트 응답

        Returns:
            추천 액션 리스트
        """
        actions = []
        query_lower = query.lower()
        response_lower = response.lower()

        # 근로계약서 관련 키워드
        contract_keywords = ["근로계약서", "근로 계약서", "고용계약서", "계약서 작성"]
        if any(kw in query_lower or kw in response_lower for kw in contract_keywords):
            actions.append(
                ActionSuggestion(
                    type="document_generation",
                    label="근로계약서 생성",
                    description="표준 근로계약서를 생성합니다",
                    params={"document_type": "labor_contract"},
                )
            )

        # 취업규칙 관련 키워드
        rules_keywords = ["취업규칙", "취업 규칙", "사규"]
        if any(kw in query_lower or kw in response_lower for kw in rules_keywords):
            actions.append(
                ActionSuggestion(
                    type="document_generation",
                    label="취업규칙 템플릿",
                    description="취업규칙 작성 템플릿을 제공합니다",
                    params={"document_type": "employment_rules"},
                )
            )

        # 퇴직금 관련 키워드
        severance_keywords = ["퇴직금", "퇴직 금", "퇴직금 계산"]
        if any(kw in query_lower or kw in response_lower for kw in severance_keywords):
            actions.append(
                ActionSuggestion(
                    type="calculator",
                    label="퇴직금 계산기",
                    description="퇴직금을 계산합니다",
                    params={"calculator_type": "severance"},
                )
            )

        # 연차 관련 키워드
        leave_keywords = ["연차", "휴가", "연차수당", "연차 계산"]
        if any(kw in query_lower or kw in response_lower for kw in leave_keywords):
            actions.append(
                ActionSuggestion(
                    type="calculator",
                    label="연차 계산기",
                    description="연차 일수 및 수당을 계산합니다",
                    params={"calculator_type": "annual_leave"},
                )
            )

        # 4대보험 관련 키워드
        insurance_keywords = ["4대보험", "사대보험", "국민연금", "건강보험", "고용보험", "산재보험"]
        if any(kw in query_lower or kw in response_lower for kw in insurance_keywords):
            actions.append(
                ActionSuggestion(
                    type="external_link",
                    label="4대보험 포털",
                    description="4대보험 관련 업무는 4대보험 정보연계센터에서 가능합니다",
                    params={"url": "https://www.4insure.or.kr"},
                )
            )

        return actions
