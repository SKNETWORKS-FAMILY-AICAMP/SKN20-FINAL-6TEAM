"""Reranker 모듈.

Cross-Encoder 및 LLM 기반 Re-ranking 기능을 제공합니다.
"""

import asyncio
import logging
import re
from abc import ABC, abstractmethod

from langchain_core.documents import Document
from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import ChatPromptTemplate

from utils.config import create_llm, get_settings
from utils.prompts import RERANK_PROMPT

logger = logging.getLogger(__name__)


class BaseReranker(ABC):
    """Reranker 추상 기본 클래스.

    모든 Reranker 구현체는 이 클래스를 상속해야 합니다.
    """

    @abstractmethod
    def rerank(
        self,
        query: str,
        documents: list[Document],
        top_k: int = 5,
    ) -> list[Document]:
        """문서를 재정렬합니다.

        Args:
            query: 검색 쿼리
            documents: 문서 리스트
            top_k: 반환할 문서 수

        Returns:
            재정렬된 문서 리스트
        """
        pass

    @abstractmethod
    async def arerank(
        self,
        query: str,
        documents: list[Document],
        top_k: int = 5,
        max_concurrent: int = 5,
    ) -> list[Document]:
        """문서를 비동기로 재정렬합니다.

        Args:
            query: 검색 쿼리
            documents: 문서 리스트
            top_k: 반환할 문서 수
            max_concurrent: 최대 동시 처리 수

        Returns:
            재정렬된 문서 리스트
        """
        pass


class CrossEncoderReranker(BaseReranker):
    """Cross-Encoder 기반 Reranker.

    sentence-transformers CrossEncoder를 사용한 빠른 재정렬을 수행합니다.
    한국어 지원 모델(BAAI/bge-reranker-base)을 기본으로 사용합니다.

    Attributes:
        model_name: CrossEncoder 모델명
        model: CrossEncoder 인스턴스
    """

    def __init__(self, model_name: str | None = None):
        """CrossEncoderReranker를 초기화합니다.

        Args:
            model_name: CrossEncoder 모델명 (None이면 설정값 사용)
        """
        self.settings = get_settings()
        self.model_name = model_name or self.settings.cross_encoder_model
        self._model = None  # 지연 로딩
        self._model_load_failed = False  # 로딩 실패 상태

    @property
    def model(self):
        """CrossEncoder 모델 인스턴스 (지연 로딩)."""
        if self._model is None:
            if self._model_load_failed:
                return None
            logger.info("[CrossEncoder] 모델 로딩: %s", self.model_name)
            try:
                from sentence_transformers import CrossEncoder
                self._model = CrossEncoder(self.model_name)
                logger.info("[CrossEncoder] 모델 로딩 완료")
            except Exception as e:
                logger.error("[CrossEncoder] 모델 로딩 실패: %s — reranking 스킵", e)
                self._model_load_failed = True
                return None
        return self._model

    def rerank(
        self,
        query: str,
        documents: list[Document],
        top_k: int = 5,
    ) -> list[Document]:
        """문서를 재정렬합니다.

        Args:
            query: 검색 쿼리
            documents: 문서 리스트
            top_k: 반환할 문서 수

        Returns:
            재정렬된 문서 리스트
        """
        if len(documents) <= top_k:
            return documents

        logger.info("[리랭킹] CrossEncoder 시작: %d건 → top_%d", len(documents), top_k)

        # 모델 로딩 실패 시 원본 반환
        if self.model is None:
            logger.warning("[리랭킹] CrossEncoder 모델 미사용 가능 — 원본 순서 유지")
            return documents[:top_k]

        # 쿼리-문서 쌍 생성 (Cross-Encoder 512 토큰 제한으로 500자로 제한)
        pairs = [(query, doc.page_content[:500]) for doc in documents]

        # CrossEncoder로 점수 계산
        try:
            scores = self.model.predict(pairs)

            # 점수와 문서를 쌍으로 묶어 정렬 (numpy float를 명시적으로 Python float로 변환)
            scored_docs = list(zip(documents, [float(s) for s in scores]))
            scored_docs.sort(key=lambda x: x[1], reverse=True)

            scores_list = [s for _, s in scored_docs]
            logger.info(
                "[리랭킹] CrossEncoder 완료: 점수 범위 %.4f~%.4f",
                min(scores_list), max(scores_list)
            )

            return [doc for doc, _ in scored_docs[:top_k]]

        except Exception as e:
            logger.warning("[리랭킹] CrossEncoder 실패: %s (원본 순서 유지)", e)
            return documents[:top_k]

    async def arerank(
        self,
        query: str,
        documents: list[Document],
        top_k: int = 5,
        max_concurrent: int = 5,
    ) -> list[Document]:
        """문서를 비동기로 재정렬합니다.

        CrossEncoder는 배치 처리가 빠르므로 동기 함수를 스레드로 실행합니다.

        Args:
            query: 검색 쿼리
            documents: 문서 리스트
            top_k: 반환할 문서 수
            max_concurrent: 최대 동시 처리 수 (CrossEncoder에서는 미사용)

        Returns:
            재정렬된 문서 리스트
        """
        return await asyncio.to_thread(self.rerank, query, documents, top_k)


