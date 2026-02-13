"""도메인 분류 모듈.

두 가지 분류 모드를 지원합니다:
1. 기본 모드 (ENABLE_LLM_DOMAIN_CLASSIFICATION=false):
   키워드 매칭 + 벡터 유사도 기반 분류. 벡터가 최종 결정권을 가집니다.
2. LLM 모드 (ENABLE_LLM_DOMAIN_CLASSIFICATION=true):
   순수 LLM 분류만 사용. 키워드/벡터 계산 없이 LLM이 직접 도메인을 판별합니다.
   LLM 호출 실패 시에만 키워드+벡터 방식으로 자동 fallback합니다.

키워드 매칭은 kiwipiepy 형태소 분석기를 사용하여 원형(lemma) 기반으로 수행합니다.

DB 관리 기능(DomainConfig, init_db, load_domain_config 등)은 utils.config에 위치하며,
후방 호환을 위해 이 모듈에서 re-export합니다.
"""

import json
import logging
import threading
import time as _time
from dataclasses import dataclass

import numpy as np
from kiwipiepy import Kiwi
from langchain_huggingface import HuggingFaceEmbeddings

from utils.config import (
    DOMAIN_REPRESENTATIVE_QUERIES,
    DomainConfig,
    _get_connection,
    _get_default_config,
    create_llm,
    get_domain_config,
    get_settings,
    init_db,
    load_domain_config,
    reload_domain_config,
    reset_domain_config,
)
from utils.prompts import LLM_DOMAIN_CLASSIFICATION_PROMPT

logger = logging.getLogger(__name__)

# Re-exports (backward compatibility):
# DOMAIN_REPRESENTATIVE_QUERIES, DomainConfig, _get_connection,
# _get_default_config, init_db, load_domain_config, get_domain_config,
# reload_domain_config, reset_domain_config


# ===================================================================
# 도메인 분류 결과 및 형태소 분석
# ===================================================================

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


_kiwi: Kiwi | None = None


def _get_kiwi() -> Kiwi:
    """Kiwi 형태소 분석기 싱글톤."""
    global _kiwi
    if _kiwi is None:
        _kiwi = Kiwi()
    return _kiwi


def extract_lemmas(query: str) -> set[str]:
    """쿼리에서 명사와 동사/형용사 원형을 추출합니다.

    Args:
        query: 사용자 질문

    Returns:
        추출된 lemma 집합 (명사 원형 + 동사/형용사 '~다' 형태)
    """
    kiwi = _get_kiwi()
    tokens = kiwi.tokenize(query)
    lemmas: set[str] = set()

    for token in tokens:
        if token.tag.startswith("NN") or token.tag == "SL":
            # 명사, 외래어 → 그대로
            lemmas.add(token.form)
        elif token.tag.startswith("VV") or token.tag.startswith("VA"):
            # 동사/형용사 → 원형 + "다"
            lemmas.add(token.form + "다")

    return lemmas


# ===================================================================
# VectorDomainClassifier
# ===================================================================

