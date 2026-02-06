"""벡터 유사도 기반 도메인 분류 모듈.

LLM 호출 없이 임베딩 유사도로 도메인을 분류합니다.
키워드 매칭 1차 시도 후 실패 시 벡터 유사도 기반 분류를 수행합니다.
"""

import logging
from dataclasses import dataclass
from functools import lru_cache

import numpy as np
from langchain_huggingface import HuggingFaceEmbeddings

from utils.config import get_settings
from utils.prompts import DOMAIN_KEYWORDS

logger = logging.getLogger(__name__)


# 도메인별 대표 쿼리 (임베딩 미리 계산)
DOMAIN_REPRESENTATIVE_QUERIES: dict[str, list[str]] = {
    "startup_funding": [
        "사업자등록 절차가 궁금합니다",
        "창업 지원사업 추천해주세요",
        "법인 설립 방법을 알려주세요",
        "정부 보조금 신청 방법",
        "마케팅 전략 조언",
        "스타트업 초기 자금 조달",
        "업종별 인허가 필요한가요",
        "창업 아이템 검증 방법",
        "예비창업자 지원 프로그램",
        "소상공인 지원정책",
    ],
    "finance_tax": [
        "부가세 신고 방법",
        "법인세 계산 방법",
        "세금 절세 방법",
        "회계 처리 방법",
        "재무제표 작성법",
        "원천징수 신고 절차",
        "세무조정 어떻게 하나요",
        "종합소득세 신고 기한",
        "매입세액 공제 조건",
        "결산 절차가 궁금합니다",
    ],
    "hr_labor": [
        "퇴직금 계산 방법",
        "근로계약서 작성법",
        "4대보험 가입 방법",
        "연차 계산 방법",
        "해고 절차",
        "최저임금 적용 기준",
        "야근 수당 계산",
        "취업규칙 작성 방법",
        "근로시간 단축 제도",
        "채용 공고 작성법",
    ],
}


@dataclass
class DomainClassificationResult:
    """도메인 분류 결과.

    Attributes:
        domains: 분류된 도메인 리스트
        confidence: 분류 신뢰도 (0.0-1.0)
        is_relevant: 관련 질문 여부
        method: 분류 방법 ('keyword', 'vector', 'fallback')
        matched_keywords: 키워드 매칭 시 매칭된 키워드들
    """

    domains: list[str]
    confidence: float
    is_relevant: bool
    method: str
    matched_keywords: dict[str, list[str]] | None = None


