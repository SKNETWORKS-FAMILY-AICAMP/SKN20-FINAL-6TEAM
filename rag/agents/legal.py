"""법률 에이전트 모듈.

일반 법률, 소송/분쟁, 지식재산권 도메인을 담당하는 전문 에이전트입니다.
"""

from agents.base import ActionRule, BaseAgent
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

    ACTION_RULES = [
        ActionRule(
            keywords=["소송", "분쟁", "고소", "손해배상", "변호사"],
            action=ActionSuggestion(
                type="external_link",
                label="대한법률구조공단",
                description="무료 법률 상담 및 소송 지원을 받을 수 있습니다",
                params={"url": "https://www.klac.or.kr"},
            ),
        ),
        ActionRule(
            keywords=["특허", "상표", "출원", "등록", "지식재산", "저작권"],
            action=ActionSuggestion(
                type="external_link",
                label="KIPRIS 특허 검색",
                description="특허/상표/디자인 검색 서비스입니다",
                params={"url": "https://www.kipris.or.kr"},
            ),
        ),
        ActionRule(
            keywords=["법률", "법령", "조문", "상법", "민법", "판례"],
            action=ActionSuggestion(
                type="external_link",
                label="국가법령정보센터",
                description="법령 및 판례를 검색할 수 있습니다",
                params={"url": "https://www.law.go.kr"},
            ),
        ),
        ActionRule(
            keywords=["NDA", "비밀유지", "기밀유지", "비밀유지계약"],
            action=ActionSuggestion(
                type="document_generation",
                label="비밀유지계약서(NDA) 생성",
                description="비밀유지계약서(NDA)를 생성합니다",
                params={"document_type": "nda"},
            ),
        ),
        ActionRule(
            keywords=["주주간", "주주간계약", "주주 계약", "주주간 합의"],
            action=ActionSuggestion(
                type="document_generation",
                label="주주간 계약서 생성",
                description="주주간 계약서를 생성합니다",
                params={"document_type": "shareholders_agreement"},
            ),
        ),
        ActionRule(
            keywords=["용역", "용역계약", "외주", "아웃소싱", "프리랜서 계약"],
            action=ActionSuggestion(
                type="document_generation",
                label="용역 계약서 생성",
                description="용역(외주) 계약서를 생성합니다",
                params={"document_type": "service_agreement"},
            ),
        ),
    ]

    def get_system_prompt(self) -> str:
        """법률 에이전트 시스템 프롬프트를 반환합니다."""
        return LEGAL_PROMPT
