"""쿼리 처리 유틸리티 모듈.

쿼리 재작성, 확장, 컨텍스트 압축, Multi-Query 검색 등의 기능을 제공합니다.
"""

import asyncio
import hashlib
import json
import logging
import re
from collections import OrderedDict
from typing import TYPE_CHECKING, Any

from langchain_core.documents import Document
from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import ChatPromptTemplate

from utils.config import create_llm, get_settings
from utils.prompts import CONTEXT_COMPRESSION_PROMPT, MULTI_QUERY_PROMPT, QUERY_REWRITE_PROMPT
from utils.search import reciprocal_rank_fusion_docs

if TYPE_CHECKING:
    from chains.rag_chain import RAGChain

logger = logging.getLogger(__name__)


class QueryProcessor:
    """쿼리 처리 클래스.

    쿼리 재작성, 확장, 해시 생성 등의 기능을 제공합니다.
    """

    def __init__(self):
        """QueryProcessor를 초기화합니다."""
        self.settings = get_settings()
        self.llm = create_llm("쿼리재작성", temperature=0.0)
        self._rewrite_chain = self._build_rewrite_chain()
        self._compression_chain = self._build_compression_chain()
        self._rewrite_cache: OrderedDict[str, str] = OrderedDict()
        self._rewrite_cache_max_size = 500

    def _build_rewrite_chain(self):
        """쿼리 재작성 체인을 빌드합니다."""
        prompt = ChatPromptTemplate.from_template(QUERY_REWRITE_PROMPT)
        return prompt | self.llm | StrOutputParser()

    def _build_compression_chain(self):
        """컨텍스트 압축 체인을 빌드합니다."""
        prompt = ChatPromptTemplate.from_template(CONTEXT_COMPRESSION_PROMPT)
        return prompt | self.llm | StrOutputParser()

    def rewrite_query(self, query: str) -> str:
        """쿼리를 검색에 최적화된 형태로 재작성합니다.

        Args:
            query: 원본 사용자 쿼리

        Returns:
            재작성된 쿼리
        """
        cache_key = query.strip().lower()
        if cache_key in self._rewrite_cache:
            self._rewrite_cache.move_to_end(cache_key)
            logger.debug(f"쿼리 재작성 캐시 히트: '{query}'")
            return self._rewrite_cache[cache_key]

        try:
            rewritten = self._rewrite_chain.invoke({"query": query})
            rewritten = rewritten.strip()
            logger.debug(f"쿼리 재작성: '{query}' -> '{rewritten}'")

            if len(self._rewrite_cache) >= self._rewrite_cache_max_size:
                self._rewrite_cache.popitem(last=False)
            self._rewrite_cache[cache_key] = rewritten

            return rewritten
        except Exception as e:
            logger.warning(f"쿼리 재작성 실패, 원본 사용: {e}")
            return query

    async def arewrite_query(self, query: str) -> str:
        """쿼리를 비동기로 재작성합니다.

        Args:
            query: 원본 사용자 쿼리

        Returns:
            재작성된 쿼리
        """
        cache_key = query.strip().lower()
        if cache_key in self._rewrite_cache:
            self._rewrite_cache.move_to_end(cache_key)
            logger.debug(f"쿼리 재작성 캐시 히트: '{query}'")
            return self._rewrite_cache[cache_key]

        try:
            rewritten = await self._rewrite_chain.ainvoke({"query": query})
            rewritten = rewritten.strip()
            logger.debug(f"쿼리 재작성: '{query}' -> '{rewritten}'")

            if len(self._rewrite_cache) >= self._rewrite_cache_max_size:
                self._rewrite_cache.popitem(last=False)
            self._rewrite_cache[cache_key] = rewritten

            return rewritten
        except Exception as e:
            logger.warning(f"쿼리 재작성 실패, 원본 사용: {e}")
            return query

    async def acompress_context(self, query: str, document: str) -> str:
        """문서를 비동기로 압축합니다.

        Args:
            query: 사용자 질문
            document: 원본 문서 내용

        Returns:
            압축된 컨텍스트
        """
        try:
            if len(document) < 300:
                return document

            compressed = await self._compression_chain.ainvoke({
                "query": query,
                "document": document,
            })
            compressed = compressed.strip()

            if "관련 내용 없음" in compressed or len(compressed) < 50:
                return document[:500]

            return compressed
        except Exception as e:
            logger.warning(f"컨텍스트 압축 실패: {e}")
            return document[:500]

    async def acompress_documents(
        self,
        query: str,
        documents: list[Document],
        max_concurrent: int = 5,
    ) -> list[Document]:
        """여러 문서를 병렬로 압축합니다.

        Args:
            query: 사용자 질문
            documents: 문서 리스트
            max_concurrent: 최대 동시 처리 수

        Returns:
            압축된 문서 리스트
        """
        semaphore = asyncio.Semaphore(max_concurrent)

        async def compress_one(doc: Document) -> Document:
            async with semaphore:
                try:
                    compressed_content = await self.acompress_context(
                        query, doc.page_content
                    )
                    return Document(
                        page_content=compressed_content,
                        metadata=doc.metadata,
                    )
                except Exception as e:
                    logger.warning(f"문서 압축 실패 (원본 사용): {e}")
                    return doc

        tasks = [compress_one(doc) for doc in documents]
        return await asyncio.gather(*tasks)

    @staticmethod
    def generate_cache_key(query: str, domain: str | None = None) -> str:
        """쿼리에 대한 캐시 키를 생성합니다.

        Args:
            query: 사용자 쿼리
            domain: 도메인 (선택)

        Returns:
            캐시 키 (MD5 해시)
        """
        # 정규화: 소문자, 공백 정리
        normalized = query.lower().strip()
        normalized = re.sub(r'\s+', ' ', normalized)

        if domain:
            normalized = f"{domain}:{normalized}"

        return hashlib.md5(normalized.encode()).hexdigest()

    @staticmethod
    def extract_keywords(query: str) -> list[str]:
        """쿼리에서 키워드를 추출합니다.

        Args:
            query: 사용자 쿼리

        Returns:
            키워드 리스트
        """
        # 불용어 제거
        stopwords = {
            "은", "는", "이", "가", "을", "를", "의", "에", "에서",
            "으로", "로", "와", "과", "도", "만", "까지", "부터",
            "어떻게", "무엇", "언제", "어디", "왜", "얼마나",
            "할", "수", "있", "없", "해야", "하나요", "인가요",
            "알려주세요", "해주세요", "싶어요", "궁금해요",
        }

        # 단어 분리 (간단한 방식)
        words = re.findall(r'[가-힣a-zA-Z0-9]+', query)

        # 불용어 제거 및 2글자 이상만
        keywords = [
            word for word in words
            if word not in stopwords and len(word) >= 2
        ]

        return keywords


