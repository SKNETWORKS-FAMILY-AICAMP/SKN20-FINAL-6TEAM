"""MySQL 기반 도메인 분류 설정 관리 모듈.

도메인 키워드, 복합 규칙, 대표 쿼리를 MySQL DB에서 관리합니다.
DB 연결 실패 시 기존 하드코딩 값으로 자동 fallback합니다.
"""

import json
import logging
from dataclasses import dataclass, field

import pymysql

logger = logging.getLogger(__name__)

# 모듈 레벨 캐시
_domain_config: "DomainConfig | None" = None


@dataclass
class DomainConfig:
    """도메인 분류 설정 데이터.

    Attributes:
        keywords: 도메인별 키워드 리스트
        compound_rules: (도메인, 필수 lemma 집합) 튜플 리스트
        representative_queries: 도메인별 대표 쿼리 리스트
    """

    keywords: dict[str, list[str]] = field(default_factory=dict)
    compound_rules: list[tuple[str, set[str]]] = field(default_factory=list)
    representative_queries: dict[str, list[str]] = field(default_factory=dict)


def _get_default_config() -> DomainConfig:
    """하드코딩된 기본 설정을 반환합니다 (fallback용).

    Returns:
        기본 DomainConfig
    """
    from utils.prompts import _DEFAULT_DOMAIN_COMPOUND_RULES, _DEFAULT_DOMAIN_KEYWORDS

    from utils.domain_classifier import DOMAIN_REPRESENTATIVE_QUERIES as _DEFAULT_QUERIES

    return DomainConfig(
        keywords=dict(_DEFAULT_DOMAIN_KEYWORDS),
        compound_rules=list(_DEFAULT_DOMAIN_COMPOUND_RULES),
        representative_queries=dict(_DEFAULT_QUERIES),
    )


def _get_connection() -> pymysql.Connection:
    """MySQL 연결을 생성합니다.

    Returns:
        pymysql Connection 객체
    """
    from utils.config import get_settings

    settings = get_settings()
    return pymysql.connect(
        host=settings.mysql_host,
        port=settings.mysql_port,
        user=settings.mysql_user,
        password=settings.mysql_password,
        database=settings.mysql_database,
        charset="utf8mb4",
        cursorclass=pymysql.cursors.DictCursor,
    )


def _tables_exist(conn: pymysql.Connection) -> bool:
    """도메인 설정 테이블이 존재하는지 확인합니다."""
    with conn.cursor() as cursor:
        cursor.execute(
            "SELECT COUNT(*) AS cnt FROM information_schema.tables "
            "WHERE table_schema = DATABASE() AND table_name = 'domain'"
        )
        result = cursor.fetchone()
        return result["cnt"] > 0


def _has_data(conn: pymysql.Connection) -> bool:
    """도메인 테이블에 데이터가 있는지 확인합니다."""
    with conn.cursor() as cursor:
        cursor.execute("SELECT COUNT(*) AS cnt FROM domain")
        result = cursor.fetchone()
        return result["cnt"] > 0


def init_db() -> None:
    """MySQL에 도메인 설정 테이블을 생성하고 시드 데이터를 삽입합니다.

    테이블이 이미 존재하고 데이터가 있으면 건너뜁니다.
    """
    try:
        conn = _get_connection()
    except Exception:
        logger.warning("[도메인 설정 DB] MySQL 연결 실패, 하드코딩 기본값 사용")
        return

    try:
        if _tables_exist(conn) and _has_data(conn):
            logger.info("[도메인 설정 DB] 기존 테이블/데이터 사용")
            return

        if not _tables_exist(conn):
            _create_tables(conn)

        if not _has_data(conn):
            _seed_data(conn)
            conn.commit()
            logger.info("[도메인 설정 DB] 시드 데이터 삽입 완료")
    finally:
        conn.close()


