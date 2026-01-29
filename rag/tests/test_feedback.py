"""피드백 분석 모듈 테스트."""

import pytest

from utils.feedback import (
    FeedbackAnalyzer,
    FeedbackType,
    SearchStrategy,
    get_feedback_analyzer,
)


class TestFeedbackType:
    """FeedbackType Enum 테스트."""

    def test_feedback_types_exist(self):
        """모든 피드백 유형이 정의되어 있는지 테스트."""
        assert FeedbackType.RETRIEVAL_QUALITY.value == "retrieval_quality"
        assert FeedbackType.ACCURACY.value == "accuracy"
        assert FeedbackType.COMPLETENESS.value == "completeness"
        assert FeedbackType.RELEVANCE.value == "relevance"
        assert FeedbackType.CITATION.value == "citation"
        assert FeedbackType.UNKNOWN.value == "unknown"


class TestSearchStrategy:
    """SearchStrategy 데이터클래스 테스트."""

    def test_default_values(self):
        """기본값 테스트."""
        strategy = SearchStrategy()

        assert strategy.k == 3
        assert strategy.k_common == 2
        assert strategy.use_query_rewrite is True
        assert strategy.use_mmr is True
        assert strategy.use_rerank is False
        assert strategy.use_hybrid is False
        assert strategy.mmr_lambda == 0.6
        assert strategy.fetch_k_multiplier == 4

    def test_custom_values(self):
        """커스텀 값 테스트."""
        strategy = SearchStrategy(
            k=5,
            k_common=3,
            use_rerank=True,
            use_hybrid=True,
        )

        assert strategy.k == 5
        assert strategy.k_common == 3
        assert strategy.use_rerank is True
        assert strategy.use_hybrid is True


class TestFeedbackAnalyzer:
    """FeedbackAnalyzer 테스트."""

    @pytest.fixture
    def analyzer(self):
        """FeedbackAnalyzer fixture."""
        return FeedbackAnalyzer()

    def test_analyze_retrieval_quality(self, analyzer):
        """검색 품질 피드백 분석 테스트."""
        feedback = "검색 결과가 부족합니다. 관련 문서를 더 찾아주세요."
        types = analyzer.analyze(feedback)

        assert FeedbackType.RETRIEVAL_QUALITY in types

    def test_analyze_accuracy(self, analyzer):
        """정확성 피드백 분석 테스트."""
        feedback = "정보가 부정확합니다. 잘못된 정보가 포함되어 있습니다."
        types = analyzer.analyze(feedback)

        assert FeedbackType.ACCURACY in types

    def test_analyze_completeness(self, analyzer):
        """완성도 피드백 분석 테스트."""
        feedback = "답변이 불완전합니다. 더 자세한 설명이 필요합니다."
        types = analyzer.analyze(feedback)

        assert FeedbackType.COMPLETENESS in types

    def test_analyze_relevance(self, analyzer):
        """관련성 피드백 분석 테스트."""
        feedback = "질문과 관련 없는 내용입니다."
        types = analyzer.analyze(feedback)

        assert FeedbackType.RELEVANCE in types

    def test_analyze_citation(self, analyzer):
        """출처 피드백 분석 테스트."""
        feedback = "출처가 명시되지 않았습니다. 근거 제시가 없습니다."
        types = analyzer.analyze(feedback)

        assert FeedbackType.CITATION in types

    def test_analyze_unknown(self, analyzer):
        """알 수 없는 피드백 분석 테스트."""
        feedback = "별다른 문제 없음"
        types = analyzer.analyze(feedback)

        assert FeedbackType.UNKNOWN in types

    def test_analyze_none(self, analyzer):
        """None 피드백 처리 테스트."""
        types = analyzer.analyze(None)

        assert FeedbackType.UNKNOWN in types

    def test_analyze_multiple_types(self, analyzer):
        """복합 피드백 분석 테스트."""
        feedback = "검색 품질이 부족하고 정보가 부정확합니다. 출처도 없습니다."
        types = analyzer.analyze(feedback)

        assert FeedbackType.RETRIEVAL_QUALITY in types
        assert FeedbackType.ACCURACY in types
        assert FeedbackType.CITATION in types


