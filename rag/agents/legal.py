"""법률 에이전트 모듈.

일반 법률, 소송/분쟁, 지식재산권 도메인을 담당하는 전문 에이전트입니다.
"""

from agents.base import BaseAgent
from schemas.response import ActionSuggestion
from utils.prompts import LEGAL_PROMPT


class LegalAgent(BaseAgent):
    """법률 에이전트.

    담당 도메인:
    - 일반 법률 (상법, 민법, 계약법)
    - 소송/분쟁 (소송 절차, 손해배상, 조정/중재)
    - 지식재산권 (특허, 상표, 저작권)

    데이터 소스:
    - law_common_db (법률 전용)

    Attributes:
        domain: law_common
    """

    domain = "law_common"

    def get_system_prompt(self) -> str:
        """법률 에이전트 시스템 프롬프트를 반환합니다."""
        return LEGAL_PROMPT

    def suggest_actions(
        self,
        query: str,
        response: str,
    ) -> list[ActionSuggestion]:
        """추천 액션을 생성합니다.

        법률구조공단, KIPRIS, 국가법령정보센터 관련 키워드가 있으면
        해당 액션을 제안합니다.

        Args:
            query: 사용자 질문
            response: 에이전트 응답

        Returns:
            추천 액션 리스트
        """
        actions: list[ActionSuggestion] = []
        query_lower = query.lower()
        response_lower = response.lower()

        # 소송/분쟁 관련 키워드
        litigation_keywords = ["소송", "분쟁", "고소", "손해배상", "변호사"]
        if any(kw in query_lower or kw in response_lower for kw in litigation_keywords):
            actions.append(
                ActionSuggestion(
                    type="external_link",
                    label="대한법률구조공단",
                    description="무료 법률 상담 및 소송 지원을 받을 수 있습니다",
                    params={"url": "https://www.klac.or.kr"},
                )
            )

        # 특허/상표/지식재산 관련 키워드
        ip_keywords = ["특허", "상표", "출원", "등록", "지식재산", "저작권"]
        if any(kw in query_lower or kw in response_lower for kw in ip_keywords):
            actions.append(
                ActionSuggestion(
                    type="external_link",
                    label="KIPRIS 특허 검색",
                    description="특허/상표/디자인 검색 서비스입니다",
                    params={"url": "https://www.kipris.or.kr"},
                )
            )

        # 법령 관련 키워드
        law_keywords = ["법률", "법령", "조문", "상법", "민법", "판례"]
        if any(kw in query_lower or kw in response_lower for kw in law_keywords):
            actions.append(
                ActionSuggestion(
                    type="external_link",
                    label="국가법령정보센터",
                    description="법령 및 판례를 검색할 수 있습니다",
                    params={"url": "https://www.law.go.kr"},
                )
            )

        return actions