def _create_tables(conn: pymysql.Connection) -> None:
    """테이블을 생성합니다."""
    with conn.cursor() as cursor:
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS `domain` (
                `domain_id` INT NOT NULL AUTO_INCREMENT PRIMARY KEY,
                `domain_key` VARCHAR(50) NOT NULL UNIQUE,
                `name` VARCHAR(100) NOT NULL,
                `sort_order` INT DEFAULT 0,
                `create_date` DATETIME DEFAULT CURRENT_TIMESTAMP,
                `update_date` DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
                `use_yn` TINYINT(1) NOT NULL DEFAULT 1
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
        """)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS `domain_keyword` (
                `keyword_id` INT NOT NULL AUTO_INCREMENT PRIMARY KEY,
                `domain_id` INT NOT NULL,
                `keyword` VARCHAR(100) NOT NULL,
                `keyword_type` VARCHAR(20) DEFAULT 'noun',
                `create_date` DATETIME DEFAULT CURRENT_TIMESTAMP,
                `update_date` DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
                `use_yn` TINYINT(1) NOT NULL DEFAULT 1,
                FOREIGN KEY (`domain_id`) REFERENCES `domain`(`domain_id`) ON DELETE CASCADE,
                UNIQUE KEY `uq_domain_keyword` (`domain_id`, `keyword`)
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
        """)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS `domain_compound_rule` (
                `rule_id` INT NOT NULL AUTO_INCREMENT PRIMARY KEY,
                `domain_id` INT NOT NULL,
                `required_lemmas` JSON NOT NULL,
                `description` VARCHAR(255) DEFAULT NULL,
                `create_date` DATETIME DEFAULT CURRENT_TIMESTAMP,
                `update_date` DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
                `use_yn` TINYINT(1) NOT NULL DEFAULT 1,
                FOREIGN KEY (`domain_id`) REFERENCES `domain`(`domain_id`) ON DELETE CASCADE
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
        """)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS `domain_representative_query` (
                `query_id` INT NOT NULL AUTO_INCREMENT PRIMARY KEY,
                `domain_id` INT NOT NULL,
                `query_text` VARCHAR(500) NOT NULL,
                `create_date` DATETIME DEFAULT CURRENT_TIMESTAMP,
                `update_date` DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
                `use_yn` TINYINT(1) NOT NULL DEFAULT 1,
                FOREIGN KEY (`domain_id`) REFERENCES `domain`(`domain_id`) ON DELETE CASCADE
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
        """)
    conn.commit()
    logger.info("[도메인 설정 DB] 테이블 생성 완료")


def _seed_data(conn: pymysql.Connection) -> None:
    """현재 하드코딩 값으로 시드 데이터를 삽입합니다."""
    default = _get_default_config()

    domain_names = {
        "startup_funding": "창업/지원사업",
        "finance_tax": "재무/세무",
        "hr_labor": "인사/노무",
    }

    domain_ids: dict[str, int] = {}

    with conn.cursor() as cursor:
        # 도메인 삽입
        for i, domain_key in enumerate(["startup_funding", "finance_tax", "hr_labor"]):
            name = domain_names[domain_key]
            cursor.execute(
                "INSERT INTO domain (domain_key, name, sort_order) VALUES (%s, %s, %s)",
                (domain_key, name, i),
            )
            domain_ids[domain_key] = cursor.lastrowid

        # 키워드 삽입
        for domain_key, keywords in default.keywords.items():
            domain_id = domain_ids[domain_key]
            for kw in keywords:
                kw_type = "verb" if kw.endswith("다") else "noun"
                cursor.execute(
                    "INSERT INTO domain_keyword (domain_id, keyword, keyword_type) "
                    "VALUES (%s, %s, %s)",
                    (domain_id, kw, kw_type),
                )

        # 복합 규칙 삽입
        for domain_key, required_lemmas in default.compound_rules:
            domain_id = domain_ids[domain_key]
            lemmas_json = json.dumps(sorted(required_lemmas), ensure_ascii=False)
            desc = "+".join(sorted(required_lemmas)) + " → " + domain_key
            cursor.execute(
                "INSERT INTO domain_compound_rule (domain_id, required_lemmas, description) "
                "VALUES (%s, %s, %s)",
                (domain_id, lemmas_json, desc),
            )

        # 대표 쿼리 삽입
        for domain_key, queries in default.representative_queries.items():
            domain_id = domain_ids[domain_key]
            for query_text in queries:
                cursor.execute(
                    "INSERT INTO domain_representative_query (domain_id, query_text) "
                    "VALUES (%s, %s)",
                    (domain_id, query_text),
                )