class TestSuggestStrategy:
    """검색 전략 제안 테스트."""

    @pytest.fixture
    def analyzer(self):
        """FeedbackAnalyzer fixture."""
        return FeedbackAnalyzer()

    def test_suggest_strategy_retrieval_quality(self, analyzer):
        """검색 품질 문제 시 전략 제안 테스트."""
        feedback = "검색 결과가 부족합니다."
        strategy = analyzer.suggest_strategy(feedback)

        assert strategy.k > 3  # 검색 결과 증가
        assert strategy.use_rerank is True  # Re-ranking 활성화
        assert strategy.use_hybrid is True  # Hybrid Search 활성화
        assert strategy.expand_search is True

    def test_suggest_strategy_accuracy(self, analyzer):
        """정확성 문제 시 전략 제안 테스트."""
        feedback = "정보가 부정확합니다."
        strategy = analyzer.suggest_strategy(feedback)

        assert strategy.use_query_rewrite is True
        assert strategy.use_rerank is True
        assert strategy.fetch_k_multiplier >= 4

    def test_suggest_strategy_relevance(self, analyzer):
        """관련성 문제 시 전략 제안 테스트."""
        feedback = "질문과 관련 없는 답변입니다."
        strategy = analyzer.suggest_strategy(feedback)

        assert strategy.use_query_rewrite is True
        assert strategy.mmr_lambda >= 0.6  # 유사도 중시

    def test_suggest_strategy_citation(self, analyzer):
        """출처 문제 시 전략 제안 테스트."""
        feedback = "출처가 없습니다."
        strategy = analyzer.suggest_strategy(feedback)

        assert strategy.k_common > 2  # 법령 DB 검색 강화

    def test_suggest_strategy_retry_count(self, analyzer):
        """재시도 횟수에 따른 전략 조정 테스트."""
        feedback = "일반적인 피드백"

        # 첫 번째 재시도
        strategy1 = analyzer.suggest_strategy(feedback, retry_count=1)
        assert strategy1.use_rerank is True
        assert strategy1.use_hybrid is True

    def test_suggest_strategy_with_current(self, analyzer):
        """기존 전략 기반 조정 테스트."""
        current = SearchStrategy(k=5, use_rerank=True)
        feedback = "검색 품질 부족"

        strategy = analyzer.suggest_strategy(
            feedback,
            current_strategy=current,
            retry_count=1,
        )

        # 기존 전략 기반으로 조정
        assert strategy.k >= 5


class TestExtractSuggestions:
    """제안사항 추출 테스트."""

    @pytest.fixture
    def analyzer(self):
        """FeedbackAnalyzer fixture."""
        return FeedbackAnalyzer()

    def test_extract_quoted_keywords(self, analyzer):
        """따옴표 안의 키워드 추출 테스트."""
        feedback = "'부가가치세'와 '법인세'에 대한 정보가 필요합니다."
        suggestions = analyzer.extract_suggestions(feedback)

        assert "부가가치세" in suggestions
        assert "법인세" in suggestions

    def test_extract_korean_brackets(self, analyzer):
        """한국어 꺾쇠 안의 키워드 추출 테스트."""
        feedback = "「근로기준법」 제50조를 참고하세요."
        suggestions = analyzer.extract_suggestions(feedback)

        assert "근로기준법" in suggestions

    def test_extract_empty(self, analyzer):
        """추출할 내용이 없는 경우 테스트."""
        feedback = "일반적인 피드백입니다."
        suggestions = analyzer.extract_suggestions(feedback)

        assert suggestions == []


class TestSingleton:
    """싱글톤 패턴 테스트."""

    def test_get_feedback_analyzer_singleton(self):
        """싱글톤 인스턴스 테스트."""
        analyzer1 = get_feedback_analyzer()
        analyzer2 = get_feedback_analyzer()

        assert analyzer1 is analyzer2
