"""RAG 체인 모듈.

벡터 스토어 검색과 LLM 응답 생성을 담당하는 RAG 체인을 구현합니다.
고급 기능: 쿼리 재작성, Hybrid Search, Re-ranking, 컨텍스트 압축, 캐싱
"""

import asyncio
import logging
import time
from typing import TYPE_CHECKING, Any

from langchain_core.documents import Document
from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.runnables import RunnablePassthrough
from langchain_openai import ChatOpenAI

from schemas.response import SourceDocument
from utils.config import get_settings
from utils.token_tracker import TokenUsageCallbackHandler
from vectorstores.chroma import ChromaVectorStore

if TYPE_CHECKING:
    from utils.feedback import SearchStrategy

logger = logging.getLogger(__name__)


class RAGChain:
    """RAG 체인 클래스.

    벡터 스토어에서 관련 문서를 검색하고 LLM을 사용하여 응답을 생성합니다.
    도메인별 검색과 공통 법령 DB 병합 검색을 지원합니다.

    Attributes:
        settings: 설정 객체
        vector_store: ChromaDB 벡터 스토어
        llm: OpenAI LLM 인스턴스

    Example:
        >>> chain = RAGChain()
        >>> result = chain.invoke(
        ...     query="사업자등록 절차 알려주세요",
        ...     domain="startup_funding",
        ...     system_prompt="당신은 창업 전문가입니다."
        ... )
    """

    def __init__(self, vector_store: ChromaVectorStore | None = None):
        """RAGChain을 초기화합니다.

        Args:
            vector_store: ChromaDB 벡터 스토어. None이면 새로 생성.
        """
        self.settings = get_settings()
        self.vector_store = vector_store or ChromaVectorStore()
        self.llm = ChatOpenAI(
            model=self.settings.openai_model,
            temperature=self.settings.openai_temperature,
            api_key=self.settings.openai_api_key,
            request_timeout=self.settings.llm_timeout,
            callbacks=[TokenUsageCallbackHandler("생성")],
        )

        # 고급 기능 초기화 (지연 로딩)
        self._query_processor = None
        self._response_cache = None
        self._hybrid_searcher = None
        self._reranker = None

    @property
    def query_processor(self):
        """QueryProcessor 인스턴스 (지연 로딩)."""
        if self._query_processor is None and self.settings.enable_query_rewrite:
            from utils.query import get_query_processor
            self._query_processor = get_query_processor()
        return self._query_processor

    @property
    def response_cache(self):
        """ResponseCache 인스턴스 (지연 로딩)."""
        if self._response_cache is None and self.settings.enable_response_cache:
            from utils.cache import ResponseCache
            self._response_cache = ResponseCache(
                max_size=self.settings.cache_max_size,
                ttl=self.settings.cache_ttl,
            )
        return self._response_cache

    @property
    def hybrid_searcher(self):
        """HybridSearcher 인스턴스 (지연 로딩)."""
        if self._hybrid_searcher is None and self.settings.enable_hybrid_search:
            from utils.search import HybridSearcher
            self._hybrid_searcher = HybridSearcher(self.vector_store)
        return self._hybrid_searcher

    @property
    def reranker(self):
        """LLMReranker 인스턴스 (지연 로딩)."""
        if self._reranker is None and self.settings.enable_reranking:
            from utils.search import LLMReranker
            self._reranker = LLMReranker()
        return self._reranker

    def retrieve(
        self,
        query: str,
        domain: str,
        k: int | None = None,
        include_common: bool = True,
        use_mmr: bool = True,
        use_query_rewrite: bool | None = None,
        use_rerank: bool | None = None,
        use_hybrid: bool | None = None,
        search_strategy: "SearchStrategy | None" = None,
    ) -> list[Document]:
        """벡터 스토어에서 관련 문서를 검색합니다.

        도메인별 벡터 DB를 검색하고, include_common이 True면
        공통 법령 DB(law_common)도 함께 검색하여 병합합니다.

        Args:
            query: 검색 쿼리
            domain: 검색할 도메인 (startup_funding, finance_tax, hr_labor)
            k: 검색 결과 개수 (None이면 설정값 사용)
            include_common: 공통 법령 DB 포함 여부
            use_mmr: MMR 검색 사용 여부 (다양성 확보)
            use_query_rewrite: 쿼리 재작성 사용 여부 (None이면 설정값)
            use_rerank: Re-ranking 사용 여부 (None이면 설정값)
            use_hybrid: Hybrid Search 사용 여부 (None이면 설정값)
            search_strategy: 피드백 기반 검색 전략 (재시도 시 사용)

        Returns:
            검색된 문서 리스트
        """
        # SearchStrategy가 있으면 전략 파라미터 적용
        if search_strategy:
            k = search_strategy.k
            k_common = search_strategy.k_common
            use_query_rewrite = search_strategy.use_query_rewrite
            use_rerank = search_strategy.use_rerank
            use_mmr = search_strategy.use_mmr
            fetch_k_mult = search_strategy.fetch_k_multiplier
            lambda_mult = search_strategy.mmr_lambda
            logger.debug(f"검색 전략 적용: k={k}, rewrite={use_query_rewrite}, rerank={use_rerank}")
        else:
            k = k or self.settings.retrieval_k
            k_common = self.settings.retrieval_k_common
            fetch_k_mult = self.settings.mmr_fetch_k_multiplier
            lambda_mult = self.settings.mmr_lambda_mult

        documents: list[Document] = []

        logger.info("=" * 60)
        logger.info("[검색 시작] 도메인=%s, 쿼리='%s'", domain, query[:50])

        # 쿼리 재작성 (설정에 따라)
        search_query = query
        if use_query_rewrite is None:
            use_query_rewrite = self.settings.enable_query_rewrite

        if use_query_rewrite and self.query_processor:
            logger.info("[쿼리 재작성] 활성화 (ENABLE_QUERY_REWRITE=true)")
            logger.info("[쿼리 재작성] 원본: %s", query)
            try:
                rewrite_start = time.time()
                search_query = self.query_processor.rewrite_query(query)
                rewrite_time = time.time() - rewrite_start
                logger.info("[쿼리 재작성] 재작성: %s", search_query)
                logger.info("[쿼리 재작성] 소요 시간: %.3fs", rewrite_time)
            except Exception as e:
                logger.warning("[쿼리 재작성] 실패: %s (원본 쿼리 사용)", e)
                search_query = query
        elif use_query_rewrite and not self.query_processor:
            logger.info("[쿼리 재작성] 비활성화 (QueryProcessor 미초기화)")
        else:
            logger.info("[쿼리 재작성] 비활성화 (ENABLE_QUERY_REWRITE=false)")

        # Re-ranking 사용 여부 결정
        if use_rerank is None:
            use_rerank = self.settings.enable_reranking

        # Hybrid Search 사용 여부 결정
        if use_hybrid is None:
            use_hybrid = self.settings.enable_hybrid_search

        # Hybrid Search 모드
        if use_hybrid and self.hybrid_searcher:
            logger.info("[검색] Hybrid Search 모드 (BM25+Vector+RRF)")

            # 도메인별 Hybrid Search
            try:
                domain_search_start = time.time()
                domain_docs = self.hybrid_searcher.search(
                    query=search_query,
                    domain=domain,
                    k=k,
                    use_rerank=use_rerank,  # HybridSearcher 내부에서 rerank 처리
                )
                domain_search_time = time.time() - domain_search_start
                documents.extend(domain_docs)
                logger.info("[검색] 도메인 DB (Hybrid): %d건 (%.3fs)", len(domain_docs), domain_search_time)
            except Exception as e:
                logger.error(f"Hybrid Search 실패 ({domain}): {e}")

            # 공통 법령 DB 검색 (Vector Search만 사용, rerank 생략)
            if include_common and domain != "law_common":
                try:
                    common_search_start = time.time()
                    common_docs = self.vector_store.max_marginal_relevance_search(
                        query=search_query,
                        domain="law_common",
                        k=k_common,
                        fetch_k=k_common * fetch_k_mult,
                        lambda_mult=lambda_mult,
                    )
                    common_search_time = time.time() - common_search_start
                    documents.extend(common_docs)
                    logger.info("[검색] 공통 법령 DB: %d건 (%.3fs)", len(common_docs), common_search_time)
                except Exception as e:
                    logger.error(f"공통 법령 DB 검색 실패: {e}")

            return documents

        # 기존 로직 (MMR/similarity search + separate rerank)
        fetch_k = k * 3 if use_rerank else k

        logger.info(
            "[검색] 검색 방법: %s, use_rerank=%s, fetch_k=%d",
            "MMR" if use_mmr else "similarity", use_rerank, fetch_k,
        )

        # 도메인별 검색 (MMR 또는 일반 유사도 검색)
        try:
            domain_search_start = time.time()
            if use_mmr:
                domain_docs = self.vector_store.max_marginal_relevance_search(
                    query=search_query,
                    domain=domain,
                    k=fetch_k,
                    fetch_k=fetch_k * fetch_k_mult,
                    lambda_mult=lambda_mult,
                )
            else:
                domain_docs = self.vector_store.similarity_search(
                    query=search_query,
                    domain=domain,
                    k=fetch_k,
                )
            domain_search_time = time.time() - domain_search_start
            documents.extend(domain_docs)
            logger.info("[검색] 도메인 DB: %d건 (%.3fs)", len(domain_docs), domain_search_time)
        except Exception as e:
            logger.error(f"도메인 검색 실패 ({domain}): {e}")

        # 공통 법령 DB 검색
        if include_common and domain != "law_common":
            common_fetch_k = k_common * 2 if use_rerank else k_common

            try:
                common_search_start = time.time()
                if use_mmr:
                    common_docs = self.vector_store.max_marginal_relevance_search(
                        query=search_query,
                        domain="law_common",
                        k=common_fetch_k,
                        fetch_k=common_fetch_k * fetch_k_mult,
                        lambda_mult=lambda_mult,
                    )
                else:
                    common_docs = self.vector_store.similarity_search(
                        query=search_query,
                        domain="law_common",
                        k=common_fetch_k,
                    )
                common_search_time = time.time() - common_search_start
                documents.extend(common_docs)
                logger.info("[검색] 공통 법령 DB: %d건 (%.3fs)", len(common_docs), common_search_time)
            except Exception as e:
                logger.error(f"공통 법령 DB 검색 실패: {e}")

        # Re-ranking (설정에 따라)
        if use_rerank and self.reranker and len(documents) > k:
            try:
                pre_rerank_count = len(documents)
                rerank_start = time.time()
                documents = self.reranker.rerank(query, documents, top_k=k)
                rerank_time = time.time() - rerank_start
                logger.info("[검색] Re-ranking: %d건 → %d건 (%.3fs)", pre_rerank_count, len(documents), rerank_time)
            except Exception as e:
                logger.warning(f"Re-ranking 실패: {e}")
                documents = documents[:k]
        elif len(documents) > k:
            documents = documents[:k]

        # 최종 검색 결과 로깅 (제목 및 출처)
        logger.info("[검색 완료] 총 %d건 검색됨", len(documents))
        for idx, doc in enumerate(documents):
            title = doc.metadata.get("title", "제목 없음")[:50]
            source = doc.metadata.get("source_name") or doc.metadata.get("source_file") or "출처 없음"
            score = doc.metadata.get("score")
            score_str = f"{score:.4f}" if score is not None else "N/A"
            logger.info("  [%d] %s (score: %s, 출처: %s)", idx + 1, title, score_str, source[:30])
        logger.info("=" * 60)

        return documents

    def retrieve_with_scores(
        self,
        query: str,
        domain: str,
        k: int | None = None,
        include_common: bool = True,
    ) -> list[tuple[Document, float]]:
        """유사도 점수와 함께 문서를 검색합니다.

        Args:
            query: 검색 쿼리
            domain: 검색할 도메인
            k: 검색 결과 개수
            include_common: 공통 법령 DB 포함 여부

        Returns:
            (문서, 유사도 점수) 튜플 리스트
        """
        k = k or self.settings.retrieval_k
        results: list[tuple[Document, float]] = []

        # 도메인별 검색
        try:
            domain_results = self.vector_store.similarity_search_with_score(
                query=query,
                domain=domain,
                k=k,
            )
            results.extend(domain_results)
        except Exception as e:
            logger.error(f"도메인 검색 실패 ({domain}): {e}")

        # 공통 법령 DB 검색
        if include_common and domain != "law_common":
            try:
                common_results = self.vector_store.similarity_search_with_score(
                    query=query,
                    domain="law_common",
                    k=self.settings.retrieval_k_common,
                )
                results.extend(common_results)
            except Exception as e:
                logger.error(f"공통 법령 DB 검색 실패: {e}")

        # 유사도 점수로 정렬 (낮을수록 유사)
        results.sort(key=lambda x: x[1])
        return results

    def format_context(self, documents: list[Document]) -> str:
        """문서 리스트를 컨텍스트 문자열로 포맷팅합니다.

        Args:
            documents: 문서 리스트

        Returns:
            포맷팅된 컨텍스트 문자열
        """
        if not documents:
            logger.info("[컨텍스트] 포맷팅 대상 문서 없음")
            return "관련 참고 자료가 없습니다."

        titles = [doc.metadata.get("title", "제목 없음") for doc in documents]
        logger.info("[컨텍스트] 포맷팅 대상 %d건: %s", len(documents), titles)

        context_parts = []
        for i, doc in enumerate(documents, 1):
            # source 정보 추출 (source_name 또는 source_file 사용)
            source = (
                doc.metadata.get("source_name")
                or doc.metadata.get("source_file")
                or doc.metadata.get("source")
                or "알 수 없음"
            )
            title = doc.metadata.get("title", "")
            content = doc.page_content[:self.settings.format_context_length]

            if title:
                context_parts.append(f"[{i}] {title}\n출처: {source}\n{content}")
            else:
                context_parts.append(f"[{i}] 출처: {source}\n{content}")

        return "\n\n---\n\n".join(context_parts)

    def documents_to_sources(self, documents: list[Document]) -> list[SourceDocument]:
        """문서 리스트를 SourceDocument 리스트로 변환합니다.

        Args:
            documents: 문서 리스트

        Returns:
            SourceDocument 리스트
        """
        sources = []
        for doc in documents:
            # source 정보 추출 (source_name 또는 source_file 사용)
            source = (
                doc.metadata.get("source_name")
                or doc.metadata.get("source_file")
                or doc.metadata.get("source")
            )
            sources.append(
                SourceDocument(
                    title=doc.metadata.get("title"),
                    content=doc.page_content[:self.settings.source_content_length],
                    source=source,
                    metadata=doc.metadata,
                )
            )
        return sources

    def invoke(
        self,
        query: str,
        domain: str,
        system_prompt: str,
        user_type: str = "prospective",
        company_context: str = "정보 없음",
        include_common: bool = True,
        search_strategy: "SearchStrategy | None" = None,
    ) -> dict[str, Any]:
        """RAG 체인을 실행하여 응답을 생성합니다.

        Args:
            query: 사용자 질문
            domain: 도메인
            system_prompt: 시스템 프롬프트
            user_type: 사용자 유형
            company_context: 기업 정보 컨텍스트
            include_common: 공통 법령 DB 포함 여부
            search_strategy: 피드백 기반 검색 전략

        Returns:
            응답 딕셔너리 (content, sources, documents, retrieve_time, generate_time)
        """
        # 문서 검색 - 시간 측정
        retrieve_start = time.time()
        documents = self.retrieve(
            query=query,
            domain=domain,
            include_common=include_common,
            search_strategy=search_strategy,
        )
        retrieve_time = time.time() - retrieve_start
        logger.info("[invoke] 검색 완료: %d건 (%.3fs)", len(documents), retrieve_time)

        # 컨텍스트 포맷팅
        context = self.format_context(documents)

        # 프롬프트 구성
        prompt = ChatPromptTemplate.from_messages([
            ("system", system_prompt),
            ("human", "{query}"),
        ])

        # 체인 실행 - 시간 측정
        chain = prompt | self.llm | StrOutputParser()

        generate_start = time.time()
        response = chain.invoke({
            "query": query,
            "context": context,
            "user_type": user_type,
            "company_context": company_context,
        })
        generate_time = time.time() - generate_start
        logger.info("[생성] LLM 응답 생성 완료 (%.3fs, %d자)", generate_time, len(response))

        return {
            "content": response,
            "sources": self.documents_to_sources(documents),
            "documents": documents,
            "retrieve_time": retrieve_time,
            "generate_time": generate_time,
        }

    async def ainvoke(
        self,
        query: str,
        domain: str,
        system_prompt: str,
        user_type: str = "prospective",
        company_context: str = "정보 없음",
        include_common: bool = True,
        use_cache: bool | None = None,
        search_strategy: "SearchStrategy | None" = None,
    ) -> dict[str, Any]:
        """RAG 체인을 비동기로 실행합니다.

        Args:
            query: 사용자 질문
            domain: 도메인
            system_prompt: 시스템 프롬프트
            user_type: 사용자 유형
            company_context: 기업 정보 컨텍스트
            include_common: 공통 법령 DB 포함 여부
            use_cache: 캐싱 사용 여부 (None이면 설정값)
            search_strategy: 피드백 기반 검색 전략

        Returns:
            응답 딕셔너리
        """
        # 캐시 확인 (설정에 따라)
        if use_cache is None:
            use_cache = self.settings.enable_response_cache

        if use_cache and self.response_cache:
            cached = self.response_cache.get(query, domain)
            if cached:
                logger.info("[ainvoke] 캐시 히트: '%s...'", query[:30])
                return cached

        logger.info("[ainvoke] 도메인=%s, 쿼리='%s'", domain, query[:50])

        # 쿼리 재작성 (비동기)
        search_query = query
        if self.settings.enable_query_rewrite and self.query_processor:
            try:
                rewrite_start = time.time()
                search_query = await self.query_processor.arewrite_query(query)
                rewrite_time = time.time() - rewrite_start
                logger.info("[ainvoke] 쿼리 재작성: '%s' → '%s' (%.3fs)", query[:30], search_query[:30], rewrite_time)
            except Exception as e:
                logger.warning(f"쿼리 재작성 실패: {e}")

        # 문서 검색 (동기 호출을 스레드로 실행) - 시간 측정
        retrieve_start = time.time()
        documents = await asyncio.to_thread(
            self._retrieve_with_rewritten_query,
            search_query,
            query,
            domain,
            None,
            include_common,
        )
        retrieve_time = time.time() - retrieve_start
        logger.info("[ainvoke] 검색 완료: %d건 (%.3fs)", len(documents), retrieve_time)

        # 컨텍스트 압축 (설정에 따라)
        if self.settings.enable_context_compression and self.query_processor:
            try:
                logger.info("[ainvoke] 컨텍스트 압축 적용: %d건", len(documents))
                documents = await self.query_processor.acompress_documents(
                    query, documents
                )
            except Exception as e:
                logger.warning(f"컨텍스트 압축 실패: {e}")

        # 컨텍스트 포맷팅
        context = self.format_context(documents)

        # 프롬프트 구성
        prompt = ChatPromptTemplate.from_messages([
            ("system", system_prompt),
            ("human", "{query}"),
        ])

        # 체인 실행 (타임아웃 적용) - 시간 측정
        chain = prompt | self.llm | StrOutputParser()

        generate_start = time.time()
        try:
            response = await asyncio.wait_for(
                chain.ainvoke({
                    "query": query,
                    "context": context,
                    "user_type": user_type,
                    "company_context": company_context,
                }),
                timeout=self.settings.llm_timeout,
            )
        except asyncio.TimeoutError:
            logger.error(f"LLM 타임아웃: {query[:30]}...")
            if self.settings.enable_fallback:
                response = self.settings.fallback_message
            else:
                raise
        generate_time = time.time() - generate_start
        logger.info("[생성] LLM 응답 생성 완료 (%.3fs, %d자)", generate_time, len(response))

        result = {
            "content": response,
            "sources": self.documents_to_sources(documents),
            "documents": documents,
            "retrieve_time": retrieve_time,
            "generate_time": generate_time,
        }

        # 캐시 저장
        if use_cache and self.response_cache and response != self.settings.fallback_message:
            self.response_cache.set(query, result, domain)

        return result

    def _retrieve_with_rewritten_query(
        self,
        search_query: str,
        original_query: str,
        domain: str,
        k: int | None,
        include_common: bool,
    ) -> list[Document]:
        """재작성된 쿼리로 검색합니다 (내부 헬퍼)."""
        k = k or self.settings.retrieval_k
        documents: list[Document] = []

        fetch_k_mult = self.settings.mmr_fetch_k_multiplier
        lambda_mult = self.settings.mmr_lambda_mult
        use_rerank = self.settings.enable_reranking
        fetch_k = k * 3 if use_rerank else k

        # 도메인별 검색
        try:
            domain_docs = self.vector_store.max_marginal_relevance_search(
                query=search_query,
                domain=domain,
                k=fetch_k,
                fetch_k=fetch_k * fetch_k_mult,
                lambda_mult=lambda_mult,
            )
            documents.extend(domain_docs)
        except Exception as e:
            logger.error(f"도메인 검색 실패 ({domain}): {e}")

        # 공통 법령 DB 검색
        if include_common and domain != "law_common":
            common_k = self.settings.retrieval_k_common
            common_fetch_k = common_k * 2 if use_rerank else common_k

            try:
                common_docs = self.vector_store.max_marginal_relevance_search(
                    query=search_query,
                    domain="law_common",
                    k=common_fetch_k,
                    fetch_k=common_fetch_k * fetch_k_mult,
                    lambda_mult=lambda_mult,
                )
                documents.extend(common_docs)
            except Exception as e:
                logger.error(f"공통 법령 DB 검색 실패: {e}")

        # Re-ranking
        if use_rerank and self.reranker and len(documents) > k:
            try:
                documents = self.reranker.rerank(original_query, documents, top_k=k)
            except Exception as e:
                logger.warning(f"Re-ranking 실패: {e}")
                documents = documents[:k]
        elif len(documents) > k:
            documents = documents[:k]

        return documents

    async def astream(
        self,
        query: str,
        domain: str,
        system_prompt: str,
        user_type: str = "prospective",
        company_context: str = "정보 없음",
        include_common: bool = True,
    ):
        """RAG 체인을 스트리밍으로 실행합니다.

        Args:
            query: 사용자 질문
            domain: 도메인
            system_prompt: 시스템 프롬프트
            user_type: 사용자 유형
            company_context: 기업 정보 컨텍스트
            include_common: 공통 법령 DB 포함 여부

        Yields:
            응답 토큰
        """
        # 문서 검색 (동기 호출을 스레드로 실행)
        documents = await asyncio.to_thread(
            self.retrieve,
            query,
            domain,
            None,
            include_common,
        )

        # 컨텍스트 포맷팅
        context = self.format_context(documents)

        # 프롬프트 구성
        prompt = ChatPromptTemplate.from_messages([
            ("system", system_prompt),
            ("human", "{query}"),
        ])

        # 체인 실행 (스트리밍)
        chain = prompt | self.llm | StrOutputParser()

        async for chunk in chain.astream({
            "query": query,
            "context": context,
            "user_type": user_type,
            "company_context": company_context,
        }):
            yield chunk
