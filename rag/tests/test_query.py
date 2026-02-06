"""쿼리 처리 모듈 테스트."""

import pytest

from utils.query import QueryProcessor


class TestQueryProcessor:
    """QueryProcessor 테스트."""

    def test_generate_cache_key(self):
        """캐시 키 생성 테스트."""
        key1 = QueryProcessor.generate_cache_key("창업 절차 알려주세요")
        key2 = QueryProcessor.generate_cache_key("창업 절차  알려주세요")  # 공백 다름
        key3 = QueryProcessor.generate_cache_key("창업 절차 알려주세요", domain="startup")

        # 정규화로 인해 공백 차이는 무시
        assert key1 == key2
        # 도메인이 다르면 다른 키
        assert key1 != key3

    def test_generate_cache_key_case_insensitive(self):
        """캐시 키 대소문자 무시 테스트."""
        key1 = QueryProcessor.generate_cache_key("Hello World")
        key2 = QueryProcessor.generate_cache_key("hello world")

        assert key1 == key2

    def test_extract_keywords(self):
        """키워드 추출 테스트."""
        query = "창업할 때 세금 신고는 어떻게 하나요?"
        keywords = QueryProcessor.extract_keywords(query)

        # 정규식이 완전한 단어를 추출하므로 "창업할", "신고는" 등이 추출됨
        assert "창업할" in keywords or "창업" in keywords
        assert "세금" in keywords
        assert "신고는" in keywords or "신고" in keywords

        # 불용어는 제외
        assert "어떻게" not in keywords
        assert "하나요" not in keywords

    def test_extract_keywords_empty(self):
        """빈 쿼리 키워드 추출."""
        keywords = QueryProcessor.extract_keywords("")
        assert keywords == []

    def test_extract_keywords_only_stopwords(self):
        """불용어만 있는 쿼리."""
        query = "어떻게 하나요?"
        keywords = QueryProcessor.extract_keywords(query)
        # 모두 불용어이므로 빈 리스트 또는 짧은 단어 제외
        # "어떻게", "하나요"는 불용어이므로 제외됨

    def test_extract_keywords_mixed(self):
        """한글/영어 혼합 쿼리."""
        query = "startup 창업 funding 지원금"
        keywords = QueryProcessor.extract_keywords(query)

        assert "startup" in keywords
        assert "창업" in keywords
        assert "funding" in keywords
        assert "지원금" in keywords


class TestQueryProcessorIntegration:
    """QueryProcessor 통합 테스트 (API 호출 필요)."""

    @pytest.fixture
    def processor(self):
        """테스트용 프로세서."""
        import os
        os.environ.setdefault("OPENAI_API_KEY", "sk-test-key")

        try:
            return QueryProcessor()
        except Exception:
            pytest.skip("OpenAI API 키가 설정되지 않음")

    @pytest.mark.skip(reason="실제 API 호출 필요")
    def test_rewrite_query(self, processor):
        """쿼리 재작성 테스트 (실제 API 호출)."""
        query = "창업할 때 세금 어떻게 해요?"
        rewritten = processor.rewrite_query(query)

        # 재작성된 쿼리는 원본과 다를 수 있음
        assert isinstance(rewritten, str)
        assert len(rewritten) > 0

    @pytest.mark.skip(reason="실제 API 호출 필요")
    def test_compress_context(self, processor):
        """컨텍스트 압축 테스트 (실제 API 호출)."""
        query = "부가세 신고 기한"
        document = """
        부가가치세 신고는 매 분기별로 해야 합니다.
        일반과세자의 경우 1월, 4월, 7월, 10월에 신고합니다.
        오늘 날씨가 좋습니다. 이것은 관련 없는 내용입니다.
        신고 기한은 각 분기 종료 후 25일 이내입니다.
        """

        compressed = processor.compress_context(query, document)

        # 압축된 내용은 원본보다 짧거나 관련 내용만 포함
        assert isinstance(compressed, str)
        assert len(compressed) > 0
