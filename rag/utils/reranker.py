"""Reranker 紐⑤뱢.

Cross-Encoder 諛?LLM 湲곕컲 Re-ranking 湲곕뒫???쒓났?⑸땲??
"""

import asyncio
import logging
import os
import re
from abc import ABC, abstractmethod

from langchain_core.documents import Document
from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import ChatPromptTemplate

from utils.config import create_llm, get_settings
from utils.prompts import RERANK_PROMPT

logger = logging.getLogger(__name__)


class BaseReranker(ABC):
    """Reranker 異붿긽 湲곕낯 ?대옒??

    紐⑤뱺 Reranker 援ы쁽泥대뒗 ???대옒?ㅻ? ?곸냽?댁빞 ?⑸땲??
    """

    @abstractmethod
    def rerank(
        self,
        query: str,
        documents: list[Document],
        top_k: int = 5,
    ) -> list[Document]:
        """臾몄꽌瑜??ъ젙?ы빀?덈떎.

        Args:
            query: 寃??荑쇰━
            documents: 臾몄꽌 由ъ뒪??
            top_k: 諛섑솚??臾몄꽌 ??

        Returns:
            ?ъ젙?щ맂 臾몄꽌 由ъ뒪??
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
        """臾몄꽌瑜?鍮꾨룞湲곕줈 ?ъ젙?ы빀?덈떎.

        Args:
            query: 寃??荑쇰━
            documents: 臾몄꽌 由ъ뒪??
            top_k: 諛섑솚??臾몄꽌 ??
            max_concurrent: 理쒕? ?숈떆 泥섎━ ??

        Returns:
            ?ъ젙?щ맂 臾몄꽌 由ъ뒪??
        """
        pass


class CrossEncoderReranker(BaseReranker):
    """Cross-Encoder 湲곕컲 Reranker.

    sentence-transformers CrossEncoder瑜??ъ슜??鍮좊Ⅸ ?ъ젙?ъ쓣 ?섑뻾?⑸땲??
    ?쒓뎅??吏??紐⑤뜽(BAAI/bge-reranker-base)??湲곕낯?쇰줈 ?ъ슜?⑸땲??

    Attributes:
        model_name: CrossEncoder 紐⑤뜽紐?
        model: CrossEncoder ?몄뒪?댁뒪
    """

    def __init__(self, model_name: str | None = None):
        """CrossEncoderReranker瑜?珥덇린?뷀빀?덈떎.

        Args:
            model_name: CrossEncoder 紐⑤뜽紐?(None?대㈃ ?ㅼ젙媛??ъ슜)
        """
        self.settings = get_settings()
        self.model_name = model_name or self.settings.cross_encoder_model
        self._model = None  # 吏??濡쒕뵫
        self._model_load_failed = False  # 濡쒕뵫 ?ㅽ뙣 ?곹깭

    @property
    def model(self):
        """CrossEncoder 紐⑤뜽 ?몄뒪?댁뒪 (吏??濡쒕뵫)."""
        if self._model is None:
            if self._model_load_failed:
                return None
            logger.info("[CrossEncoder] 紐⑤뜽 濡쒕뵫: %s", self.model_name)
            try:
                from sentence_transformers import CrossEncoder
                local_files_only = bool(os.getenv("PYTEST_CURRENT_TEST"))
                self._model = CrossEncoder(
                    self.model_name,
                    local_files_only=local_files_only,
                )
                logger.info("[CrossEncoder] 紐⑤뜽 濡쒕뵫 ?꾨즺")
            except Exception as e:
                logger.error("[CrossEncoder] 紐⑤뜽 濡쒕뵫 ?ㅽ뙣: %s ??reranking ?ㅽ궢", e)
                self._model_load_failed = True
                return None
        return self._model

    def _fallback_rerank(self, query: str, documents: list[Document], top_k: int) -> list[Document]:
        query_tokens = set(re.findall(r"\w+", query.lower()))
        if not query_tokens:
            return documents[:top_k]

        scored_docs: list[tuple[Document, int]] = []
        for doc in documents:
            doc_tokens = set(re.findall(r"\w+", doc.page_content.lower()))
            scored_docs.append((doc, len(query_tokens & doc_tokens)))

        scored_docs.sort(key=lambda x: x[1], reverse=True)
        return [doc for doc, _ in scored_docs[:top_k]]

    def rerank(
        self,
        query: str,
        documents: list[Document],
        top_k: int = 5,
    ) -> list[Document]:
        """臾몄꽌瑜??ъ젙?ы빀?덈떎.

        Args:
            query: 寃??荑쇰━
            documents: 臾몄꽌 由ъ뒪??
            top_k: 諛섑솚??臾몄꽌 ??

        Returns:
            ?ъ젙?щ맂 臾몄꽌 由ъ뒪??
        """
        if len(documents) <= top_k:
            return documents

        logger.info("[由щ옲?? CrossEncoder ?쒖옉: %d嫄???top_%d", len(documents), top_k)

        # 紐⑤뜽 濡쒕뵫 ?ㅽ뙣 ???먮낯 諛섑솚
        if self.model is None:
            logger.warning("[rerank] CrossEncoder model unavailable, using fallback ranking")
            return self._fallback_rerank(query, documents, top_k)

        # 荑쇰━-臾몄꽌 ???앹꽦 (Cross-Encoder 512 ?좏겙 ?쒗븳?쇰줈 500?먮줈 ?쒗븳)
        pairs = [(query, doc.page_content[:500]) for doc in documents]

        # CrossEncoder濡??먯닔 怨꾩궛
        try:
            scores = self.model.predict(pairs)

            # ?먯닔? 臾몄꽌瑜??띿쑝濡?臾띠뼱 ?뺣젹 (numpy float瑜?紐낆떆?곸쑝濡?Python float濡?蹂??
            scored_docs = list(zip(documents, [float(s) for s in scores]))
            scored_docs.sort(key=lambda x: x[1], reverse=True)

            scores_list = [s for _, s in scored_docs]
            logger.info(
                "[由щ옲?? CrossEncoder ?꾨즺: ?먯닔 踰붿쐞 %.4f~%.4f",
                min(scores_list), max(scores_list)
            )

            return [doc for doc, _ in scored_docs[:top_k]]

        except Exception as e:
            logger.warning("[rerank] CrossEncoder failure: %s (using fallback ranking)", e)
            return self._fallback_rerank(query, documents, top_k)

    async def arerank(
        self,
        query: str,
        documents: list[Document],
        top_k: int = 5,
        max_concurrent: int = 5,
    ) -> list[Document]:
        """臾몄꽌瑜?鍮꾨룞湲곕줈 ?ъ젙?ы빀?덈떎.

        CrossEncoder??諛곗튂 泥섎━媛 鍮좊Ⅴ誘濡??숆린 ?⑥닔瑜??ㅻ젅?쒕줈 ?ㅽ뻾?⑸땲??

        Args:
            query: 寃??荑쇰━
            documents: 臾몄꽌 由ъ뒪??
            top_k: 諛섑솚??臾몄꽌 ??
            max_concurrent: 理쒕? ?숈떆 泥섎━ ??(CrossEncoder?먯꽌??誘몄궗??

        Returns:
            ?ъ젙?щ맂 臾몄꽌 由ъ뒪??
        """
        return await asyncio.to_thread(self.rerank, query, documents, top_k)


class RunPodReranker(BaseReranker):
    """RunPod Serverless瑜??듯븳 Re-ranking.

    RunPod GPU ?붾뱶?ъ씤?몄뿉 HTTP ?붿껌??蹂대궡 臾몄꽌瑜??ъ젙?ы빀?덈떎.
    ?꾨쿋?⑷낵 ?숈씪???붾뱶?ъ씤?몃? ?ъ슜?⑸땲??(task="rerank").

    Attributes:
        api_url: RunPod runsync API URL
        headers: HTTP ?붿껌 ?ㅻ뜑 (?몄쬆 ?ы븿)
    """

    def __init__(self, api_key: str, endpoint_id: str) -> None:
        """RunPodReranker瑜?珥덇린?뷀빀?덈떎.

        Args:
            api_key: RunPod API ??
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
        """臾몄꽌瑜??숆린濡??ъ젙?ы빀?덈떎.

        Args:
            query: 寃??荑쇰━
            documents: 臾몄꽌 由ъ뒪??
            top_k: 諛섑솚??臾몄꽌 ??

        Returns:
            ?ъ젙?щ맂 臾몄꽌 由ъ뒪??
        """
        if len(documents) <= top_k:
            return documents

        import httpx

        logger.info("[由щ옲?? RunPod ?쒖옉: %d嫄???top_%d", len(documents), top_k)

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
                logger.warning("[由щ옲?? RunPod ?ㅽ뙣: status=%s (?먮낯 ?쒖꽌 ?좎?)", result.get("status"))
                return documents[:top_k]

            scores = [float(s) for s in result["output"]["scores"]]
            scored_docs = sorted(zip(documents, scores), key=lambda x: x[1], reverse=True)

            logger.info(
                "[由щ옲?? RunPod ?꾨즺: ?먯닔 踰붿쐞 %.4f~%.4f",
                min(scores), max(scores),
            )

            return [doc for doc, _ in scored_docs[:top_k]]

        except Exception as e:
            logger.warning("[由щ옲?? RunPod ?ㅽ뙣: %s (?먮낯 ?쒖꽌 ?좎?)", e)
            return documents[:top_k]

    async def arerank(
        self,
        query: str,
        documents: list[Document],
        top_k: int = 5,
        max_concurrent: int = 5,
    ) -> list[Document]:
        """臾몄꽌瑜?鍮꾨룞湲곕줈 ?ъ젙?ы빀?덈떎.

        Args:
            query: 寃??荑쇰━
            documents: 臾몄꽌 由ъ뒪??
            top_k: 諛섑솚??臾몄꽌 ??
            max_concurrent: 理쒕? ?숈떆 泥섎━ ??(RunPod?먯꽌??誘몄궗??

        Returns:
            ?ъ젙?щ맂 臾몄꽌 由ъ뒪??
        """
        if len(documents) <= top_k:
            return documents

        import httpx

        logger.info("[由щ옲?? RunPod 鍮꾨룞湲??쒖옉: %d嫄???top_%d", len(documents), top_k)

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
                logger.warning("[由щ옲?? RunPod ?ㅽ뙣: status=%s (?먮낯 ?쒖꽌 ?좎?)", result.get("status"))
                return documents[:top_k]

            scores = [float(s) for s in result["output"]["scores"]]
            scored_docs = sorted(zip(documents, scores), key=lambda x: x[1], reverse=True)

            logger.info(
                "[由щ옲?? RunPod ?꾨즺: ?먯닔 踰붿쐞 %.4f~%.4f",
                min(scores), max(scores),
            )

            return [doc for doc, _ in scored_docs[:top_k]]

        except Exception as e:
            logger.warning("[由щ옲?? RunPod ?ㅽ뙣: %s (?먮낯 ?쒖꽌 ?좎?)", e)
            return documents[:top_k]


class LLMReranker(BaseReranker):
    """LLM 湲곕컲 Reranker.

    Cross-encoder ?ㅽ??쇱쓽 LLM 湲곕컲 ?ъ젙?ъ쓣 ?섑뻾?⑸땲??
    """

    def __init__(self):
        """LLMReranker瑜?珥덇린?뷀빀?덈떎."""
        self.settings = get_settings()
        self.llm = create_llm("리랭킹", temperature=0.0)
        self._chain = self._build_chain()

    def _build_chain(self):
        """Re-ranking 泥댁씤??鍮뚮뱶?⑸땲??"""
        prompt = ChatPromptTemplate.from_template(RERANK_PROMPT)
        return prompt | self.llm | StrOutputParser()

    def _parse_score(self, response: str) -> float:
        """?묐떟?먯꽌 ?먯닔瑜?異붿텧?⑸땲??"""
        try:
            # ?レ옄留?異붿텧
            numbers = re.findall(r'\d+(?:\.\d+)?', response)
            if numbers:
                score = float(numbers[0])
                return min(10, max(0, score))  # 0-10 踰붿쐞濡??대옩??
        except ValueError:
            pass
        return 5.0  # 湲곕낯媛?

    def rerank(
        self,
        query: str,
        documents: list[Document],
        top_k: int = 5,
    ) -> list[Document]:
        """臾몄꽌瑜??ъ젙?ы빀?덈떎.

        Args:
            query: 寃??荑쇰━
            documents: 臾몄꽌 由ъ뒪??
            top_k: 諛섑솚??臾몄꽌 ??

        Returns:
            ?ъ젙?щ맂 臾몄꽌 由ъ뒪??
        """
        if len(documents) <= top_k:
            return documents

        logger.info("[由щ옲?? LLM ?쒖옉: %d嫄???top_%d", len(documents), top_k)

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
                logger.warning(f"Re-ranking ?ㅽ뙣: {e}")
                scored_docs.append((doc, 5.0))

        # ?먯닔濡??뺣젹
        scored_docs.sort(key=lambda x: x[1], reverse=True)

        scores_list = [s for _, s in scored_docs]
        logger.info("[由щ옲?? LLM ?꾨즺: ?먯닔 踰붿쐞 %.1f~%.1f", min(scores_list), max(scores_list))

        return [doc for doc, _ in scored_docs[:top_k]]

    async def arerank(
        self,
        query: str,
        documents: list[Document],
        top_k: int = 5,
        max_concurrent: int = 5,
    ) -> list[Document]:
        """臾몄꽌瑜?鍮꾨룞湲곕줈 ?ъ젙?ы빀?덈떎.

        Args:
            query: 寃??荑쇰━
            documents: 臾몄꽌 由ъ뒪??
            top_k: 諛섑솚??臾몄꽌 ??
            max_concurrent: 理쒕? ?숈떆 泥섎━ ??

        Returns:
            ?ъ젙?щ맂 臾몄꽌 由ъ뒪??
        """
        if len(documents) <= top_k:
            return documents

        logger.info("[由щ옲?? LLM ?쒖옉: %d嫄???top_%d", len(documents), top_k)

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
                    logger.warning(f"Re-ranking ?ㅽ뙣: {e}")
                    return doc, 5.0

        tasks = [score_one(doc) for doc in documents]
        results = await asyncio.gather(*tasks)

        # ?먯닔濡??뺣젹
        results = sorted(results, key=lambda x: x[1], reverse=True)

        scores_list = [s for _, s in results]
        logger.info("[由щ옲?? LLM ?꾨즺: ?먯닔 踰붿쐞 %.1f~%.1f", min(scores_list), max(scores_list))

        return [doc for doc, _ in results[:top_k]]


# ?깃????몄뒪?댁뒪
_reranker: BaseReranker | None = None


def get_reranker(reranker_type: str | None = None) -> BaseReranker:
    """Reranker ?몄뒪?댁뒪瑜?諛섑솚?⑸땲??(?깃???.

    EMBEDDING_PROVIDER=runpod?대㈃ RunPodReranker瑜?諛섑솚?⑸땲??
    洹??몄뿉??reranker_type???곕씪 CrossEncoderReranker ?먮뒗 LLMReranker瑜?諛섑솚?⑸땲??

    Args:
        reranker_type: Reranker ???("cross-encoder" ?먮뒗 "llm")
                       None?대㈃ ?ㅼ젙媛??ъ슜

    Returns:
        BaseReranker 援ы쁽泥??몄뒪?댁뒪

    Raises:
        ValueError: 吏?먰븯吏 ?딅뒗 reranker_type??寃쎌슦
    """
    global _reranker

    settings = get_settings()

    # RunPod 紐⑤뱶: ?꾨쿋?⑷낵 ?숈씪 ?붾뱶?ъ씤?몃줈 由щ옲??
    if reranker_type is None and settings.embedding_provider == "runpod":
        if _reranker is not None and isinstance(_reranker, RunPodReranker):
            return _reranker
        _reranker = RunPodReranker(
            api_key=settings.runpod_api_key,
            endpoint_id=settings.runpod_endpoint_id,
        )
        logger.info("[Reranker] RunPodReranker 珥덇린??(endpoint: %s)", settings.runpod_endpoint_id)
        return _reranker

    # 濡쒖뺄 紐⑤뱶
    requested_type = reranker_type or settings.reranker_type

    # ?대? ?앹꽦???몄뒪?댁뒪媛 ?덇퀬 ??낆씠 ?쇱튂?섎㈃ ?ъ궗??
    if _reranker is not None:
        if requested_type == "cross-encoder" and isinstance(_reranker, CrossEncoderReranker):
            return _reranker
        if requested_type == "llm" and isinstance(_reranker, LLMReranker):
            return _reranker

    # ???몄뒪?댁뒪 ?앹꽦
    if requested_type == "cross-encoder":
        _reranker = CrossEncoderReranker()
        logger.info("[Reranker] CrossEncoderReranker 珥덇린??(紐⑤뜽: %s)", settings.cross_encoder_model)
    elif requested_type == "llm":
        _reranker = LLMReranker()
        logger.info("[Reranker] LLMReranker initialized")
    else:
        raise ValueError(f"吏?먰븯吏 ?딅뒗 reranker_type: {requested_type}")

    return _reranker


def reset_reranker() -> None:
    """Reranker ?깃??ㅼ쓣 由ъ뀑?⑸땲??(?뚯뒪?몄슜)."""
    global _reranker
    if _reranker is not None:
        # CrossEncoderReranker??寃쎌슦 紐⑤뜽 李몄“ ?댁젣
        if isinstance(_reranker, CrossEncoderReranker):
            _reranker._model = None
    _reranker = None
    logger.debug("[Reranker] ?깃???由ъ뀑")



