"""복합 질문 분해 모듈.

여러 도메인에 걸친 복합 질문을 단일 도메인 질문들로 분해합니다.
"""

import json
import logging
import re
from dataclasses import dataclass
from functools import lru_cache

from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import ChatPromptTemplate
from langchain_openai import ChatOpenAI

from utils.config import get_settings
from utils.prompts import QUESTION_DECOMPOSER_PROMPT
from utils.token_tracker import TokenUsageCallbackHandler

logger = logging.getLogger(__name__)


@dataclass
class SubQuery:
    """분해된 하위 질문.

    Attributes:
        domain: 질문이 속하는 도메인
        query: 분해된 질문 내용
    """

    domain: str
    query: str


class QuestionDecomposer:
    """복합 질문을 단일 도메인 질문들로 분해하는 클래스.

    여러 도메인이 감지된 복합 질문을 각 도메인에 해당하는
    독립적인 질문들로 분해합니다.

    Example:
        입력: "창업 절차와 세금 신고 방법 알려주세요" (startup_funding, finance_tax)
        출력: [
            SubQuery(domain="startup_funding", query="창업 절차 알려주세요"),
            SubQuery(domain="finance_tax", query="세금 신고 방법 알려주세요"),
        ]
    """

    def __init__(self):
        """QuestionDecomposer를 초기화합니다."""
        self.settings = get_settings()
        self.llm = ChatOpenAI(
            model=self.settings.openai_model,
            temperature=0.3,
            api_key=self.settings.openai_api_key,
            callbacks=[TokenUsageCallbackHandler("질문분해")],
        )

    def decompose(
        self,
        query: str,
        detected_domains: list[str],
    ) -> list[SubQuery]:
        """복합 질문을 단일 도메인 질문들로 분해합니다.

        Args:
            query: 원본 질문
            detected_domains: 감지된 도메인 리스트

        Returns:
            분해된 하위 질문 리스트
        """
        # 단일 도메인이면 분해 불필요
        if len(detected_domains) <= 1:
            domain = detected_domains[0] if detected_domains else "startup_funding"
            logger.info("[질문 분해] 단일 도메인 (%s) - 분해 불필요", domain)
            return [SubQuery(domain=domain, query=query)]

        logger.info(
            "[질문 분해] 복합 질문 분해 시작: '%s' → %s",
            query[:30],
            detected_domains,
        )

        prompt = ChatPromptTemplate.from_messages([
            ("system", QUESTION_DECOMPOSER_PROMPT),
        ])

        chain = prompt | self.llm | StrOutputParser()

        try:
            response = chain.invoke({
                "query": query,
                "domains": ", ".join(detected_domains),
            })

            # JSON 파싱
            json_match = re.search(r"```json\s*(.*?)\s*```", response, re.DOTALL)
            if json_match:
                result = json.loads(json_match.group(1))
            else:
                result = json.loads(response)

            sub_queries_data = result.get("sub_queries", [])
            sub_queries = []

            for sq in sub_queries_data:
                domain = sq.get("domain", "")
                sub_query = sq.get("query", "")

                # 유효한 도메인인지 확인
                if domain in detected_domains and sub_query:
                    sub_queries.append(SubQuery(domain=domain, query=sub_query))
                    logger.debug(
                        "[질문 분해] %s: '%s'",
                        domain,
                        sub_query[:50],
                    )

            # 분해 결과가 비어있으면 원본 사용
            if not sub_queries:
                logger.warning("[질문 분해] 분해 실패, 원본 질문 사용")
                return [
                    SubQuery(domain=domain, query=query)
                    for domain in detected_domains
                ]

            logger.info(
                "[질문 분해] 완료: %d개 하위 질문 생성",
                len(sub_queries),
            )
            return sub_queries

        except (json.JSONDecodeError, Exception) as e:
            logger.warning("[질문 분해] 파싱 실패: %s", e)
            # 실패 시 각 도메인에 원본 질문 전달
            return [
                SubQuery(domain=domain, query=query)
                for domain in detected_domains
            ]

    async def adecompose(
        self,
        query: str,
        detected_domains: list[str],
    ) -> list[SubQuery]:
        """복합 질문을 비동기로 분해합니다.

        Args:
            query: 원본 질문
            detected_domains: 감지된 도메인 리스트

        Returns:
            분해된 하위 질문 리스트
        """
        import asyncio

        return await asyncio.to_thread(
            self.decompose,
            query,
            detected_domains,
        )


@lru_cache(maxsize=1)
def get_question_decomposer() -> QuestionDecomposer:
    """QuestionDecomposer 싱글톤 인스턴스를 반환합니다.

    Returns:
        QuestionDecomposer 인스턴스
    """
    return QuestionDecomposer()
