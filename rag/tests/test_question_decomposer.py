"""QuestionDecomposer 단위 테스트.

질문 분해 로직, 캐싱, 대화 이력 활용, 폴백 처리를 검증합니다.
"""

import json
from unittest.mock import MagicMock, AsyncMock, patch

import pytest

from utils.question_decomposer import (
    QuestionDecomposer,
    SubQuery,
    _build_cache_key,
    _format_history,
)


# ============================================================
# Fixtures
# ============================================================


@pytest.fixture
def decomposer():
    """QuestionDecomposer 인스턴스를 생성합니다."""
    with patch("utils.question_decomposer.get_settings") as mock_settings, \
         patch("utils.question_decomposer.create_llm"):
        mock_settings.return_value = MagicMock(
            openai_model="gpt-4o-mini",
            openai_api_key="sk-test-key",
        )
        return QuestionDecomposer()


def _make_llm_response(sub_queries: list[dict]) -> str:
    """LLM 응답 JSON 문자열을 생성합니다."""
    return json.dumps({"sub_queries": sub_queries}, ensure_ascii=False)


def _make_llm_response_with_code_block(sub_queries: list[dict]) -> str:
    """코드 블록으로 감싼 LLM 응답을 생성합니다."""
    payload = json.dumps({"sub_queries": sub_queries}, ensure_ascii=False)
    return f"```json\n{payload}\n```"


# ============================================================
# 단일 도메인 스킵 테스트
# ============================================================


class TestSingleDomainSkip:
    """단일 도메인 시 LLM 호출 없이 원본 반환."""

    def test_single_domain_skip(self, decomposer: QuestionDecomposer):
        result = decomposer.decompose("사업자등록 절차", ["startup_funding"])

        assert len(result) == 1
        assert result[0].domain == "startup_funding"
        assert result[0].query == "사업자등록 절차"

    def test_empty_domains_defaults_to_startup(self, decomposer: QuestionDecomposer):
        result = decomposer.decompose("질문입니다", [])

        assert len(result) == 1
        assert result[0].domain == "startup_funding"

    @pytest.mark.asyncio
    async def test_single_domain_skip_async(self, decomposer: QuestionDecomposer):
        result = await decomposer.adecompose("퇴직금 계산", ["hr_labor"])

        assert len(result) == 1
        assert result[0].domain == "hr_labor"
        assert result[0].query == "퇴직금 계산"


# ============================================================
# 멀티 도메인 분해 테스트
# ============================================================


class TestMultiDomainDecompose:
    """2개 이상 도메인 분해 테스트."""

    def test_two_domain_decompose(self, decomposer: QuestionDecomposer):
        mock_response = _make_llm_response([
            {"domain": "startup_funding", "query": "창업 절차 알려주세요"},
            {"domain": "finance_tax", "query": "세금 신고 방법 알려주세요"},
        ])

        with patch.object(decomposer, "llm") as mock_llm:
            mock_llm.__or__ = MagicMock()
            chain_mock = MagicMock()
            chain_mock.invoke.return_value = mock_response
            with patch(
                "utils.question_decomposer.ChatPromptTemplate.from_messages"
            ) as mock_prompt:
                mock_chain = MagicMock()
                mock_chain.__or__ = MagicMock(return_value=chain_mock)
                mock_prompt.return_value = mock_chain

                result = decomposer.decompose(
                    "창업 절차와 세금 신고 방법 알려주세요",
                    ["startup_funding", "finance_tax"],
                )

        assert len(result) == 2
        assert result[0].domain == "startup_funding"
        assert result[1].domain == "finance_tax"

    def test_three_domain_decompose(self, decomposer: QuestionDecomposer):
        mock_response = _make_llm_response([
            {"domain": "startup_funding", "query": "카페 창업 지원금"},
            {"domain": "finance_tax", "query": "카페 창업 세무"},
            {"domain": "hr_labor", "query": "카페 근로계약"},
        ])

        with patch.object(decomposer, "llm") as mock_llm:
            mock_llm.__or__ = MagicMock()
            chain_mock = MagicMock()
            chain_mock.invoke.return_value = mock_response
            with patch(
                "utils.question_decomposer.ChatPromptTemplate.from_messages"
            ) as mock_prompt:
                mock_chain = MagicMock()
                mock_chain.__or__ = MagicMock(return_value=chain_mock)
                mock_prompt.return_value = mock_chain

                result = decomposer.decompose(
                    "직원 5명 카페 지원금, 세무, 근로계약",
                    ["startup_funding", "finance_tax", "hr_labor"],
                )

        assert len(result) == 3
        domains = [sq.domain for sq in result]
        assert "startup_funding" in domains
        assert "finance_tax" in domains
        assert "hr_labor" in domains


