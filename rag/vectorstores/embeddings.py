"""?꾨쿋???ㅼ젙 紐⑤뱢.

??紐⑤뱢? VectorDB?먯꽌 ?ъ슜???꾨쿋?⑹쓣 ?ㅼ젙?⑸땲??
EMBEDDING_PROVIDER ?섍꼍蹂?섏뿉 ?곕씪 濡쒖뺄(HuggingFace) ?먮뒗 RunPod GPU瑜??ъ슜?⑸땲??

Example:
    >>> from vectorstores.embeddings import get_embeddings
    >>> embeddings = get_embeddings()
    >>> vector = embeddings.embed_query("李쎌뾽 吏?먭툑")
"""

import logging
from functools import lru_cache

from langchain_core.embeddings import Embeddings

from .config import VectorDBConfig

logger = logging.getLogger(__name__)


class RunPodEmbeddings(Embeddings):
    """RunPod Serverless瑜??듯븳 ?꾨쿋??

    RunPod GPU ?붾뱶?ъ씤?몄뿉 HTTP ?붿껌??蹂대궡 ?꾨쿋??踰≫꽣瑜??앹꽦?⑸땲??
    LangChain Embeddings ?명꽣?섏씠?ㅻ? 援ы쁽?섏뿬 湲곗〈 肄붾뱶? ?명솚?⑸땲??

    Attributes:
        api_url: RunPod runsync API URL
        headers: HTTP ?붿껌 ?ㅻ뜑 (?몄쬆 ?ы븿)
    """

    def __init__(self, api_key: str, endpoint_id: str) -> None:
        """RunPodEmbeddings瑜?珥덇린?뷀빀?덈떎.

        Args:
            api_key: RunPod API ??
            endpoint_id: RunPod Serverless Endpoint ID
        """
        self.base_url = f"https://api.runpod.ai/v2/{endpoint_id}"
        self.run_url = f"{self.base_url}/run"
        self.headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        }

    def _call_runpod(self, texts: list[str]) -> list[list[float]]:
        """RunPod API瑜??숆린 ?몄텧?섏뿬 ?꾨쿋??踰≫꽣瑜?諛섑솚?⑸땲??

        Args:
            texts: ?꾨쿋?⑺븷 ?띿뒪??由ъ뒪??

        Returns:
            ?꾨쿋??踰≫꽣 由ъ뒪??

        Raises:
            RuntimeError: RunPod API ?몄텧 ?ㅽ뙣 ??
        """
        import httpx
        import time

        payload = {"input": {"task": "embed", "texts": texts}}
        max_poll = 120
        poll_interval_sec = 1.5

        with httpx.Client(timeout=120.0) as client:
            submit = client.post(self.run_url, json=payload, headers=self.headers)
            submit.raise_for_status()
            run = submit.json()
            job_id = run.get("id")
            if not job_id:
                raise RuntimeError("RunPod 임베딩 실패: missing job id")

            status_url = f"{self.base_url}/status/{job_id}"
            for attempt in range(1, max_poll + 1):
                status_resp = client.get(status_url, headers=self.headers)
                status_resp.raise_for_status()
                result = status_resp.json()
                status = result.get("status")

                if status == "COMPLETED":
                    return result["output"]["vectors"]
                if status in {"IN_QUEUE", "IN_PROGRESS"}:
                    if attempt % 10 == 0:
                        logger.warning(
                            "[RunPod] polling job=%s status=%s (%d/%d)",
                            job_id,
                            status,
                            attempt,
                            max_poll,
                        )
                    time.sleep(poll_interval_sec)
                    continue
                raise RuntimeError(f"RunPod 임베딩 실패: status={status}")

        raise RuntimeError("RunPod 임베딩 실패: polling timeout")
    async def _acall_runpod(self, texts: list[str]) -> list[list[float]]:
        """RunPod API瑜?鍮꾨룞湲??몄텧?섏뿬 ?꾨쿋??踰≫꽣瑜?諛섑솚?⑸땲??

        Args:
            texts: ?꾨쿋?⑺븷 ?띿뒪??由ъ뒪??

        Returns:
            ?꾨쿋??踰≫꽣 由ъ뒪??

        Raises:
            RuntimeError: RunPod API ?몄텧 ?ㅽ뙣 ??
        """
        import asyncio
        import httpx

        payload = {"input": {"task": "embed", "texts": texts}}
        max_poll = 120
        poll_interval_sec = 1.5

        async with httpx.AsyncClient(timeout=120.0) as client:
            submit = await client.post(self.run_url, json=payload, headers=self.headers)
            submit.raise_for_status()
            run = submit.json()
            job_id = run.get("id")
            if not job_id:
                raise RuntimeError("RunPod 임베딩 실패: missing job id")

            status_url = f"{self.base_url}/status/{job_id}"
            for attempt in range(1, max_poll + 1):
                status_resp = await client.get(status_url, headers=self.headers)
                status_resp.raise_for_status()
                result = status_resp.json()
                status = result.get("status")

                if status == "COMPLETED":
                    return result["output"]["vectors"]
                if status in {"IN_QUEUE", "IN_PROGRESS"}:
                    if attempt % 10 == 0:
                        logger.warning(
                            "[RunPod] async polling job=%s status=%s (%d/%d)",
                            job_id,
                            status,
                            attempt,
                            max_poll,
                        )
                    await asyncio.sleep(poll_interval_sec)
                    continue
                raise RuntimeError(f"RunPod 임베딩 실패: status={status}")

        raise RuntimeError("RunPod 임베딩 실패: polling timeout")

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        """臾몄꽌 由ъ뒪?몃? ?숆린 ?꾨쿋?⑺빀?덈떎.

        Args:
            texts: ?꾨쿋?⑺븷 ?띿뒪??由ъ뒪??

        Returns:
            ?꾨쿋??踰≫꽣 由ъ뒪??
        """
        if not texts:
            return []
        logger.debug("[RunPod] embed_documents: %d嫄??붿껌", len(texts))
        return self._call_runpod(texts)

    def embed_query(self, text: str) -> list[float]:
        """?⑥씪 荑쇰━瑜??숆린 ?꾨쿋?⑺빀?덈떎.

        Args:
            text: ?꾨쿋?⑺븷 ?띿뒪??

        Returns:
            ?꾨쿋??踰≫꽣
        """
        return self.embed_documents([text])[0]

    async def aembed_documents(self, texts: list[str]) -> list[list[float]]:
        """臾몄꽌 由ъ뒪?몃? 鍮꾨룞湲??꾨쿋?⑺빀?덈떎.

        Args:
            texts: ?꾨쿋?⑺븷 ?띿뒪??由ъ뒪??

        Returns:
            ?꾨쿋??踰≫꽣 由ъ뒪??
        """
        if not texts:
            return []
        logger.debug("[RunPod] aembed_documents: %d嫄??붿껌", len(texts))
        return await self._acall_runpod(texts)

    async def aembed_query(self, text: str) -> list[float]:
        """?⑥씪 荑쇰━瑜?鍮꾨룞湲??꾨쿋?⑺빀?덈떎.

        Args:
            text: ?꾨쿋?⑺븷 ?띿뒪??

        Returns:
            ?꾨쿋??踰≫꽣
        """
        return (await self.aembed_documents([text]))[0]


