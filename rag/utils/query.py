"""쿼리 처리 유틸리티 모듈.

쿼리 확장, 컨텍스트 압축, Multi-Query 검색 기능을 제공합니다.
"""

import asyncio
import hashlib
import json
import logging
import re
from typing import TYPE_CHECKING

from langchain_core.documents import Document
from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import ChatPromptTemplate

from utils.config import create_llm, get_settings
from utils.prompts import CONTEXT_COMPRESSION_PROMPT, MULTI_QUERY_PROMPT

if TYPE_CHECKING:
    from chains.rag_chain import RAGChain
    from utils.feedback import SearchStrategy

logger = logging.getLogger(__name__)


class QueryProcessor:
    """쿼리 처리 클래스.

    컨텍스트 압축 및 쿼리 유틸리티 클래스.
    쿼리 재작성(Query Rewrite) 기능은 제거되었으며,
    현재는 컨텍스트 압축, 키워드 추출, 캐시 키 생성을 전담합니다.
    """

    def __init__(self):
        """QueryProcessor를 초기화합니다."""
        self.settings = get_settings()
        self.llm = create_llm("컨텍스트압축", temperature=0.0)
        self._compression_chain = self._build_compression_chain()

    def _build_compression_chain(self):
        """컨텍스트 압축 체인을 빌드합니다."""
        prompt = ChatPromptTemplate.from_template(CONTEXT_COMPRESSION_PROMPT)
        return prompt | self.llm | StrOutputParser()

    def compress_context(self, query: str, document: str) -> str:
        """문서에서 질문과 관련된 부분만 추출합니다.

        Args:
            query: 사용자 질문
            document: 원본 문서 내용

        Returns:
            압축된 컨텍스트
        """
        try:
            # 문서가 짧으면 그대로 반환
            if len(document) < 300:
                return document

            compressed = self._compression_chain.invoke({
                "query": query,
                "document": document,
            })
            compressed = compressed.strip()

            # "관련 내용 없음"이면 원본 반환
            if "관련 내용 없음" in compressed or len(compressed) < 50:
                return document[:500]

            return compressed
        except Exception as e:
            logger.warning(f"컨텍스트 압축 실패: {e}")
            return document[:500]

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
                        logger.warning("[Multi-Query] 모든 파싱 실패")
                        return []

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
            return []

    @staticmethod
    def _make_doc_key(doc: Document) -> str:
        """문서 식별용 안정 키를 생성합니다."""
        metadata = doc.metadata or {}
        source = (
            str(metadata.get("source_name") or "")
            or str(metadata.get("source_file") or "")
            or str(metadata.get("source") or "")
        )
        title = str(metadata.get("title") or "")
        content = doc.page_content.strip()[:1000]
        raw = f"{source}|{title}|{content}"
        return hashlib.sha256(raw.encode("utf-8")).hexdigest()

    @staticmethod
    def _distance_to_similarity(distance: float) -> float:
        """Chroma distance를 코사인 유사도(0~1)로 변환합니다."""
        similarity = 1.0 - distance
        return max(0.0, min(1.0, similarity))

    def _collect_embedding_similarity_map(
        self,
        query: str,
        domain: str,
        candidate_docs: list[Document],
        include_common: bool,
    ) -> dict[str, float]:
        """원본 쿼리 기준 후보 문서의 embedding similarity 맵을 생성합니다."""
        if not candidate_docs:
            return {}

        target_domains = [domain]
        if include_common and domain != "law_common":
            target_domains.append("law_common")

        search_k = max(
            len(candidate_docs) * 2,
            self.settings.max_retrieval_docs,
            self.settings.retrieval_k + (
                self.settings.retrieval_k_common if include_common and domain != "law_common" else 0
            ),
        )

        similarity_map: dict[str, float] = {}
        for target_domain in target_domains:
            try:
                scored_docs = self.rag_chain.vector_store.similarity_search_with_score(
                    query=query,
                    domain=target_domain,
                    k=search_k,
                )
            except Exception as e:
                logger.warning(
                    "[Multi-Query] embedding 유사도 계산 실패 (domain=%s): %s",
                    target_domain,
                    e,
                )
                continue

            for scored_doc, distance in scored_docs:
                doc_key = self._make_doc_key(scored_doc)
                similarity = self._distance_to_similarity(float(distance))
                current = similarity_map.get(doc_key)
                if current is None or similarity > current:
                    similarity_map[doc_key] = similarity

        return similarity_map

    def _apply_embedding_similarity_filter(
        self,
        query: str,
        domain: str,
        fused_docs: list[Document],
        include_common: bool,
    ) -> tuple[list[Document], bool]:
        """RRF 후보에 embedding similarity를 주입하고 임계값으로 필터링합니다."""
        if not fused_docs:
            return [], False

        threshold = self.settings.min_doc_embedding_similarity
        similarity_map = self._collect_embedding_similarity_map(
            query=query,
            domain=domain,
            candidate_docs=fused_docs,
            include_common=include_common,
        )

        for doc in fused_docs:
            doc_key = self._make_doc_key(doc)
            metadata = doc.metadata or {}
            metadata["embedding_similarity"] = similarity_map.get(doc_key, 0.0)
            doc.metadata = metadata

        filtered_docs = [
            doc
            for doc in fused_docs
            if doc.metadata.get("embedding_similarity", 0.0) >= threshold
        ]

        used_fallback = False
        if not filtered_docs and fused_docs:
            used_fallback = True
            filtered_docs = [fused_docs[0]]
            logger.warning(
                "[Multi-Query] embedding 필터 전부 탈락. RRF Top1 유지 (threshold=%.2f)",
                threshold,
            )

        logger.info(
            "[Multi-Query] 후보=%d, embedding 필터 통과=%d, fallback=%s",
            len(fused_docs),
            len(filtered_docs),
            used_fallback,
        )

        return filtered_docs, used_fallback

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
                # 문서 식별자 (안정 해시 사용)
                doc_id = self._make_doc_key(doc)

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
            # RRF 점수는 랭킹 전용 메타데이터로만 유지
            metadata = doc.metadata or {}
            metadata["rrf_score"] = fused_scores[doc_id]
            metadata["ranking_score"] = fused_scores[doc_id]
            doc.metadata = metadata
            result_docs.append(doc)

        return result_docs

    def retrieve(
        self,
        query: str,
        domain: str,
        k: int | None = None,
        include_common: bool = True,
        use_mmr: bool | None = None,
        use_rerank: bool | None = None,
        use_hybrid: bool | None = None,
        search_strategy: "SearchStrategy | None" = None,
    ) -> tuple[list[Document], str]:
        """Multi-Query 검색을 수행합니다.

        Args:
            query: 원본 검색 쿼리
            domain: 검색할 도메인
            k: 최종 반환할 문서 수
            include_common: 공통 법령 DB 포함 여부
            use_mmr: 단일 쿼리 primitive 검색 시 MMR 사용 여부
            use_rerank: 최종 융합 결과 Re-ranking 사용 여부
            use_hybrid: 단일 쿼리 primitive 검색 시 Hybrid 사용 여부
            search_strategy: 검색 전략

        Returns:
            (검색된 문서 리스트, 확장된 쿼리들 문자열)
        """
        if search_strategy is not None:
            target_k = search_strategy.k
            target_use_mmr = search_strategy.use_mmr if use_mmr is None else use_mmr
            target_use_rerank = search_strategy.use_rerank if use_rerank is None else use_rerank
            target_use_hybrid = search_strategy.use_hybrid if use_hybrid is None else use_hybrid
        else:
            target_k = k or self.settings.retrieval_k
            target_use_mmr = use_mmr if use_mmr is not None else True
            target_use_rerank = use_rerank if use_rerank is not None else self.settings.enable_reranking
            target_use_hybrid = use_hybrid

        max_docs = self.settings.max_retrieval_docs

        # 1. 쿼리 확장
        queries = self._generate_queries(query)
        if not queries:
            logger.warning("[Multi-Query] 쿼리 확장 실패로 검색 중단")
            return [], ""

        # 2. 각 쿼리로 primitive 검색 (쿼리별 rerank 비활성화 후 RRF 적용)
        doc_lists: list[list[Document]] = []

        for q in queries:
            docs = self.rag_chain._retrieve_documents(
                query=q,
                domain=domain,
                k=target_k,
                include_common=include_common,
                use_mmr=target_use_mmr,
                use_rerank=False,
                use_hybrid=target_use_hybrid,
                search_strategy=search_strategy,
            )
            doc_lists.append(docs)
            logger.debug(
                "[Multi-Query] 쿼리='%s...' → %d건",
                q[:20],
                len(docs),
            )

        # 3. RRF 융합
        fused_docs = self._reciprocal_rank_fusion(doc_lists)

        # 4. embedding 유사도 주입 + 품질 필터
        filtered_docs, _ = self._apply_embedding_similarity_filter(
            query=query,
            domain=domain,
            fused_docs=fused_docs,
            include_common=include_common,
        )

        # 5. 최종 Re-ranking (설정/전략에 따라)
        final_k = min(target_k, max_docs)
        if target_use_rerank and self.rag_chain.reranker and len(filtered_docs) > final_k:
            try:
                final_docs = self.rag_chain.reranker.rerank(
                    query=query,
                    documents=filtered_docs,
                    top_k=final_k,
                )
            except Exception as e:
                logger.warning("[Multi-Query] 최종 Re-ranking 실패: %s", e)
                final_docs = filtered_docs[:final_k]
        else:
            final_docs = filtered_docs[:final_k]

        logger.info(
            "[Multi-Query] 융합 완료: %d개 쿼리 → %d건(RRF) → %d건(최종)",
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
        use_mmr: bool | None = None,
        use_rerank: bool | None = None,
        use_hybrid: bool | None = None,
        search_strategy: "SearchStrategy | None" = None,
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
            use_mmr,
            use_rerank,
            use_hybrid,
            search_strategy,
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
