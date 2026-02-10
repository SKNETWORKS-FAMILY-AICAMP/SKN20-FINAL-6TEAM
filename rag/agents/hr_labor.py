"""인사/노무 에이전트 모듈.

인사, 노무, 법률 도메인을 담당하는 전문 에이전트입니다.
"""

from agents.base import ActionRule, BaseAgent
from schemas.response import ActionSuggestion
from utils.prompts import HR_LABOR_PROMPT


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

    ACTION_RULES = [
        ActionRule(
            keywords=["근로계약서", "근로 계약서", "고용계약서", "계약서 작성"],
            action=ActionSuggestion(
                type="document_generation",
                label="근로계약서 생성",
                description="표준 근로계약서를 생성합니다",
                params={"document_type": "labor_contract"},
            ),
        ),
        ActionRule(
            keywords=["취업규칙", "취업 규칙", "사규"],
            action=ActionSuggestion(
                type="document_generation",
                label="취업규칙 템플릿",
                description="취업규칙 작성 템플릿을 제공합니다",
                params={"document_type": "employment_rules"},
            ),
        ),
        ActionRule(
            keywords=["퇴직금", "퇴직 금", "퇴직금 계산"],
            action=ActionSuggestion(
                type="calculator",
                label="퇴직금 계산기",
                description="퇴직금을 계산합니다",
                params={"calculator_type": "severance"},
            ),
        ),
        ActionRule(
            keywords=["연차", "휴가", "연차수당", "연차 계산"],
            action=ActionSuggestion(
                type="calculator",
                label="연차 계산기",
                description="연차 일수 및 수당을 계산합니다",
                params={"calculator_type": "annual_leave"},
            ),
        ),
        ActionRule(
            keywords=["4대보험", "사대보험", "국민연금", "건강보험", "고용보험", "산재보험"],
            action=ActionSuggestion(
                type="external_link",
                label="4대보험 포털",
                description="4대보험 관련 업무는 4대보험 정보연계센터에서 가능합니다",
                params={"url": "https://www.4insure.or.kr"},
            ),
        ),
    ]

    def get_system_prompt(self) -> str:
        """인사/노무 에이전트 시스템 프롬프트를 반환합니다."""
        return HR_LABOR_PROMPT
