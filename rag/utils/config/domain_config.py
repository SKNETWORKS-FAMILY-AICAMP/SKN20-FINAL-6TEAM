"""MySQL 기반 도메인 설정 관리.

DomainConfig 데이터클래스와 DB CRUD 함수를 제공합니다.
domain 테이블 대신 code 테이블(code_id INT PK)을 직접 참조합니다.
"""

import json
import logging
from dataclasses import dataclass, field

import pymysql

from utils.config.domain_data import (
    DOMAIN_REPRESENTATIVE_QUERIES,
    _DEFAULT_DOMAIN_COMPOUND_RULES,
    _DEFAULT_DOMAIN_KEYWORDS,
)
from utils.config.settings import get_settings

logger = logging.getLogger(__name__)

# code 테이블 code 값 → 내부 domain_key 매핑
# code 테이블의 A 코드(에이전트)가 domain을 대표합니다.
AGENT_CODE_TO_DOMAIN: dict[str, str] = {
    "A0000002": "startup_funding",
    "A0000003": "finance_tax",
    "A0000004": "hr_labor",
    "A0000007": "law_common",
}

# 역방향 매핑
DOMAIN_TO_AGENT_CODE: dict[str, str] = {v: k for k, v in AGENT_CODE_TO_DOMAIN.items()}


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


# 모듈 레벨 캐시
_domain_config: DomainConfig | None = None


def _get_default_config() -> DomainConfig:
    """하드코딩된 기본 설정을 반환합니다 (fallback용).

    Returns:
        기본 DomainConfig
    """
    return DomainConfig(
        keywords=dict(_DEFAULT_DOMAIN_KEYWORDS),
        compound_rules=list(_DEFAULT_DOMAIN_COMPOUND_RULES),
        representative_queries=dict(DOMAIN_REPRESENTATIVE_QUERIES),
    )


def _get_connection() -> pymysql.Connection:
    """MySQL 연결을 생성합니다.

    Returns:
        pymysql Connection 객체
    """
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
            "WHERE table_schema = DATABASE() AND table_name = 'domain_keyword'"
        )
        result = cursor.fetchone()
        return result["cnt"] > 0