class RunPodReranker(BaseReranker):
    """RunPod Serverless를 통한 Re-ranking.

    RunPod GPU 엔드포인트에 HTTP 요청을 보내 문서를 재정렬합니다.
    임베딩과 동일한 엔드포인트를 사용합니다 (task="rerank").

    Attributes:
        api_url: RunPod runsync API URL
        headers: HTTP 요청 헤더 (인증 포함)
    """

    def __init__(self, api_key: str, endpoint_id: str) -> None:
        """RunPodReranker를 초기화합니다.

        Args:
            api_key: RunPod API 키
            endpoint_id: RunPod Serverless Endpoint ID
        """
        self.api_url = f"https://api.runpod.ai/v2/{endpoint_id}/runsync"
        self.headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        }

    def rerank(
        self,
        query: str,
        documents: list[Document],
        top_k: int = 5,
    ) -> list[Document]:
        """문서를 동기로 재정렬합니다.

        Args:
            query: 검색 쿼리
            documents: 문서 리스트
            top_k: 반환할 문서 수

        Returns:
            재정렬된 문서 리스트
        """
        if len(documents) <= top_k:
            return documents

        import httpx

        logger.info("[리랭킹] RunPod 시작: %d건 → top_%d", len(documents), top_k)

        doc_texts = [doc.page_content[:500] for doc in documents]
        payload = {
            "input": {
                "task": "rerank",
                "query": query,
                "documents": doc_texts,
            }
        }

        try:
            with httpx.Client(timeout=60.0) as client:
                response = client.post(self.api_url, json=payload, headers=self.headers)
                response.raise_for_status()
                result = response.json()

            if result.get("status") != "COMPLETED":
                logger.warning("[리랭킹] RunPod 실패: status=%s (원본 순서 유지)", result.get("status"))
                return documents[:top_k]

            scores = [float(s) for s in result["output"]["scores"]]
            scored_docs = sorted(zip(documents, scores), key=lambda x: x[1], reverse=True)

            logger.info(
                "[리랭킹] RunPod 완료: 점수 범위 %.4f~%.4f",
                min(scores), max(scores),
            )

            return [doc for doc, _ in scored_docs[:top_k]]

        except Exception as e:
            logger.warning("[리랭킹] RunPod 실패: %s (원본 순서 유지)", e)
            return documents[:top_k]

    async def arerank(
        self,
        query: str,
        documents: list[Document],
        top_k: int = 5,
        max_concurrent: int = 5,
    ) -> list[Document]:
        """문서를 비동기로 재정렬합니다.

        Args:
            query: 검색 쿼리
            documents: 문서 리스트
            top_k: 반환할 문서 수
            max_concurrent: 최대 동시 처리 수 (RunPod에서는 미사용)

        Returns:
            재정렬된 문서 리스트
        """
        if len(documents) <= top_k:
            return documents

        import httpx

        logger.info("[리랭킹] RunPod 비동기 시작: %d건 → top_%d", len(documents), top_k)

        doc_texts = [doc.page_content[:500] for doc in documents]
        payload = {
            "input": {
                "task": "rerank",
                "query": query,
                "documents": doc_texts,
            }
        }

        try:
            async with httpx.AsyncClient(timeout=60.0) as client:
                response = await client.post(self.api_url, json=payload, headers=self.headers)
                response.raise_for_status()
                result = response.json()

            if result.get("status") != "COMPLETED":
                logger.warning("[리랭킹] RunPod 실패: status=%s (원본 순서 유지)", result.get("status"))
                return documents[:top_k]

            scores = [float(s) for s in result["output"]["scores"]]
            scored_docs = sorted(zip(documents, scores), key=lambda x: x[1], reverse=True)

            logger.info(
                "[리랭킹] RunPod 완료: 점수 범위 %.4f~%.4f",
                min(scores), max(scores),
            )

            return [doc for doc, _ in scored_docs[:top_k]]

        except Exception as e:
            logger.warning("[리랭킹] RunPod 실패: %s (원본 순서 유지)", e)
            return documents[:top_k]


