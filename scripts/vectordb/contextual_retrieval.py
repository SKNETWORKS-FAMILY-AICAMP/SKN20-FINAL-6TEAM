"""LLM 기반 Contextual Retrieval 모듈.

Anthropic 연구 기반으로 각 청크에 문서 수준의 맥락을 추가합니다.
"""

import asyncio
import logging
import os

from langchain_openai import ChatOpenAI
from tenacity import retry, stop_after_attempt, wait_exponential

logger = logging.getLogger(__name__)

CONTEXTUAL_RETRIEVAL_PROMPT = """<document>
{whole_document}
</document>

다음 청크는 위 문서에서 발췌한 것입니다.

<chunk>
{chunk_content}
</chunk>

위 문서 전체 맥락에서 이 청크를 간결하게 설명하는 한 단락을 작성하세요. \
검색 시 이 청크를 올바르게 찾을 수 있도록 돕는 맥락만 포함하세요. \
부연 설명 없이 맥락 설명만 출력하세요."""


class ContextualRetriever:
    """LLM 기반으로 청크에 문서 수준 맥락을 추가하는 클래스."""

    def __init__(
        self,
        model: str = "gpt-4o-mini",
        max_concurrent: int = 5,
        max_doc_chars: int = 8000,
    ):
        """초기화.

        Args:
            model: OpenAI 모델 이름
            max_concurrent: 최대 동시 LLM 호출 수
            max_doc_chars: 문서 전문 최대 문자 수 (LLM 컨텍스트 제한)
        """
        self.model = model
        self.max_concurrent = max_concurrent
        self.max_doc_chars = max_doc_chars
        self._llm: ChatOpenAI | None = None
        self._semaphore: asyncio.Semaphore | None = None

    def _get_llm(self) -> ChatOpenAI:
        if self._llm is None:
            self._llm = ChatOpenAI(
                model=self.model,
                temperature=0,
                openai_api_key=os.getenv("OPENAI_API_KEY"),
            )
        return self._llm

    def _get_semaphore(self) -> asyncio.Semaphore:
        if self._semaphore is None:
            self._semaphore = asyncio.Semaphore(self.max_concurrent)
        return self._semaphore

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(min=1, max=10), reraise=True)
    async def _call_llm_with_retry(self, prompt: str) -> str:
        """LLM을 호출하여 맥락 텍스트를 생성합니다."""
        llm = self._get_llm()
        response = await llm.ainvoke(prompt)
        return response.content.strip()

    async def generate_context(self, full_document: str, chunk_text: str) -> str:
        """청크에 대한 문서 수준 맥락을 생성합니다.

        Args:
            full_document: 전체 문서 텍스트
            chunk_text: 맥락을 생성할 청크 텍스트

        Returns:
            생성된 맥락 텍스트 (실패 시 빈 문자열)
        """
        truncated_doc = full_document[: self.max_doc_chars]
        prompt = CONTEXTUAL_RETRIEVAL_PROMPT.format(
            whole_document=truncated_doc,
            chunk_content=chunk_text,
        )
        semaphore = self._get_semaphore()
        async with semaphore:
            try:
                return await self._call_llm_with_retry(prompt)
            except Exception as e:
                logger.warning("맥락 생성 실패 (chunk[:50]=%r): %s", chunk_text[:50], e)
                return ""

    async def generate_contexts_batch(
        self, full_document: str, chunks: list[str]
    ) -> list[str]:
        """여러 청크에 대한 맥락을 동시에 생성합니다.

        Args:
            full_document: 전체 문서 텍스트
            chunks: 맥락을 생성할 청크 텍스트 리스트

        Returns:
            각 청크에 대한 맥락 텍스트 리스트
        """
        tasks = [self.generate_context(full_document, chunk) for chunk in chunks]
        return list(await asyncio.gather(*tasks))