class VectorDomainClassifier:
    """벡터 유사도 기반 도메인 분류기 (LLM 미사용).

    1차: 키워드 매칭 시도
    2차: 실패 시 도메인 대표 쿼리와 임베딩 유사도 비교

    Attributes:
        embeddings: HuggingFace 임베딩 모델
        settings: RAG 설정
        _domain_vectors: 도메인별 대표 쿼리 임베딩 벡터

    Example:
        >>> from vectorstores.embeddings import get_embeddings
        >>> classifier = VectorDomainClassifier(get_embeddings())
        >>> result = classifier.classify("사업자등록 절차가 궁금합니다")
        >>> print(result.domains)  # ['startup_funding']
    """

    def __init__(self, embeddings: HuggingFaceEmbeddings):
        """VectorDomainClassifier를 초기화합니다.

        Args:
            embeddings: HuggingFace 임베딩 인스턴스
        """
        self.embeddings = embeddings
        self.settings = get_settings()
        self._domain_vectors: dict[str, np.ndarray] | None = None

    def _precompute_vectors(self) -> dict[str, np.ndarray]:
        """도메인별 대표 쿼리 벡터를 미리 계산합니다.

        Returns:
            도메인별 평균 임베딩 벡터
        """
        if self._domain_vectors is not None:
            return self._domain_vectors

        logger.info("[도메인 분류] 대표 쿼리 벡터 계산 중...")
        domain_vectors: dict[str, np.ndarray] = {}

        for domain, queries in DOMAIN_REPRESENTATIVE_QUERIES.items():
            # 각 도메인의 대표 쿼리들 임베딩
            vectors = self.embeddings.embed_documents(queries)
            # 평균 벡터 계산 (centroid)
            domain_vectors[domain] = np.mean(vectors, axis=0)
            logger.debug(
                "[도메인 분류] %s: %d개 쿼리 임베딩 완료",
                domain,
                len(queries),
            )

        self._domain_vectors = domain_vectors
        logger.info("[도메인 분류] 대표 쿼리 벡터 계산 완료")
        return domain_vectors

    def _keyword_classify(self, query: str) -> DomainClassificationResult | None:
        """키워드 기반 도메인 분류.

        Args:
            query: 사용자 질문

        Returns:
            분류 결과 (키워드 매칭 실패 시 None)
        """
        detected_domains: list[str] = []
        matched_keywords: dict[str, list[str]] = {}

        for domain, keywords in DOMAIN_KEYWORDS.items():
            hits = [kw for kw in keywords if kw in query]
            if hits:
                detected_domains.append(domain)
                matched_keywords[domain] = hits

        if detected_domains:
            # 매칭된 키워드 수에 따른 신뢰도 계산
            total_matches = sum(len(kws) for kws in matched_keywords.values())
            confidence = min(1.0, 0.5 + (total_matches * 0.1))

            return DomainClassificationResult(
                domains=detected_domains,
                confidence=confidence,
                is_relevant=True,
                method="keyword",
                matched_keywords=matched_keywords,
            )

        return None

    def _vector_classify(self, query: str) -> DomainClassificationResult:
        """벡터 유사도 기반 도메인 분류.

        Args:
            query: 사용자 질문

        Returns:
            분류 결과
        """
        domain_vectors = self._precompute_vectors()

        # 쿼리 임베딩
        query_vector = np.array(self.embeddings.embed_query(query))

        # 각 도메인과의 코사인 유사도 계산
        similarities: dict[str, float] = {}
        for domain, domain_vec in domain_vectors.items():
            # 코사인 유사도 (이미 정규화된 벡터)
            similarity = float(np.dot(query_vector, domain_vec))
            similarities[domain] = similarity

        # 유사도 내림차순 정렬
        sorted_domains = sorted(
            similarities.items(),
            key=lambda x: x[1],
            reverse=True,
        )

        logger.debug("[도메인 분류] 벡터 유사도: %s", sorted_domains)

        threshold = self.settings.domain_classification_threshold
        best_domain, best_score = sorted_domains[0]

        # 임계값 미만이면 도메인 외 질문으로 판단
        if best_score < threshold:
            return DomainClassificationResult(
                domains=[],
                confidence=best_score,
                is_relevant=False,
                method="vector",
            )

        # 복수 도메인 탐지: 최고 점수와 0.1 이내 차이인 도메인 포함
        detected_domains = [best_domain]
        for domain, score in sorted_domains[1:]:
            if best_score - score < 0.1 and score >= threshold:
                detected_domains.append(domain)

        return DomainClassificationResult(
            domains=detected_domains,
            confidence=best_score,
            is_relevant=True,
            method="vector",
        )

    def classify(self, query: str) -> DomainClassificationResult:
        """질문을 분류하여 관련 도메인과 신뢰도를 반환합니다.

        1. 키워드 매칭 시도
        2. 실패 시: 임베딩 유사도 기반 분류

        Args:
            query: 사용자 질문

        Returns:
            도메인 분류 결과
        """
        # 1차: 키워드 매칭
        keyword_result = self._keyword_classify(query)
        if keyword_result:
            logger.info(
                "[도메인 분류] 키워드 매칭 성공: %s (신뢰도: %.2f)",
                keyword_result.domains,
                keyword_result.confidence,
            )
            return keyword_result

        # 2차: 벡터 유사도 기반 분류
        if self.settings.enable_vector_domain_classification:
            logger.info("[도메인 분류] 키워드 매칭 실패, 벡터 유사도 분류 사용")
            vector_result = self._vector_classify(query)

            if vector_result.is_relevant:
                logger.info(
                    "[도메인 분류] 벡터 유사도 분류: %s (신뢰도: %.2f)",
                    vector_result.domains,
                    vector_result.confidence,
                )
            else:
                logger.info(
                    "[도메인 분류] 도메인 외 질문으로 판단됨 (신뢰도: %.2f)",
                    vector_result.confidence,
                )

            return vector_result

        # fallback: startup_funding 기본값
        logger.warning("[도메인 분류] 분류 실패, 기본값 사용")
        return DomainClassificationResult(
            domains=["startup_funding"],
            confidence=0.3,
            is_relevant=True,
            method="fallback",
        )


@lru_cache(maxsize=1)
def get_domain_classifier() -> VectorDomainClassifier:
    """VectorDomainClassifier 싱글톤 인스턴스를 반환합니다.

    Returns:
        VectorDomainClassifier 인스턴스
    """
    from vectorstores.embeddings import get_embeddings

    return VectorDomainClassifier(get_embeddings())