# ============================================================
# 폴백 테스트
# ============================================================


class TestFallback:
    """JSON 파싱 실패 및 빈 결과 폴백 테스트."""

    def test_invalid_json_fallback(self, decomposer: QuestionDecomposer):
        """JSON 파싱 실패 시 원본 쿼리로 폴백."""
        with patch.object(decomposer, "llm") as mock_llm:
            mock_llm.__or__ = MagicMock()
            chain_mock = MagicMock()
            chain_mock.invoke.return_value = "이것은 유효한 JSON이 아닙니다"
            with patch(
                "utils.question_decomposer.ChatPromptTemplate.from_messages"
            ) as mock_prompt:
                mock_chain = MagicMock()
                mock_chain.__or__ = MagicMock(return_value=chain_mock)
                mock_prompt.return_value = mock_chain

                result = decomposer.decompose(
                    "창업하면서 세금은?",
                    ["startup_funding", "finance_tax"],
                )

        assert len(result) == 2
        assert all(sq.query == "창업하면서 세금은?" for sq in result)

    def test_empty_result_fallback(self, decomposer: QuestionDecomposer):
        """빈 결과 시 원본 쿼리로 폴백."""
        mock_response = _make_llm_response([])

        with patch.object(decomposer, "llm") as mock_llm:
            mock_llm.__or__ = MagicMock()
            chain_mock = MagicMock()
            chain_mock.invoke.return_value = mock_response
            with patch(
                "utils.question_decomposer.ChatPromptTemplate.from_messages"
            ) as mock_prompt:
                mock_chain = MagicMock()
                mock_chain.__or__ = MagicMock(return_value=chain_mock)
                mock_prompt.return_value = mock_chain

                result = decomposer.decompose(
                    "창업하면서 세금은?",
                    ["startup_funding", "finance_tax"],
                )

        assert len(result) == 2
        assert all(sq.query == "창업하면서 세금은?" for sq in result)

    def test_invalid_domain_filtered(self, decomposer: QuestionDecomposer):
        """detected_domains에 없는 도메인은 필터링."""
        mock_response = _make_llm_response([
            {"domain": "startup_funding", "query": "창업 절차"},
            {"domain": "unknown_domain", "query": "알 수 없는 도메인"},
            {"domain": "finance_tax", "query": "세금 신고"},
        ])

        with patch.object(decomposer, "llm") as mock_llm:
            mock_llm.__or__ = MagicMock()
            chain_mock = MagicMock()
            chain_mock.invoke.return_value = mock_response
            with patch(
                "utils.question_decomposer.ChatPromptTemplate.from_messages"
            ) as mock_prompt:
                mock_chain = MagicMock()
                mock_chain.__or__ = MagicMock(return_value=chain_mock)
                mock_prompt.return_value = mock_chain

                result = decomposer.decompose(
                    "창업과 세금",
                    ["startup_funding", "finance_tax"],
                )

        assert len(result) == 2
        domains = [sq.domain for sq in result]
        assert "unknown_domain" not in domains


# ============================================================
# 대화 이력 테스트
# ============================================================


class TestHistory:
    """대화 이력(history) 활용 테스트."""

    def test_history_included_in_prompt(self, decomposer: QuestionDecomposer):
        """history가 프롬프트 변수에 포함되는지 검증."""
        history = [
            {"role": "user", "content": "카페 창업하려고 합니다"},
            {"role": "assistant", "content": "카페 창업 절차를 안내드리겠습니다..."},
        ]

        variables = decomposer._build_prompt_variables(
            query="그러면 세금은요?",
            detected_domains=["startup_funding", "finance_tax"],
            history=history,
        )

        assert "history_section" in variables
        assert "카페 창업하려고 합니다" in variables["history_section"]
        assert "카페 창업 절차를 안내드리겠습니다" in variables["history_section"]

    def test_no_history_empty_section(self, decomposer: QuestionDecomposer):
        """history 없으면 빈 섹션."""
        variables = decomposer._build_prompt_variables(
            query="창업과 세금",
            detected_domains=["startup_funding", "finance_tax"],
            history=None,
        )

        assert variables["history_section"] == ""

    def test_format_history_max_turns(self):
        """최근 N턴만 포함되는지 검증."""
        # user+assistant 쌍으로 구성된 이력 (5턴)
        history = []
        for i in range(5):
            history.append({"role": "user", "content": f"질문 {i}"})
            history.append({"role": "assistant", "content": f"답변 {i}"})

        # max_turns=2이면 최근 4개 메시지 (2턴 * 2 = 4 메시지)
        result = _format_history(history, max_turns=2)
        assert "질문 2" not in result
        assert "질문 3" in result
        assert "답변 3" in result
        assert "질문 4" in result
        assert "답변 4" in result


