"""쿼리 처리 유틸리티 모듈.

쿼리 재작성, 확장, 컨텍스트 압축 등의 기능을 제공합니다.
"""

import asyncio
import hashlib
import logging
import re
from collections import OrderedDict
from typing import Any

from langchain_core.documents import Document
from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import ChatPromptTemplate

from utils.config import create_llm, get_settings

logger = logging.getLogger(__name__)

# 쿼리 재작성 프롬프트
QUERY_REWRITE_PROMPT = """당신은 검색 쿼리 최적화 전문가입니다.
사용자의 질문을 벡터 검색에 최적화된 쿼리로 변환하세요.

## 규칙
1. 핵심 키워드를 추출하고 관련 동의어/유사어를 추가
2. 불필요한 조사, 어미 제거
3. 전문 용어가 있다면 일반 용어도 함께 포함
4. 검색에 도움이 되는 구체적인 키워드 추가
5. 원래 의미를 유지하면서 검색 친화적으로 변환

## 예시
- 입력: "창업할 때 세금 어떻게 해요?"
- 출력: "창업 초기 세금 신고 부가가치세 법인세 개인사업자 세무"

- 입력: "직원 자르려면 어떻게 해야 하나요?"
- 출력: "직원 해고 절차 근로기준법 해고예고 정당한 해고 사유"

- 입력: "정부 지원금 받을 수 있나요?"
- 출력: "정부 지원금 보조금 지원사업 중소기업 스타트업 창업지원"

## 입력
{query}

## 출력
검색에 최적화된 쿼리만 출력하세요 (설명 없이):"""

# 컨텍스트 압축 프롬프트
CONTEXT_COMPRESSION_PROMPT = """주어진 문서에서 질문과 관련된 핵심 내용만 추출하세요.

## 질문
{query}

## 문서
{document}

## 규칙
1. 질문에 답하는 데 필요한 문장만 추출
2. 원문을 그대로 인용 (수정하지 않음)
3. 관련 없는 내용은 제외
4. 여러 문장이면 줄바꿈으로 구분
5. 관련 내용이 없으면 "관련 내용 없음" 출력

## 추출된 내용:"""


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