class LLMReranker(BaseReranker):
    """LLM 기반 Reranker.

    Cross-encoder 스타일의 LLM 기반 재정렬을 수행합니다.
    """

    def __init__(self):
        """LLMReranker를 초기화합니다."""
        self.settings = get_settings()
        self.llm = create_llm("리랭킹", temperature=0.0)
        self._chain = self._build_chain()

    def _build_chain(self):
        """Re-ranking 체인을 빌드합니다."""
        prompt = ChatPromptTemplate.from_template(RERANK_PROMPT)
        return prompt | self.llm | StrOutputParser()

    def _parse_score(self, response: str) -> float:
        """응답에서 점수를 추출합니다."""
        try:
            # 숫자만 추출
            numbers = re.findall(r'\d+(?:\.\d+)?', response)
            if numbers:
                score = float(numbers[0])
                return min(10, max(0, score))  # 0-10 범위로 클램프
        except ValueError:
            pass
        return 5.0  # 기본값

    def rerank(
        self,
        query: str,
        documents: list[Document],
        top_k: int = 5,
    ) -> list[Document]:
        """문서를 재정렬합니다.

        Args:
            query: 검색 쿼리
            documents: 문서 리스트
            top_k: 반환할 문서 수

        Returns:
            재정렬된 문서 리스트
        """
        if len(documents) <= top_k:
            return documents

        logger.info("[리랭킹] LLM 시작: %d건 → top_%d", len(documents), top_k)

        scored_docs: list[tuple[Document, float]] = []

        for doc in documents:
            try:
                response = self._chain.invoke({
                    "query": query,
                    "document": doc.page_content[:500],
                })
                score = self._parse_score(response)
                scored_docs.append((doc, score))
            except Exception as e:
                logger.warning(f"Re-ranking 실패: {e}")
                scored_docs.append((doc, 5.0))

        # 점수로 정렬
        scored_docs.sort(key=lambda x: x[1], reverse=True)

        scores_list = [s for _, s in scored_docs]
        logger.info("[리랭킹] LLM 완료: 점수 범위 %.1f~%.1f", min(scores_list), max(scores_list))

        return [doc for doc, _ in scored_docs[:top_k]]

    async def arerank(
        self,
        query: str,
        documents: list[Document],
        top_k: int = 5,
        max_concurrent: int = 5,
    ) -> list[Document]:
        """문서를 비동기로 재정렬합니다.

        Args:
            query: 검색 쿼리
            documents: 문서 리스트
            top_k: 반환할 문서 수
            max_concurrent: 최대 동시 처리 수

        Returns:
            재정렬된 문서 리스트
        """
        if len(documents) <= top_k:
            return documents

        logger.info("[리랭킹] LLM 시작: %d건 → top_%d", len(documents), top_k)

        semaphore = asyncio.Semaphore(max_concurrent)

        async def score_one(doc: Document) -> tuple[Document, float]:
            async with semaphore:
                try:
                    response = await self._chain.ainvoke({
                        "query": query,
                        "document": doc.page_content[:500],
                    })
                    score = self._parse_score(response)
                    return doc, score
                except Exception as e:
                    logger.warning(f"Re-ranking 실패: {e}")
                    return doc, 5.0

        tasks = [score_one(doc) for doc in documents]
        results = await asyncio.gather(*tasks)

        # 점수로 정렬
        results = sorted(results, key=lambda x: x[1], reverse=True)

        scores_list = [s for _, s in results]
        logger.info("[리랭킹] LLM 완료: 점수 범위 %.1f~%.1f", min(scores_list), max(scores_list))

        return [doc for doc, _ in results[:top_k]]


# 싱글톤 인스턴스
_reranker: BaseReranker | None = None


def get_reranker(reranker_type: str | None = None) -> BaseReranker:
    """Reranker 인스턴스를 반환합니다 (싱글톤).

    EMBEDDING_PROVIDER=runpod이면 RunPodReranker를 반환합니다.
    그 외에는 reranker_type에 따라 CrossEncoderReranker 또는 LLMReranker를 반환합니다.

    Args:
        reranker_type: Reranker 타입 ("cross-encoder" 또는 "llm")
                       None이면 설정값 사용

    Returns:
        BaseReranker 구현체 인스턴스

    Raises:
        ValueError: 지원하지 않는 reranker_type인 경우
    """
    global _reranker

    settings = get_settings()

    # RunPod 모드: 임베딩과 동일 엔드포인트로 리랭킹
    if settings.embedding_provider == "runpod":
        if _reranker is not None and isinstance(_reranker, RunPodReranker):
            return _reranker
        _reranker = RunPodReranker(
            api_key=settings.runpod_api_key,
            endpoint_id=settings.runpod_endpoint_id,
        )
        logger.info("[Reranker] RunPodReranker 초기화 (endpoint: %s)", settings.runpod_endpoint_id)
        return _reranker

    # 로컬 모드
    requested_type = reranker_type or settings.reranker_type

    # 이미 생성된 인스턴스가 있고 타입이 일치하면 재사용
    if _reranker is not None:
        if requested_type == "cross-encoder" and isinstance(_reranker, CrossEncoderReranker):
            return _reranker
        if requested_type == "llm" and isinstance(_reranker, LLMReranker):
            return _reranker

    # 새 인스턴스 생성
    if requested_type == "cross-encoder":
        _reranker = CrossEncoderReranker()
        logger.info("[Reranker] CrossEncoderReranker 초기화 (모델: %s)", settings.cross_encoder_model)
    elif requested_type == "llm":
        _reranker = LLMReranker()
        logger.info("[Reranker] LLMReranker 초기화")
    else:
        raise ValueError(f"지원하지 않는 reranker_type: {requested_type}")

    return _reranker


def reset_reranker() -> None:
    """Reranker 싱글톤을 리셋합니다 (테스트용)."""
    global _reranker
    if _reranker is not None:
        # CrossEncoderReranker의 경우 모델 참조 해제
        if isinstance(_reranker, CrossEncoderReranker):
            _reranker._model = None
    _reranker = None
    logger.debug("[Reranker] 싱글톤 리셋")