# ============================================================
# 캐싱 테스트
# ============================================================


class TestCaching:
    """분해 결과 캐싱 테스트."""

    def test_cache_hit(self, decomposer: QuestionDecomposer):
        """동일 쿼리+도메인 시 캐시 히트."""
        cached_result = [
            SubQuery(domain="startup_funding", query="창업 절차"),
            SubQuery(domain="finance_tax", query="세금 신고"),
        ]

        # 캐시에 직접 저장
        cache_key = _build_cache_key(
            "창업과 세금", ["startup_funding", "finance_tax"], None,
        )
        decomposer._cache.set(cache_key, cached_result)

        result = decomposer.decompose(
            "창업과 세금", ["startup_funding", "finance_tax"],
        )

        assert result == cached_result

    def test_cache_miss_different_query(self, decomposer: QuestionDecomposer):
        """다른 쿼리면 캐시 미스."""
        cached_result = [
            SubQuery(domain="startup_funding", query="창업 절차"),
            SubQuery(domain="finance_tax", query="세금 신고"),
        ]

        cache_key = _build_cache_key(
            "창업과 세금", ["startup_funding", "finance_tax"], None,
        )
        decomposer._cache.set(cache_key, cached_result)

        # 다른 쿼리로 조회 → 캐시 미스 → LLM 호출 필요
        different_key = _build_cache_key(
            "퇴직금과 세금", ["hr_labor", "finance_tax"], None,
        )
        assert decomposer._cache.get(different_key) is None

    def test_cache_key_includes_history(self):
        """history가 캐시 키에 영향을 주는지 검증."""
        key_no_history = _build_cache_key(
            "질문", ["startup_funding", "finance_tax"], None,
        )
        key_with_history = _build_cache_key(
            "질문",
            ["startup_funding", "finance_tax"],
            [{"role": "assistant", "content": "이전 답변"}],
        )

        assert key_no_history != key_with_history


# ============================================================
# 비동기 테스트
# ============================================================


class TestAsync:
    """비동기 분해 테스트."""

    @pytest.mark.asyncio
    async def test_adecompose_async(self, decomposer: QuestionDecomposer):
        """비동기 분해가 chain.ainvoke를 사용하는지 검증."""
        mock_response = _make_llm_response([
            {"domain": "startup_funding", "query": "창업 절차"},
            {"domain": "finance_tax", "query": "세금 신고"},
        ])

        # chain = prompt | llm | parser 전체를 모킹
        mock_final_chain = MagicMock()
        mock_final_chain.ainvoke = AsyncMock(return_value=mock_response)

        # prompt | llm 의 결과 (중간 체인)
        mock_intermediate = MagicMock()
        mock_intermediate.__or__ = MagicMock(return_value=mock_final_chain)

        # prompt 모킹 - prompt | llm 시 중간 체인 반환
        mock_prompt_instance = MagicMock()
        mock_prompt_instance.__or__ = MagicMock(return_value=mock_intermediate)

        with patch(
            "utils.question_decomposer.ChatPromptTemplate.from_messages",
            return_value=mock_prompt_instance,
        ):
            result = await decomposer.adecompose(
                "창업과 세금",
                ["startup_funding", "finance_tax"],
            )

        assert len(result) == 2
        mock_final_chain.ainvoke.assert_called_once()


# ============================================================
# 유틸리티 함수 테스트
# ============================================================


class TestUtilityFunctions:
    """헬퍼 함수 단위 테스트."""

    def test_format_history_empty(self):
        assert _format_history([]) == ""

    def test_format_history_filters_roles(self):
        history = [
            {"role": "system", "content": "시스템 메시지"},
            {"role": "user", "content": "유저 질문"},
            {"role": "assistant", "content": "AI 답변"},
        ]
        result = _format_history(history)
        assert "시스템 메시지" not in result
        assert "유저 질문" in result
        assert "AI 답변" in result

    def test_build_cache_key_deterministic(self):
        key1 = _build_cache_key("질문", ["a", "b"], None)
        key2 = _build_cache_key("질문", ["a", "b"], None)
        assert key1 == key2

    def test_build_cache_key_domain_order_independent(self):
        """도메인 순서가 달라도 같은 키."""
        key1 = _build_cache_key("질문", ["a", "b"], None)
        key2 = _build_cache_key("질문", ["b", "a"], None)
        assert key1 == key2
