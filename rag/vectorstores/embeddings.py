"""임베딩 설정 모듈.

이 모듈은 VectorDB에서 사용할 임베딩을 설정합니다.
EMBEDDING_PROVIDER 환경변수에 따라 로컬(HuggingFace) 또는 RunPod GPU를 사용합니다.

Example:
    >>> from vectorstores.embeddings import get_embeddings
    >>> embeddings = get_embeddings()
    >>> vector = embeddings.embed_query("창업 지원금")
"""

import logging
from functools import lru_cache

from langchain_core.embeddings import Embeddings

from .config import VectorDBConfig

logger = logging.getLogger(__name__)


class RunPodEmbeddings(Embeddings):
    """RunPod Serverless를 통한 임베딩.

    RunPod GPU 엔드포인트에 HTTP 요청을 보내 임베딩 벡터를 생성합니다.
    LangChain Embeddings 인터페이스를 구현하여 기존 코드와 호환됩니다.

    Attributes:
        api_url: RunPod runsync API URL
        headers: HTTP 요청 헤더 (인증 포함)
    """

    def __init__(self, api_key: str, endpoint_id: str) -> None:
        """RunPodEmbeddings를 초기화합니다.

        Args:
            api_key: RunPod API 키
            endpoint_id: RunPod Serverless Endpoint ID
        """
        self.api_url = f"https://api.runpod.ai/v2/{endpoint_id}/runsync"
        self.headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        }

    def _call_runpod(self, texts: list[str]) -> list[list[float]]:
        """RunPod API를 동기 호출하여 임베딩 벡터를 반환합니다.

        Args:
            texts: 임베딩할 텍스트 리스트

        Returns:
            임베딩 벡터 리스트

        Raises:
            RuntimeError: RunPod API 호출 실패 시
        """
        import httpx

        payload = {"input": {"task": "embed", "texts": texts}}

        with httpx.Client(timeout=120.0) as client:
            response = client.post(self.api_url, json=payload, headers=self.headers)
            response.raise_for_status()
            result = response.json()

        if result.get("status") != "COMPLETED":
            raise RuntimeError(f"RunPod 임베딩 실패: status={result.get('status')}")

        return result["output"]["vectors"]

    async def _acall_runpod(self, texts: list[str]) -> list[list[float]]:
        """RunPod API를 비동기 호출하여 임베딩 벡터를 반환합니다.

        Args:
            texts: 임베딩할 텍스트 리스트

        Returns:
            임베딩 벡터 리스트

        Raises:
            RuntimeError: RunPod API 호출 실패 시
        """
        import httpx

        payload = {"input": {"task": "embed", "texts": texts}}

        async with httpx.AsyncClient(timeout=120.0) as client:
            response = await client.post(self.api_url, json=payload, headers=self.headers)
            response.raise_for_status()
            result = response.json()

        if result.get("status") != "COMPLETED":
            raise RuntimeError(f"RunPod 임베딩 실패: status={result.get('status')}")

        return result["output"]["vectors"]

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        """문서 리스트를 동기 임베딩합니다.

        Args:
            texts: 임베딩할 텍스트 리스트

        Returns:
            임베딩 벡터 리스트
        """
        if not texts:
            return []
        logger.debug("[RunPod] embed_documents: %d건 요청", len(texts))
        return self._call_runpod(texts)

    def embed_query(self, text: str) -> list[float]:
        """단일 쿼리를 동기 임베딩합니다.

        Args:
            text: 임베딩할 텍스트

        Returns:
            임베딩 벡터
        """
        return self.embed_documents([text])[0]

    async def aembed_documents(self, texts: list[str]) -> list[list[float]]:
        """문서 리스트를 비동기 임베딩합니다.

        Args:
            texts: 임베딩할 텍스트 리스트

        Returns:
            임베딩 벡터 리스트
        """
        if not texts:
            return []
        logger.debug("[RunPod] aembed_documents: %d건 요청", len(texts))
        return await self._acall_runpod(texts)

    async def aembed_query(self, text: str) -> list[float]:
        """단일 쿼리를 비동기 임베딩합니다.

        Args:
            text: 임베딩할 텍스트

        Returns:
            임베딩 벡터
        """
        return (await self.aembed_documents([text]))[0]


def _get_local_device() -> str:
    """CUDA > MPS > CPU 우선순위로 디바이스 반환."""
    import torch

    if torch.cuda.is_available():
        return "cuda"
    if hasattr(torch.backends, "mps") and torch.backends.mps.is_available():
        return "mps"
    return "cpu"


@lru_cache(maxsize=1)
def get_embeddings(model: str | None = None) -> Embeddings:
    """임베딩 인스턴스를 가져옵니다 (싱글톤).

    EMBEDDING_PROVIDER 설정에 따라 로컬(HuggingFace) 또는 RunPod을 사용합니다.

    Args:
        model: 임베딩 모델 이름. None이면 설정값 사용 (기본: BAAI/bge-m3)

    Returns:
        Embeddings 인스턴스 (HuggingFaceEmbeddings 또는 RunPodEmbeddings)
    """
    from utils.config import get_settings

    settings = get_settings()

    if settings.embedding_provider == "runpod":
        logger.info(
            "[임베딩] RunPod 모드 (endpoint: %s)",
            settings.runpod_endpoint_id,
        )
        return RunPodEmbeddings(
            api_key=settings.runpod_api_key,
            endpoint_id=settings.runpod_endpoint_id,
        )

    # 로컬 모드 (기존 동작)
    from langchain_huggingface import HuggingFaceEmbeddings

    config = VectorDBConfig()
    model_name = model or config.embedding_model
    device = _get_local_device()

    logger.info("[임베딩] 로컬 모드: %s (디바이스: %s)", model_name, device)

    return HuggingFaceEmbeddings(
        model_name=model_name,
        model_kwargs={"device": device},
        encode_kwargs={"normalize_embeddings": True},
    )
