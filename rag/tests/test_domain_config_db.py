"""도메인 설정 DB (MySQL) 테스트.

MySQL 연결을 mock하여 domain_classifier 모듈의 도메인 설정 로직을 검증합니다.
"""

import json
from unittest.mock import MagicMock, patch

import pytest

from utils.config import (
    DomainConfig,
    _get_default_config,
    init_db,
    load_domain_config,
    reload_domain_config,
    reset_domain_config,
    get_domain_config,
)


@pytest.fixture(autouse=True)
def _reset_cache():
    """각 테스트 전후로 모듈 캐시를 초기화합니다."""
    reset_domain_config()
    yield
    reset_domain_config()


def _make_mock_conn(
    tables_exist: bool = True,
    has_data: bool = True,
    domains: list | None = None,
    keywords: dict | None = None,
    compound_rules: list | None = None,
    rep_queries: dict | None = None,
):
    """테스트용 mock MySQL 연결을 생성합니다."""
    conn = MagicMock()
    cursor = MagicMock()
    conn.cursor.return_value.__enter__ = MagicMock(return_value=cursor)
    conn.cursor.return_value.__exit__ = MagicMock(return_value=False)

    if domains is None:
        domains = [
            {"domain_id": 1, "domain_key": "startup_funding"},
            {"domain_id": 2, "domain_key": "finance_tax"},
            {"domain_id": 3, "domain_key": "hr_labor"},
        ]

    if keywords is None:
        default = _get_default_config()
        keywords = default.keywords

    if compound_rules is None:
        default = _get_default_config()
        compound_rules = default.compound_rules

    if rep_queries is None:
        default = _get_default_config()
        rep_queries = default.representative_queries

    # fetchone 응답 설정 (tables_exist + has_data 체크용)
    tables_cnt = {"cnt": 1} if tables_exist else {"cnt": 0}
    data_cnt = {"cnt": 3} if has_data else {"cnt": 0}
    cursor.fetchone.side_effect = [tables_cnt, data_cnt]

    # fetchall 응답 설정 (도메인 → 키워드 → 규칙 → 쿼리)
    fetchall_results = [domains]

    # 도메인별 키워드
    domain_key_map = {d["domain_key"]: d["domain_id"] for d in domains}
    for dk in ["startup_funding", "finance_tax", "hr_labor"]:
        if dk in keywords:
            fetchall_results.append(
                [{"keyword": kw} for kw in keywords[dk]]
            )

    # 도메인별 복합 규칙
    rules_by_domain: dict[str, list] = {}
    for dk, lemmas in compound_rules:
        rules_by_domain.setdefault(dk, []).append(
            {"required_lemmas": json.dumps(sorted(lemmas), ensure_ascii=False)}
        )
    for dk in ["startup_funding", "finance_tax", "hr_labor"]:
        fetchall_results.append(rules_by_domain.get(dk, []))

    # 도메인별 대표 쿼리
    for dk in ["startup_funding", "finance_tax", "hr_labor"]:
        if dk in rep_queries:
            fetchall_results.append(
                [{"query_text": q} for q in rep_queries[dk]]
            )

    cursor.fetchall.side_effect = fetchall_results

    return conn


class TestDomainConfig:
    """DomainConfig 데이터 클래스 테스트."""

    def test_empty_config(self):
        """빈 DomainConfig 생성."""
        config = DomainConfig()
        assert config.keywords == {}
        assert config.compound_rules == []
        assert config.representative_queries == {}

    def test_default_config_has_data(self):
        """기본 설정에 데이터가 존재."""
        config = _get_default_config()
        assert "startup_funding" in config.keywords
        assert "finance_tax" in config.keywords
        assert "hr_labor" in config.keywords
        assert len(config.compound_rules) > 0
        assert len(config.representative_queries) > 0