def load_domain_config() -> DomainConfig:
    """MySQL에서 도메인 설정을 로드합니다.

    DB 연결 실패 시 하드코딩 기본값을 반환합니다.

    Returns:
        DomainConfig 인스턴스
    """
    try:
        conn = _get_connection()
    except Exception:
        logger.warning("[도메인 설정 DB] MySQL 연결 실패, 하드코딩 기본값 사용")
        return _get_default_config()

    try:
        if not _tables_exist(conn) or not _has_data(conn):
            logger.warning("[도메인 설정 DB] 테이블/데이터 없음, 하드코딩 기본값 사용")
            return _get_default_config()

        config = DomainConfig()

        with conn.cursor() as cursor:
            # 활성 도메인 조회
            cursor.execute(
                "SELECT domain_id, domain_key FROM domain "
                "WHERE use_yn = 1 ORDER BY sort_order"
            )
            domains = cursor.fetchall()

            domain_map: dict[int, str] = {
                row["domain_id"]: row["domain_key"] for row in domains
            }

            # 키워드 로드
            for domain_id, domain_key in domain_map.items():
                cursor.execute(
                    "SELECT keyword FROM domain_keyword "
                    "WHERE domain_id = %s AND use_yn = 1",
                    (domain_id,),
                )
                config.keywords[domain_key] = [
                    row["keyword"] for row in cursor.fetchall()
                ]

            # 복합 규칙 로드
            for domain_id, domain_key in domain_map.items():
                cursor.execute(
                    "SELECT required_lemmas FROM domain_compound_rule "
                    "WHERE domain_id = %s AND use_yn = 1",
                    (domain_id,),
                )
                for row in cursor.fetchall():
                    lemmas_raw = row["required_lemmas"]
                    # MySQL JSON 컬럼은 이미 파싱된 리스트로 반환될 수 있음
                    if isinstance(lemmas_raw, str):
                        lemmas = set(json.loads(lemmas_raw))
                    else:
                        lemmas = set(lemmas_raw)
                    config.compound_rules.append((domain_key, lemmas))

            # 대표 쿼리 로드
            for domain_id, domain_key in domain_map.items():
                cursor.execute(
                    "SELECT query_text FROM domain_representative_query "
                    "WHERE domain_id = %s AND use_yn = 1",
                    (domain_id,),
                )
                config.representative_queries[domain_key] = [
                    row["query_text"] for row in cursor.fetchall()
                ]

        logger.info(
            "[도메인 설정 DB] 로드 완료: 키워드 %d개, 규칙 %d개, 쿼리 %d개",
            sum(len(kws) for kws in config.keywords.values()),
            len(config.compound_rules),
            sum(len(qs) for qs in config.representative_queries.values()),
        )
        return config

    finally:
        conn.close()


def get_domain_config() -> DomainConfig:
    """캐시된 DomainConfig 싱글톤을 반환합니다.

    Returns:
        DomainConfig 인스턴스
    """
    global _domain_config
    if _domain_config is None:
        _domain_config = load_domain_config()
    return _domain_config


def reload_domain_config() -> DomainConfig:
    """도메인 설정을 다시 로드합니다.

    Returns:
        새로 로드된 DomainConfig
    """
    global _domain_config
    _domain_config = load_domain_config()
    logger.info("[도메인 설정 DB] 설정 리로드 완료")
    return _domain_config


def reset_domain_config() -> None:
    """캐시된 DomainConfig를 초기화합니다 (테스트용)."""
    global _domain_config
    _domain_config = None