class VectorDomainClassifier:
    """도메인 분류기.

    ENABLE_LLM_DOMAIN_CLASSIFICATION 설정에 따라 두 가지 모드로 동작:
    - false (기본): 키워드 매칭 + 벡터 유사도 분류. 벡터가 최종 결정권.
    - true: 순수 LLM 분류만 사용. LLM 실패 시에만 키워드+벡터로 fallback.

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

    # 클래스 레벨 벡터 캐시 (모든 인스턴스에서 공유)
    _DOMAIN_VECTORS_CACHE: dict[str, np.ndarray] | None = None
    _VECTORS_LOCK = threading.Lock()

    def __init__(self, embeddings: HuggingFaceEmbeddings):
        """VectorDomainClassifier를 초기화합니다.

        Args:
            embeddings: HuggingFace 임베딩 인스턴스
        """
        self.embeddings = embeddings
        self.settings = get_settings()
        self._domain_vectors: dict[str, np.ndarray] | None = None
        # LLM 분류용 인스턴스 캐시 (호출마다 재생성 방지)
        self._llm_instance = None

    def _precompute_vectors(self) -> dict[str, np.ndarray]:
        """도메인별 대표 쿼리 벡터를 미리 계산합니다.

        클래스 레벨 캐시를 사용하여 인스턴스 간 중복 계산을 방지합니다.
        threading.Lock으로 동시 호출 시 중복 계산을 방지합니다.

        Returns:
            도메인별 평균 임베딩 벡터
        """
        # 1. 클래스 레벨 캐시 확인 (lock 없이 빠른 경로)
        if VectorDomainClassifier._DOMAIN_VECTORS_CACHE is not None:
            return VectorDomainClassifier._DOMAIN_VECTORS_CACHE

        # 2. 인스턴스 레벨 캐시 확인
        if self._domain_vectors is not None:
            return self._domain_vectors

        with VectorDomainClassifier._VECTORS_LOCK:
            # Double-check: lock 획득 사이에 다른 스레드가 이미 계산했을 수 있음
            if VectorDomainClassifier._DOMAIN_VECTORS_CACHE is not None:
                return VectorDomainClassifier._DOMAIN_VECTORS_CACHE

            logger.info("[도메인 분류] 대표 쿼리 벡터 계산 중... (첫 요청 시 지연 발생 가능)")
            precompute_start = _time.time()
            domain_vectors: dict[str, np.ndarray] = {}

            config = get_domain_config()
            for domain, queries in config.representative_queries.items():
                # 각 도메인의 대표 쿼리들 임베딩
                vectors = self.embeddings.embed_documents(queries)
                # 평균 벡터 계산 (centroid)
                domain_vectors[domain] = np.mean(vectors, axis=0)
                logger.debug(
                    "[도메인 분류] %s: %d개 쿼리 임베딩 완료",
                    domain,
                    len(queries),
                )

            # 클래스 레벨 캐시에 저장
            VectorDomainClassifier._DOMAIN_VECTORS_CACHE = domain_vectors
            self._domain_vectors = domain_vectors
            elapsed = _time.time() - precompute_start
            logger.info("[도메인 분류] 대표 쿼리 벡터 계산 완료 (%.2f초)", elapsed)
            return domain_vectors

    def _keyword_classify(self, query: str) -> DomainClassificationResult | None:
        """형태소 분석 + 키워드 기반 도메인 분류.

        kiwipiepy로 쿼리를 형태소 분석하여 원형(lemma)을 추출한 뒤,
        DOMAIN_KEYWORDS의 원형 키워드와 매칭합니다.

        Args:
            query: 사용자 질문

        Returns:
            분류 결과 (키워드 매칭 실패 시 None)
        """
        lemmas = extract_lemmas(query)
        detected_domains: list[str] = []
        matched_keywords: dict[str, list[str]] = {}

        config = get_domain_config()

        for domain, keywords in config.keywords.items():
            # lemma 집합과 키워드 집합의 교집합
            keyword_set = set(keywords)
            hits = list(lemmas & keyword_set)
            # 원문 부분 문자열 매칭도 보조 (복합명사 대응: "사업자등록" in query)
            for kw in keywords:
                if len(kw) >= 2 and kw in query and kw not in hits:
                    hits.append(kw)
            if hits:
                detected_domains.append(domain)
                matched_keywords[domain] = hits

        # 복합 키워드 규칙 체크 (단일 키워드로 못 잡는 패턴)
        if not detected_domains:
            for domain, required_lemmas in config.compound_rules:
                if required_lemmas.issubset(lemmas):
                    if domain not in detected_domains:
                        detected_domains.append(domain)
                    matched_keywords.setdefault(domain, []).append(
                        "+".join(sorted(required_lemmas))
                    )
                    break  # 첫 매칭 규칙만 적용

        if detected_domains:
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

        # 복수 도메인 탐지: 최고 점수와 gap 이내 차이인 도메인 포함
        gap = self.settings.multi_domain_gap_threshold
        detected_domains = [best_domain]
        for domain, score in sorted_domains[1:]:
            if best_score - score < gap and score >= threshold:
                detected_domains.append(domain)

        return DomainClassificationResult(
            domains=detected_domains,
            confidence=best_score,
            is_relevant=True,
            method="vector",
        )

    def _llm_classify(self, query: str) -> DomainClassificationResult:
        """LLM 기반 도메인 분류.

        ENABLE_LLM_DOMAIN_CLASSIFICATION=true 시 1차 분류기로 사용됩니다.
        실패 시 method="llm_error"를 반환하여 caller가 fallback할 수 있습니다.

        Args:
            query: 사용자 질문

        Returns:
            분류 결과 (실패 시 method="llm_error")
        """
        try:
            from langchain_core.output_parsers import StrOutputParser
            from langchain_core.prompts import ChatPromptTemplate

            if self._llm_instance is None:
                self._llm_instance = create_llm("도메인분류", temperature=0.0)
            llm = self._llm_instance
            prompt = ChatPromptTemplate.from_messages([
                ("human", LLM_DOMAIN_CLASSIFICATION_PROMPT),
            ])
            chain = prompt | llm | StrOutputParser()

            response = chain.invoke({"query": query})

            # JSON 파싱
            # 코드 블록 제거
            cleaned = response.strip()
            if cleaned.startswith("```"):
                lines = cleaned.split("\n")
                # 첫 줄 (```json) 과 마지막 줄 (```) 제거
                lines = [l for l in lines if not l.strip().startswith("```")]
                cleaned = "\n".join(lines)

            result = json.loads(cleaned)

            return DomainClassificationResult(
                domains=result.get("domains", []),
                confidence=float(result.get("confidence", 0.5)),
                is_relevant=result.get("is_relevant", True),
                method="llm",
            )

        except Exception as e:
            logger.warning("[도메인 분류] LLM 분류 실패: %s", e)
            return DomainClassificationResult(
                domains=[],
                confidence=0.0,
                is_relevant=False,
                method="llm_error",
            )

    def _log_classification_comparison(
        self,
        primary_result: DomainClassificationResult,
        llm_result: DomainClassificationResult,
    ) -> None:
        """벡터 vs LLM 분류 비교 로깅.

        Args:
            primary_result: 1차 분류 결과 (키워드 또는 벡터)
            llm_result: LLM 분류 결과
        """
        primary_domains = set(primary_result.domains)
        llm_domains = set(llm_result.domains)
        match = primary_domains == llm_domains

        logger.info(
            "[도메인 비교] %s=%s (%.2f) | LLM=%s (%.2f) | 일치=%s",
            primary_result.method.upper(),
            list(primary_result.domains),
            primary_result.confidence,
            list(llm_result.domains),
            llm_result.confidence,
            "YES" if match else "NO",
        )

        if not match:
            logger.debug(
                "[도메인 비교] 불일치 상세 - 1차만: %s, LLM만: %s",
                list(primary_domains - llm_domains),
                list(llm_domains - primary_domains),
            )

    def classify(self, query: str) -> DomainClassificationResult:
        """질문을 분류하여 관련 도메인과 신뢰도를 반환합니다.

        ENABLE_LLM_DOMAIN_CLASSIFICATION=true 시 순수 LLM 분류만 사용합니다.
        LLM 실패 시 기존 키워드+벡터 방식으로 자동 fallback합니다.

        Args:
            query: 사용자 질문

        Returns:
            도메인 분류 결과
        """
        # 0. LLM 분류 모드: 순수 LLM만 사용, 실패 시에만 keyword+vector fallback
        if self.settings.enable_llm_domain_classification:
            llm_result = self._llm_classify(query)
            if llm_result.method != "llm_error":
                logger.info(
                    "[도메인 분류] LLM 분류 확정: %s (신뢰도: %.2f)",
                    llm_result.domains,
                    llm_result.confidence,
                )
                return llm_result
            logger.warning("[도메인 분류] LLM 분류 실패, keyword+vector fallback")

        # 1. 키워드 매칭 (0ms, 즉시)
        keyword_result = self._keyword_classify(query)

        # 2. 벡터 유사도 분류 (항상 실행)
        if self.settings.enable_vector_domain_classification:
            vector_result = self._vector_classify(query)
        else:
            vector_result = None

        # 3. 결과 조합: 벡터 + 키워드 보정 후 최종 판정
        if vector_result:
            threshold = self.settings.domain_classification_threshold

            # 키워드 매칭 시 벡터 유사도에 보정 적용 (threshold 판정 전)
            if keyword_result:
                boosted_confidence = min(1.0, vector_result.confidence + 0.1)

                # 벡터가 이미 통과했거나, 키워드 보정(+0.1) 후 threshold 이상이면
                # keyword+vector 확정으로 재판정
                if vector_result.is_relevant or boosted_confidence >= threshold:
                    # 보정된 신뢰도로 재판정
                    if boosted_confidence >= threshold:
                        # 키워드+벡터 도메인 합집합 (벡터 도메인 우선, 키워드 추가분 병합)
                        if vector_result.is_relevant:
                            merged_domains = list(dict.fromkeys(
                                vector_result.domains +
                                [d for d in keyword_result.domains if d not in vector_result.domains]
                            ))
                        else:
                            merged_domains = keyword_result.domains
                        vector_result.domains = merged_domains
                        vector_result.confidence = boosted_confidence
                        vector_result.is_relevant = True
                        vector_result.method = "keyword+vector"
                        vector_result.matched_keywords = keyword_result.matched_keywords
                        logger.info(
                            "[도메인 분류] 키워드+벡터 확정: %s (신뢰도: %.2f, 키워드: %s)",
                            vector_result.domains,
                            vector_result.confidence,
                            keyword_result.matched_keywords,
                        )
                        return vector_result

            if vector_result.is_relevant:
                logger.info(
                    "[도메인 분류] 벡터 유사도 확정: %s (신뢰도: %.2f)",
                    vector_result.domains,
                    vector_result.confidence,
                )
                return vector_result

            # 벡터 미통과 + 키워드 보정 없음 → 거부
            if keyword_result:
                logger.info(
                    "[도메인 분류] 키워드 '%s' 매칭됐으나 벡터 유사도 %.2f로 거부",
                    keyword_result.matched_keywords,
                    vector_result.confidence,
                )
            return vector_result

        # 벡터 분류 비활성화 시 키워드 결과 또는 fallback
        if keyword_result:
            logger.info(
                "[도메인 분류] 벡터 비활성화, 키워드 매칭: %s (신뢰도: %.2f)",
                keyword_result.domains,
                keyword_result.confidence,
            )
            return keyword_result

        # fallback: 분류 불가 → 도메인 외 질문으로 처리
        logger.warning("[도메인 분류] 분류 실패, 도메인 외 질문으로 거부")
        return DomainClassificationResult(
            domains=[],
            confidence=0.0,
            is_relevant=False,
            method="fallback_rejected",
        )


_domain_classifier: VectorDomainClassifier | None = None


def get_domain_classifier() -> VectorDomainClassifier:
    """VectorDomainClassifier 싱글톤 인스턴스를 반환합니다.

    Returns:
        VectorDomainClassifier 인스턴스
    """
    global _domain_classifier
    if _domain_classifier is None:
        from vectorstores.embeddings import get_embeddings

        _domain_classifier = VectorDomainClassifier(get_embeddings())
    return _domain_classifier


def reset_domain_classifier() -> None:
    """VectorDomainClassifier 싱글톤을 리셋합니다 (테스트용)."""
    global _domain_classifier
    _domain_classifier = None
