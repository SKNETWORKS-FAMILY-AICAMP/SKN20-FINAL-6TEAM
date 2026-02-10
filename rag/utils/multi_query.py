"""Multi-Query 검색 모듈.

검색 품질이 낮을 때 여러 관점의 쿼리를 생성하여 병렬 검색 후 RRF로 융합합니다.
"""

import json
import logging
import re
from functools import lru_cache
from typing import TYPE_CHECKING

from langchain_core.documents import Document
from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import ChatPromptTemplate

from utils.config import create_llm, get_settings
from utils.prompts import MULTI_QUERY_PROMPT

if TYPE_CHECKING:
    from chains.rag_chain import RAGChain

logger = logging.getLogger(__name__)


class MultiQueryRetriever:
    """Multi-Query 병렬 검색기.

    1. LLM을 사용하여 원본 쿼리를 여러 관점으로 확장
    2. 원본 + 확장 쿼리로 병렬 검색
    3. Reciprocal Rank Fusion (RRF)으로 결과 융합

    Attributes:
        rag_chain: RAG 체인 인스턴스
        settings: 설정 객체
        llm: 쿼리 확장용 LLM

    Example:
        >>> retriever = MultiQueryRetriever(rag_chain)
        >>> docs, queries = retriever.retrieve("사업자등록 절차", "startup_funding")
    """

    def __init__(self, rag_chain: "RAGChain"):
        """MultiQueryRetriever를 초기화합니다.

        Args:
            rag_chain: RAG 체인 인스턴스
        """
        self.rag_chain = rag_chain
        self.settings = get_settings()
        self.llm = create_llm("쿼리확장", temperature=0.7)

    def _generate_queries(self, query: str) -> list[str]:
        """쿼리를 여러 관점으로 확장합니다.

        Args:
            query: 원본 쿼리

        Returns:
            확장된 쿼리 리스트 (원본 포함)
        """
        prompt = ChatPromptTemplate.from_messages([
            ("system", MULTI_QUERY_PROMPT),
            ("human", "{query}"),
        ])

        chain = prompt | self.llm | StrOutputParser()

        try:
            response = chain.invoke({"query": query})

            # 1. JSON 블록 추출 시도
            json_match = re.search(r"```json\s*(.*?)\s*```", response, re.DOTALL)
            if json_match:
                result = json.loads(json_match.group(1))
                expanded_queries = result.get("queries", [])
            else:
                try:
                    # 2. 직접 JSON 파싱 시도
                    result = json.loads(response)
                    expanded_queries = result.get("queries", [])
                except json.JSONDecodeError:
                    # 3. 라인 기반 파싱 fallback ("1. 쿼리", "- 쿼리" 형식)
                    lines = [line.strip() for line in response.split('\n') if line.strip()]
                    expanded_queries = []
                    for line in lines:
                        cleaned = re.sub(r'^\d+[.)]\s*|-\s*|\*\s*', '', line).strip()
                        if cleaned and cleaned != query and len(cleaned) >= 5:
                            expanded_queries.append(cleaned)

                    if expanded_queries:
                        logger.info("[Multi-Query] 라인 기반 파싱: %d개", len(expanded_queries))
                    else:
                        logger.warning("[Multi-Query] 모든 파싱 실패, 원본 쿼리만 사용")
                        return [query]

            # 원본 쿼리 + 확장 쿼리
            all_queries = [query] + expanded_queries[:self.settings.multi_query_count]

            logger.info(
                "[Multi-Query] 쿼리 확장: 원본='%s' → %d개",
                query[:30],
                len(all_queries),
            )
            for i, q in enumerate(all_queries):
                logger.debug("[Multi-Query] 쿼리 %d: %s", i + 1, q[:50])

            return all_queries

        except Exception as e:
            logger.warning("[Multi-Query] 쿼리 확장 실패: %s", e)
            return [query]  # 원본 쿼리만 반환

    def _reciprocal_rank_fusion(
        self,
        doc_lists: list[list[Document]],
        k: int = 60,
    ) -> list[Document]:
        """RRF (Reciprocal Rank Fusion)로 검색 결과를 융합합니다.

        Args:
            doc_lists: 각 쿼리별 검색 결과 리스트
            k: RRF 상수 (기본 60)

        Returns:
            융합된 문서 리스트 (점수순 정렬)
        """
        # 문서 ID → RRF 점수
        fused_scores: dict[str, float] = {}
        # 문서 ID → 문서 객체
        doc_map: dict[str, Document] = {}

        for doc_list in doc_lists:
            for rank, doc in enumerate(doc_list):
                # 문서 식별자 (내용 해시 사용)
                doc_id = hash(doc.page_content[:500])

                if doc_id not in doc_map:
                    doc_map[doc_id] = doc
                    fused_scores[doc_id] = 0.0

                # RRF 점수 누적
                fused_scores[doc_id] += 1 / (rank + k)

        # 점수 내림차순 정렬
        sorted_doc_ids = sorted(
            fused_scores.keys(),
            key=lambda x: fused_scores[x],
            reverse=True,
        )

        # 문서에 RRF 점수 추가
        result_docs = []
        for doc_id in sorted_doc_ids:
            doc = doc_map[doc_id]
            # 메타데이터에 RRF 점수 추가
            doc.metadata["rrf_score"] = fused_scores[doc_id]
            doc.metadata["score"] = fused_scores[doc_id]  # 통일된 점수 필드
            result_docs.append(doc)

        return result_docs

    def retrieve(
        self,
        query: str,
        domain: str,
        k: int | None = None,
        include_common: bool = True,
    ) -> tuple[list[Document], str]:
        """Multi-Query 검색을 수행합니다.

        Args:
            query: 원본 검색 쿼리
            domain: 검색할 도메인
            k: 최종 반환할 문서 수
            include_common: 공통 법령 DB 포함 여부

        Returns:
            (검색된 문서 리스트, 확장된 쿼리들 문자열)
        """
        k = k or self.settings.retrieval_k
        max_docs = self.settings.max_retrieval_docs

        # 1. 쿼리 확장
        queries = self._generate_queries(query)

        # 2. 각 쿼리로 검색 (쿼리 재작성/리랭킹 비활성화하여 중복 방지)
        doc_lists: list[list[Document]] = []

        for q in queries:
            docs = self.rag_chain.retrieve(
                query=q,
                domain=domain,
                k=k,
                include_common=include_common,
                use_query_rewrite=False,  # Multi-Query에서 이미 확장했으므로
                use_rerank=False,  # RRF 후 별도 처리
            )
            doc_lists.append(docs)
            logger.debug(
                "[Multi-Query] 쿼리='%s...' → %d건",
                q[:20],
                len(docs),
            )

        # 3. RRF 융합
        fused_docs = self._reciprocal_rank_fusion(doc_lists)

        # 4. 상위 K개 반환 (최대 max_docs)
        final_docs = fused_docs[:min(k, max_docs)]

        logger.info(
            "[Multi-Query] 융합 완료: %d개 쿼리 → %d건 → %d건",
            len(queries),
            len(fused_docs),
            len(final_docs),
        )

        queries_str = " | ".join(queries)
        return final_docs, queries_str

    async def aretrieve(
        self,
        query: str,
        domain: str,
        k: int | None = None,
        include_common: bool = True,
    ) -> tuple[list[Document], str]:
        """Multi-Query 검색을 비동기로 수행합니다.

        Args:
            query: 원본 검색 쿼리
            domain: 검색할 도메인
            k: 최종 반환할 문서 수
            include_common: 공통 법령 DB 포함 여부

        Returns:
            (검색된 문서 리스트, 확장된 쿼리들 문자열)
        """
        import asyncio

        return await asyncio.to_thread(
            self.retrieve,
            query,
            domain,
            k,
            include_common,
        )


@lru_cache(maxsize=1)
def get_multi_query_retriever(rag_chain: "RAGChain") -> MultiQueryRetriever:
    """MultiQueryRetriever 싱글톤 인스턴스를 반환합니다.

    Args:
        rag_chain: RAG 체인 인스턴스

    Returns:
        MultiQueryRetriever 인스턴스
    """
    return MultiQueryRetriever(rag_chain)