def _get_local_device() -> str:
    """CUDA > MPS > CPU ?곗꽑?쒖쐞濡??붾컮?댁뒪 諛섑솚."""
    import torch

    if torch.cuda.is_available():
        return "cuda"
    if hasattr(torch.backends, "mps") and torch.backends.mps.is_available():
        return "mps"
    return "cpu"


@lru_cache(maxsize=1)
def get_embeddings(model: str | None = None) -> Embeddings:
    """?꾨쿋???몄뒪?댁뒪瑜?媛?몄샃?덈떎 (?깃???.

    EMBEDDING_PROVIDER ?ㅼ젙???곕씪 濡쒖뺄(HuggingFace) ?먮뒗 RunPod???ъ슜?⑸땲??

    Args:
        model: ?꾨쿋??紐⑤뜽 ?대쫫. None?대㈃ ?ㅼ젙媛??ъ슜 (湲곕낯: BAAI/bge-m3)

    Returns:
        Embeddings ?몄뒪?댁뒪 (HuggingFaceEmbeddings ?먮뒗 RunPodEmbeddings)
    """
    from utils.config import get_settings

    settings = get_settings()

    if settings.embedding_provider == "runpod":
        logger.info(
            "[?꾨쿋?? RunPod 紐⑤뱶 (endpoint: %s)",
            settings.runpod_endpoint_id,
        )
        return RunPodEmbeddings(
            api_key=settings.runpod_api_key,
            endpoint_id=settings.runpod_endpoint_id,
        )

    # 濡쒖뺄 紐⑤뱶 (湲곗〈 ?숈옉)
    from langchain_huggingface import HuggingFaceEmbeddings

    config = VectorDBConfig()
    model_name = model or config.embedding_model
    device = _get_local_device()

    logger.info("[?꾨쿋?? 濡쒖뺄 紐⑤뱶: %s (?붾컮?댁뒪: %s)", model_name, device)

    return HuggingFaceEmbeddings(
        model_name=model_name,
        model_kwargs={"device": device},
        encode_kwargs={"normalize_embeddings": True},
    )