# 싱글톤 인스턴스
_query_processor: QueryProcessor | None = None


def get_query_processor() -> QueryProcessor:
    """QueryProcessor 싱글톤 인스턴스를 반환합니다.

    Returns:
        QueryProcessor 인스턴스
    """
    global _query_processor
    if _query_processor is None:
        _query_processor = QueryProcessor()
    return _query_processor


# ===================================================================
# Multi-Query 검색
# ===================================================================

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

    @staticmethod
    def _reciprocal_rank_fusion(
        doc_lists: list[list[Document]],
        k: int = 60,
    ) -> list[Document]:
        """RRF (Reciprocal Rank Fusion)로 검색 결과를 융합합니다.

        search.reciprocal_rank_fusion_docs에 위임합니다.

        Args:
            doc_lists: 각 쿼리별 검색 결과 리스트
            k: RRF 상수 (기본 60)

        Returns:
            융합된 문서 리스트 (점수순 정렬)
        """
        return reciprocal_rank_fusion_docs(doc_lists, k=k)

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
        return await asyncio.to_thread(
            self.retrieve,
            query,
            domain,
            k,
            include_common,
        )


_multi_query_retriever: MultiQueryRetriever | None = None


def get_multi_query_retriever(rag_chain: "RAGChain") -> MultiQueryRetriever:
    """MultiQueryRetriever 싱글톤 인스턴스를 반환합니다.

    Args:
        rag_chain: RAG 체인 인스턴스

    Returns:
        MultiQueryRetriever 인스턴스
    """
    global _multi_query_retriever
    if _multi_query_retriever is None:
        _multi_query_retriever = MultiQueryRetriever(rag_chain)
    return _multi_query_retriever


def reset_multi_query_retriever() -> None:
    """MultiQueryRetriever 싱글톤을 리셋합니다 (테스트용)."""
    global _multi_query_retriever
    _multi_query_retriever = None