class TestInitDB:
    """init_db() 테스트."""

    @patch("utils.config._get_connection")
    def test_skip_if_tables_exist_and_has_data(self, mock_get_conn):
        """테이블이 이미 있고 데이터도 있으면 건너뜁니다."""
        mock_conn = _make_mock_conn(tables_exist=True, has_data=True)
        mock_get_conn.return_value = mock_conn
        init_db()
        # _create_tables나 _seed_data가 호출되지 않음
        mock_conn.commit.assert_not_called()

    @patch("utils.config._get_connection")
    def test_fallback_on_connection_error(self, mock_get_conn):
        """연결 실패 시 경고만 출력하고 넘어갑니다."""
        mock_get_conn.side_effect = Exception("Connection refused")
        init_db()  # 예외 없이 완료


class TestLoadDomainConfig:
    """load_domain_config() 테스트."""

    @patch("utils.config._get_connection")
    def test_fallback_on_connection_error(self, mock_get_conn):
        """연결 실패 시 하드코딩 기본값을 반환합니다."""
        mock_get_conn.side_effect = Exception("Connection refused")
        config = load_domain_config()

        assert "startup_funding" in config.keywords
        assert "finance_tax" in config.keywords
        assert "hr_labor" in config.keywords
        assert len(config.compound_rules) > 0

    @patch("utils.config._get_connection")
    def test_load_from_db(self, mock_get_conn):
        """DB에서 올바르게 로드합니다."""
        mock_conn = _make_mock_conn()
        mock_get_conn.return_value = mock_conn
        config = load_domain_config()

        assert set(config.keywords.keys()) == {
            "startup_funding",
            "finance_tax",
            "hr_labor",
        }
        assert "창업" in config.keywords["startup_funding"]
        assert "세금" in config.keywords["finance_tax"]
        assert "퇴직금" in config.keywords["hr_labor"]

    @patch("utils.config._get_connection")
    def test_load_matches_hardcoded(self, mock_get_conn):
        """DB에서 로드한 값이 하드코딩 값과 일치합니다."""
        mock_conn = _make_mock_conn()
        mock_get_conn.return_value = mock_conn
        db_config = load_domain_config()
        default_config = _get_default_config()

        for domain_key in default_config.keywords:
            assert set(db_config.keywords[domain_key]) == set(
                default_config.keywords[domain_key]
            )

    @patch("utils.config._get_connection")
    def test_fallback_when_no_tables(self, mock_get_conn):
        """테이블이 없으면 하드코딩 기본값을 반환합니다."""
        mock_conn = _make_mock_conn(tables_exist=False)
        # tables_exist=False이면 fetchone이 {"cnt": 0}만 반환
        cursor = MagicMock()
        mock_conn.cursor.return_value.__enter__ = MagicMock(return_value=cursor)
        mock_conn.cursor.return_value.__exit__ = MagicMock(return_value=False)
        cursor.fetchone.return_value = {"cnt": 0}
        mock_get_conn.return_value = mock_conn

        config = load_domain_config()
        assert "startup_funding" in config.keywords

    @patch("utils.config._get_connection")
    def test_compound_rule_lemmas_are_sets(self, mock_get_conn):
        """복합 규칙의 required_lemmas가 set으로 로드됩니다."""
        mock_conn = _make_mock_conn()
        mock_get_conn.return_value = mock_conn
        config = load_domain_config()

        for _, lemmas in config.compound_rules:
            assert isinstance(lemmas, set)


class TestGetDomainConfig:
    """get_domain_config() 싱글톤 테스트."""

    @patch("utils.config._get_connection")
    def test_returns_same_instance(self, mock_get_conn):
        """같은 인스턴스를 반환합니다."""
        mock_get_conn.side_effect = Exception("Connection refused")
        config1 = get_domain_config()
        config2 = get_domain_config()
        assert config1 is config2

    @patch("utils.config._get_connection")
    def test_returns_valid_config(self, mock_get_conn):
        """유효한 설정을 반환합니다."""
        mock_get_conn.side_effect = Exception("Connection refused")
        config = get_domain_config()
        assert isinstance(config, DomainConfig)
        assert len(config.keywords) > 0


class TestReloadDomainConfig:
    """reload_domain_config() 테스트."""

    @patch("utils.config._get_connection")
    def test_reload_returns_fresh_config(self, mock_get_conn):
        """리로드 시 새 인스턴스를 반환합니다."""
        mock_get_conn.side_effect = Exception("Connection refused")
        config1 = get_domain_config()
        config2 = reload_domain_config()
        assert config1 is not config2