def _has_data(conn: pymysql.Connection) -> bool:
    """도메인 키워드 테이블에 데이터가 있는지 확인합니다."""
    with conn.cursor() as cursor:
        cursor.execute("SELECT COUNT(*) AS cnt FROM domain_keyword")
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
            CREATE TABLE IF NOT EXISTS `domain_keyword` (
                `keyword_id` INT NOT NULL AUTO_INCREMENT PRIMARY KEY,
                `code_id` INT NOT NULL COMMENT 'code 테이블 PK',
                `keyword` VARCHAR(100) NOT NULL,
                `keyword_type` VARCHAR(20) DEFAULT 'noun',
                `create_date` DATETIME DEFAULT CURRENT_TIMESTAMP,
                `update_date` DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
                `use_yn` TINYINT(1) NOT NULL DEFAULT 1,
                FOREIGN KEY (`code_id`) REFERENCES `code`(`code_id`) ON DELETE CASCADE ON UPDATE CASCADE,
                UNIQUE KEY `uq_code_keyword` (`code_id`, `keyword`)
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
        """)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS `domain_compound_rule` (
                `rule_id` INT NOT NULL AUTO_INCREMENT PRIMARY KEY,
                `code_id` INT NOT NULL COMMENT 'code 테이블 PK',
                `required_lemmas` JSON NOT NULL,
                `description` VARCHAR(255) DEFAULT NULL,
                `create_date` DATETIME DEFAULT CURRENT_TIMESTAMP,
                `update_date` DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
                `use_yn` TINYINT(1) NOT NULL DEFAULT 1,
                FOREIGN KEY (`code_id`) REFERENCES `code`(`code_id`) ON DELETE CASCADE ON UPDATE CASCADE
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
        """)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS `domain_representative_query` (
                `query_id` INT NOT NULL AUTO_INCREMENT PRIMARY KEY,
                `code_id` INT NOT NULL COMMENT 'code 테이블 PK',
                `query_text` VARCHAR(500) NOT NULL,
                `create_date` DATETIME DEFAULT CURRENT_TIMESTAMP,
                `update_date` DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
                `use_yn` TINYINT(1) NOT NULL DEFAULT 1,
                FOREIGN KEY (`code_id`) REFERENCES `code`(`code_id`) ON DELETE CASCADE ON UPDATE CASCADE
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
        """)
    conn.commit()
    logger.info("[도메인 설정 DB] 테이블 생성 완료")


def _get_code_id_map(conn: pymysql.Connection) -> dict[str, int]:
    """code 테이블에서 agent_code → code_id 매핑을 조회합니다.

    Returns:
        {agent_code_str: code_id_int} 딕셔너리
    """
    placeholders = ", ".join(["%s"] * len(AGENT_CODE_TO_DOMAIN))
    with conn.cursor() as cursor:
        cursor.execute(
            f"SELECT code_id, code FROM `code` WHERE `code` IN ({placeholders})",
            list(AGENT_CODE_TO_DOMAIN.keys()),
        )
        return {row["code"]: row["code_id"] for row in cursor.fetchall()}


def _seed_data(conn: pymysql.Connection) -> None:
    """현재 하드코딩 값으로 시드 데이터를 삽입합니다."""
    default = _get_default_config()
    code_id_map = _get_code_id_map(conn)

    with conn.cursor() as cursor:
        # 키워드 삽입
        for domain_key, keywords in default.keywords.items():
            agent_code = DOMAIN_TO_AGENT_CODE.get(domain_key)
            code_id = code_id_map.get(agent_code) if agent_code else None
            if not code_id:
                continue
            for kw in keywords:
                kw_type = "verb" if kw.endswith("다") else "noun"
                cursor.execute(
                    "INSERT IGNORE INTO domain_keyword (code_id, keyword, keyword_type) "
                    "VALUES (%s, %s, %s)",
                    (code_id, kw, kw_type),
                )

        # 복합 규칙 삽입
        for domain_key, required_lemmas in default.compound_rules:
            agent_code = DOMAIN_TO_AGENT_CODE.get(domain_key)
            code_id = code_id_map.get(agent_code) if agent_code else None
            if not code_id:
                continue
            lemmas_json = json.dumps(sorted(required_lemmas), ensure_ascii=False)
            desc = "+".join(sorted(required_lemmas)) + " → " + domain_key
            cursor.execute(
                "INSERT INTO domain_compound_rule (code_id, required_lemmas, description) "
                "VALUES (%s, %s, %s)",
                (code_id, lemmas_json, desc),
            )

        # 대표 쿼리 삽입
        for domain_key, queries in default.representative_queries.items():
            agent_code = DOMAIN_TO_AGENT_CODE.get(domain_key)
            code_id = code_id_map.get(agent_code) if agent_code else None
            if not code_id:
                continue
            for query_text in queries:
                cursor.execute(
                    "INSERT INTO domain_representative_query (code_id, query_text) "
                    "VALUES (%s, %s)",
                    (code_id, query_text),
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

        # code 테이블에서 code_id → domain_key 매핑 구성
        code_id_map = _get_code_id_map(conn)
        # {code_id_int: domain_key_str}
        id_to_domain: dict[int, str] = {
            code_id: AGENT_CODE_TO_DOMAIN[agent_code]
            for agent_code, code_id in code_id_map.items()
            if agent_code in AGENT_CODE_TO_DOMAIN
        }

        config = DomainConfig()

        with conn.cursor() as cursor:
            # 키워드 로드
            for code_id, domain_key in id_to_domain.items():
                cursor.execute(
                    "SELECT keyword FROM domain_keyword "
                    "WHERE code_id = %s AND use_yn = 1",
                    (code_id,),
                )
                config.keywords[domain_key] = [
                    row["keyword"] for row in cursor.fetchall()
                ]

            # 복합 규칙 로드
            for code_id, domain_key in id_to_domain.items():
                cursor.execute(
                    "SELECT required_lemmas FROM domain_compound_rule "
                    "WHERE code_id = %s AND use_yn = 1",
                    (code_id,),
                )
                for row in cursor.fetchall():
                    lemmas_raw = row["required_lemmas"]
                    if isinstance(lemmas_raw, str):
                        lemmas = set(json.loads(lemmas_raw))
                    else:
                        lemmas = set(lemmas_raw)
                    config.compound_rules.append((domain_key, lemmas))

            # 대표 쿼리 로드
            for code_id, domain_key in id_to_domain.items():
                cursor.execute(
                    "SELECT query_text FROM domain_representative_query "
                    "WHERE code_id = %s AND use_yn = 1",
                    (code_id,),
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
