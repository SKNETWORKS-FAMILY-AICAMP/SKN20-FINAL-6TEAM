#!/usr/bin/env python3
"""지원사업 공고 일일 배치 갱신 스크립트.

파이프라인:
    1. CRAWL      → 기업마당/K-Startup API에서 모집중 공고 수집
    2. S3 UPLOAD  → 공고문/신청양식 파일 다운로드 → S3 업로드
    3. DB SYNC    → MySQL announce 테이블 동기화 (추가/갱신/마감 분류)
    4. PREPROCESS → JSONL 변환 (RAG용 통합 스키마)
    5. VECTORDB   → upsert 후 마감 표시, 보존 기간 경과 문서 삭제

Usage:
    python scripts/batch/update_announcements.py
    python scripts/batch/update_announcements.py --count 5
    python scripts/batch/update_announcements.py --skip-vectordb
    python scripts/batch/update_announcements.py --dry-run

종료 코드:
    0: 성공
    1: 크롤링 실패
    2: 파일 업로드 실패
    3: DB 동기화 실패
    4: 전처리 실패
    5: VectorDB 갱신 실패
    6: 예상치 못한 오류
"""

import argparse
import json
import logging
import os
import sys
import time
from datetime import date, datetime
from logging.handlers import RotatingFileHandler
from pathlib import Path
from typing import Any

# 프로젝트 루트를 sys.path에 추가
PROJECT_ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))
sys.path.insert(0, str(PROJECT_ROOT / "rag"))

# .env 파일 로드
from dotenv import load_dotenv

load_dotenv(PROJECT_ROOT / ".env")

# =============================================================================
# 로깅 설정
# =============================================================================

LOG_DIR = PROJECT_ROOT / "logs"
LOG_DIR.mkdir(exist_ok=True)


def setup_logging(verbose: bool = False) -> logging.Logger:
    """로거를 설정합니다."""
    logger = logging.getLogger("batch.announcements")
    logger.setLevel(logging.DEBUG if verbose else logging.INFO)

    formatter = logging.Formatter(
        "%(asctime)s [%(levelname)s] %(name)s - %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    # 콘솔 핸들러
    console = logging.StreamHandler()
    console.setFormatter(formatter)
    logger.addHandler(console)

    # 파일 핸들러 (10MB x 5)
    file_handler = RotatingFileHandler(
        LOG_DIR / "batch_announcements.log",
        maxBytes=10 * 1024 * 1024,
        backupCount=5,
        encoding="utf-8",
    )
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)

    return logger


# =============================================================================
# DB 연결 헬퍼
# =============================================================================


def _create_db_engine():
    """SQLAlchemy 엔진을 생성합니다."""
    from sqlalchemy import create_engine

    host = os.getenv("MYSQL_HOST", "localhost")
    port = int(os.getenv("MYSQL_PORT", "3306"))
    user = os.getenv("MYSQL_USER", "root")
    password = os.getenv("MYSQL_PASSWORD", "")
    database = os.getenv("MYSQL_DATABASE", "bizi_db")

    url = f"mysql+pymysql://{user}:{password}@{host}:{port}/{database}"
    return create_engine(
        url,
        pool_pre_ping=True,
        pool_recycle=1800,
        hide_parameters=True,  # 에러 로그에서 비밀번호 숨김
    )


def _create_session(engine):
    """SQLAlchemy 세션을 생성합니다."""
    from sqlalchemy.orm import sessionmaker

    Session = sessionmaker(bind=engine, autocommit=False, autoflush=False)
    return Session()


# =============================================================================
# Email SMTP 알림
# =============================================================================


def _safe_error_message(e: Exception) -> str:
    """알림용 안전한 에러 메시지를 생성합니다."""
    error_type = type(e).__name__
    if error_type in (
        "OperationalError", "DatabaseError", "InterfaceError",
        "ConnectionError", "AuthenticationError",
    ):
        return f"{error_type}: 연결 또는 인증 오류 (서버 로그 참조)"
    first_line = str(e).split("\n")[0][:100]
    return f"{error_type}: {first_line}"


def _send_email_notification(
    subject: str, body: str, logger: logging.Logger
) -> None:
    """AWS SES로 이메일 알림을 보냅니다.

    SES_FROM, ALERT_EMAIL_TO 중 하나라도 미설정이면 건너뜁니다.
    EC2 Instance Role의 IAM 권한으로 자동 인증합니다 (별도 자격 증명 불필요).

    Args:
        subject: 이메일 제목
        body: 이메일 본문 (plain text)
        logger: 로거 인스턴스
    """
    ses_from = os.getenv("SES_FROM")
    alert_to = os.getenv("ALERT_EMAIL_TO")
    aws_region = os.getenv("AWS_REGION", os.getenv("AWS_DEFAULT_REGION", "ap-northeast-2"))

    if not ses_from or not alert_to:
        return  # SES 미설정 시 건너뜀

    try:
        import boto3

        client = boto3.client("ses", region_name=aws_region)
        client.send_email(
            Source=ses_from,
            Destination={"ToAddresses": alert_to.split(",")},
            Message={
                "Subject": {"Data": f"[Bizi 배치] {subject}", "Charset": "UTF-8"},
                "Body": {"Text": {"Data": body, "Charset": "UTF-8"}},
            },
        )
    except Exception as e:
        logger.warning("이메일 알림 전송 실패: %s", e)


# =============================================================================
# 메인 배치 클래스
# =============================================================================


class AnnouncementBatchUpdater:
    """지원사업 공고 배치 갱신 오케스트레이터.

    Args:
        count: 크롤링할 공고 수 (0=전체)
        skip_vectordb: True이면 VectorDB 갱신 건너뛰기
        dry_run: True이면 실제 DB/VectorDB 변경 없이 시뮬레이션
        verbose: 상세 로깅
    """

    def __init__(
        self,
        count: int = 0,
        skip_vectordb: bool = False,
        dry_run: bool = False,
        verbose: bool = False,
    ):
        self.count = count
        self.skip_vectordb = skip_vectordb
        self.dry_run = dry_run
        self.logger = setup_logging(verbose)
        self.start_time = time.time()

        # 결과 추적
        self.stats: dict[str, Any] = {
            "crawled": {"bizinfo": 0, "kstartup": 0},
            "s3_upload": {"docs": 0, "forms": 0, "errors": 0},
            "db_sync": {"inserted": 0, "updated": 0, "deactivated": 0},
            "preprocessed": 0,
            "vectordb": {"upserted": 0, "newly_closed": 0, "removed": 0},
        }

    def run(self) -> int:
        """배치 파이프라인을 실행합니다.

        Returns:
            종료 코드 (0=성공, 1~6=단계별 실패)
        """
        self.logger.info("=" * 60)
        self.logger.info("지원사업 공고 배치 갱신 시작")
        self.logger.info(
            "  count=%s, skip_vectordb=%s, dry_run=%s",
            "전체" if self.count == 0 else self.count,
            self.skip_vectordb,
            self.dry_run,
        )
        self.logger.info("=" * 60)

        try:
            # 1단계: 크롤링
            crawled_data = self._crawl()
            if crawled_data is None:
                return 1

            total_crawled = len(crawled_data.get("bizinfo", [])) + len(
                crawled_data.get("kstartup", [])
            )
            if total_crawled == 0:
                self.logger.warning("크롤링된 공고가 없습니다. 배치를 종료합니다.")
                self._report()
                return 0

            # 2단계: 파일 다운로드 + S3 업로드
            if not self._upload_files_to_s3(crawled_data):
                return 2

            # 3단계: DB 동기화
            if not self._sync_to_database(crawled_data):
                return 3

            # 4단계: 전처리 (JSONL 변환)
            if not self._preprocess(crawled_data):
                return 4

            # 5단계: VectorDB 갱신
            if not self.skip_vectordb:
                if not self._update_vectordb():
                    return 5
            else:
                self.logger.info("VectorDB 갱신 건너뜀 (--skip-vectordb)")

            self._report()
            return 0

        except Exception as e:
            self.logger.exception("예상치 못한 오류: %s", e)
            _send_email_notification(
                subject="[Bizi 배치] 공고 갱신 실패",
                body=f"예상치 못한 오류가 발생했습니다.\n\n{_safe_error_message(e)}",
                logger=self.logger,
            )
            return 6

    # -------------------------------------------------------------------------
    # 1단계: 크롤링
    # -------------------------------------------------------------------------

    def _crawl(self) -> dict[str, list[dict]] | None:
        """기업마당/K-Startup API에서 모집중 공고를 수집합니다."""
        self.logger.info("[1/5] 크롤링 시작...")

        try:
            from scripts.crawling.collect_announcements import (
                BizinfoClient,
                Config,
                KstartupClient,
                setup_logger,
            )

            config = Config()
            crawl_logger = setup_logger("batch.crawl")

            result: dict[str, list[dict]] = {"bizinfo": [], "kstartup": []}

            # 기업마당
            bizinfo = BizinfoClient(config.bizinfo_api_key, crawl_logger)
            result["bizinfo"] = self._crawl_with_retry(
                lambda: bizinfo.fetch(count=self.count, recruiting_only=True),
                "기업마당",
            )
            self.stats["crawled"]["bizinfo"] = len(result["bizinfo"])

            # K-Startup
            kstartup = KstartupClient(config.kstartup_api_key, crawl_logger)
            result["kstartup"] = self._crawl_with_retry(
                lambda: kstartup.fetch(count=self.count, recruiting_only=True),
                "K-Startup",
            )
            self.stats["crawled"]["kstartup"] = len(result["kstartup"])

            self.logger.info(
                "  크롤링 완료: 기업마당 %d건, K-Startup %d건",
                len(result["bizinfo"]),
                len(result["kstartup"]),
            )
            return result

        except Exception as e:
            self.logger.error("크롤링 실패: %s", e)
            _send_email_notification(
                subject="[Bizi 배치] 크롤링 실패",
                body=f"크롤링 단계에서 오류가 발생했습니다.\n\n{_safe_error_message(e)}",
                logger=self.logger,
            )
            return None

    def _crawl_with_retry(
        self,
        fetch_func,
        source_name: str,
        max_retries: int = 3,
    ) -> list[dict]:
        """재시도 로직으로 크롤링을 수행합니다."""
        for attempt in range(1, max_retries + 1):
            try:
                data = fetch_func()
                if data is not None:
                    return data
            except Exception as e:
                wait = 2**attempt
                self.logger.warning(
                    "  %s 크롤링 실패 (시도 %d/%d): %s — %d초 후 재시도",
                    source_name,
                    attempt,
                    max_retries,
                    e,
                    wait,
                )
                time.sleep(wait)

        self.logger.error("  %s 크롤링 최종 실패 (%d회 시도)", source_name, max_retries)
        return []

    # -------------------------------------------------------------------------
    # 2단계: 파일 다운로드 + S3 업로드
    # -------------------------------------------------------------------------

    def _upload_files_to_s3(self, crawled_data: dict[str, list[dict]]) -> bool:
        """파일을 다운로드하여 S3에 업로드하고, crawled_data에 S3 키를 주입합니다.

        S3_BUCKET_NAME 미설정 시 건너뛰고 True를 반환합니다 (graceful degradation).
        """
        self.logger.info("[2/5] 파일 다운로드 + S3 업로드...")

        bucket = os.getenv("S3_BUCKET_NAME")
        if not bucket:
            self.logger.info("  S3_BUCKET_NAME 미설정 — 파일 업로드 건너뜀")
            return True

        if self.dry_run:
            self.logger.info("  [DRY RUN] S3 업로드 건너뜀")
            return True

        try:
            from scripts.batch.s3_uploader import S3Uploader
            from scripts.crawling.collect_announcements import Config, FileDownloader

            region = os.getenv("AWS_DEFAULT_REGION", "ap-northeast-2")
            endpoint_url = os.getenv("S3_ENDPOINT_URL") or None
            uploader = S3Uploader(bucket, region, endpoint_url)
            config = Config()
            downloader = FileDownloader(config, self.logger)

            docs_uploaded = 0
            forms_uploaded = 0
            errors = 0

            for source_type, items in crawled_data.items():
                iter_func = (
                    downloader.iter_files_bizinfo
                    if source_type == "bizinfo"
                    else downloader.iter_files_kstartup
                )

                for item in items:
                    source_id = self._extract_source_id(source_type, item)
                    if not source_id:
                        continue

                    form_files: list[str] = []

                    # 공고문 다운로드 + S3 업로드 (첫 번째만)
                    doc_s3_key = ""
                    try:
                        for file_path in iter_func(source_id, item, form_files):
                            if file_path and file_path.exists():
                                s3_key = uploader.generate_key(
                                    source_type, source_id, "doc", file_path.name
                                )
                                doc_s3_key = uploader.upload_file(file_path, s3_key)
                                file_path.unlink(missing_ok=True)
                                docs_uploaded += 1
                                break  # 첫 번째 공고문만
                    except Exception as e:
                        self.logger.warning(
                            "  공고문 업로드 실패 [%s/%s]: %s",
                            source_type, source_id, e,
                        )
                        errors += 1

                    # 신청양식 S3 업로드 (첫 번째만)
                    form_s3_key = ""
                    if form_files:
                        try:
                            form_path = Path(form_files[0])
                            if form_path.exists():
                                s3_key = uploader.generate_key(
                                    source_type, source_id, "form", form_path.name
                                )
                                form_s3_key = uploader.upload_file(form_path, s3_key)
                                form_path.unlink(missing_ok=True)
                                forms_uploaded += 1
                        except Exception as e:
                            self.logger.warning(
                                "  신청양식 업로드 실패 [%s/%s]: %s",
                                source_type, source_id, e,
                            )
                            errors += 1

                    # crawled_data에 S3 키 주입
                    item["_doc_s3_key"] = doc_s3_key
                    item["_form_s3_key"] = form_s3_key

            self.stats["s3_upload"]["docs"] = docs_uploaded
            self.stats["s3_upload"]["forms"] = forms_uploaded
            self.stats["s3_upload"]["errors"] = errors

            self.logger.info(
                "  S3 업로드 완료: 공고문 %d건, 신청양식 %d건, 오류 %d건",
                docs_uploaded, forms_uploaded, errors,
            )
            return True

        except Exception as e:
            self.logger.error("파일 업로드 실패: %s", e)
            _send_email_notification(
                subject="[Bizi 배치] 파일 업로드 실패",
                body=f"S3 파일 업로드 단계에서 오류가 발생했습니다.\n\n{_safe_error_message(e)}",
                logger=self.logger,
            )
            return False

    # -------------------------------------------------------------------------
    # 3단계: DB 동기화
    # -------------------------------------------------------------------------

    def _sync_to_database(self, crawled_data: dict[str, list[dict]]) -> bool:
        """크롤링 데이터를 MySQL announce 테이블에 동기화합니다.

        분류 기준:
        - 신규: API에 있고 DB에 없음 → INSERT
        - 갱신: API에도 DB에도 있음 → UPDATE
        - 마감: DB에 있고(use_yn=1) API에 없음 → SET use_yn=0
        """
        self.logger.info("[3/5] DB 동기화 시작...")

        if self.dry_run:
            self.logger.info("  [DRY RUN] DB 변경 건너뜀")
            return True

        from sqlalchemy import select, and_

        # Announce 모델 직접 정의 — backend 의존성 없이 독립 실행 보장
        # (backend/apps/common/models.py의 Announce와 동일 스키마)
        from sqlalchemy import (
            Boolean,
            Column,
            Date,
            DateTime,
            Integer,
            String,
            Text,
        )
        from sqlalchemy.orm import declarative_base

        Base = declarative_base()

        class Announce(Base):
            __tablename__ = "announce"
            announce_id = Column(Integer, primary_key=True, autoincrement=True)
            ann_name = Column(String(255), nullable=False, default="")
            source_type = Column(String(20), nullable=False, default="")
            source_id = Column(String(50), nullable=False, default="")
            target_desc = Column(Text)
            exclusion_desc = Column(Text)
            amount_desc = Column(Text)
            apply_start = Column(Date)
            apply_end = Column(Date)
            region = Column(String(100), default="")
            organization = Column(String(200), default="")
            source_url = Column(String(500), default="")
            doc_s3_key = Column(String(500), default="")
            form_s3_key = Column(String(500), default="")
            biz_code = Column(String(8), default="BA000000")
            host_gov_code = Column(String(8))
            create_date = Column(DateTime, default=datetime.now)
            update_date = Column(DateTime, default=datetime.now, onupdate=datetime.now)
            use_yn = Column(Boolean, nullable=False, default=True)

        engine = None
        session = None
        try:
            engine = _create_db_engine()
            session = _create_session(engine)

            # 현재 활성 공고의 source_type+source_id 조회
            stmt = select(Announce.source_type, Announce.source_id).where(
                Announce.use_yn == True  # noqa: E712
            )
            existing = {
                (row.source_type, row.source_id)
                for row in session.execute(stmt).all()
            }
            self.logger.info("  현재 활성 공고: %d건", len(existing))

            # 크롤링된 공고를 (source_type, source_id) 집합으로
            crawled_keys: set[tuple[str, str]] = set()
            all_items: list[tuple[str, dict]] = []

            for item in crawled_data.get("bizinfo", []):
                source_id = str(item.get("pblancId", item.get("id", "")))
                if source_id:
                    crawled_keys.add(("bizinfo", source_id))
                    all_items.append(("bizinfo", item))

            for item in crawled_data.get("kstartup", []):
                source_id = str(item.get("pbanc_sn", item.get("id", "")))
                if source_id:
                    crawled_keys.add(("kstartup", source_id))
                    all_items.append(("kstartup", item))

            inserted = 0
            updated = 0

            for source_type, item in all_items:
                source_id = self._extract_source_id(source_type, item)
                if not source_id:
                    continue

                row_data = self._build_announce_row(source_type, item)

                if (source_type, source_id) in existing:
                    # UPDATE
                    stmt = (
                        select(Announce)
                        .where(
                            and_(
                                Announce.source_type == source_type,
                                Announce.source_id == source_id,
                            )
                        )
                    )
                    announce = session.execute(stmt).scalar_one_or_none()
                    if announce:
                        for key, value in row_data.items():
                            if key not in ("source_type", "source_id"):
                                setattr(announce, key, value)
                        announce.use_yn = True
                        updated += 1
                else:
                    # INSERT
                    announce = Announce(**row_data)
                    session.add(announce)
                    inserted += 1

            # 마감 처리: DB에 있고 API에 없는 공고 → use_yn=0
            deactivate_keys = existing - crawled_keys
            deactivated = 0
            for src_type, src_id in deactivate_keys:
                stmt = (
                    select(Announce)
                    .where(
                        and_(
                            Announce.source_type == src_type,
                            Announce.source_id == src_id,
                            Announce.use_yn == True,  # noqa: E712
                        )
                    )
                )
                announce = session.execute(stmt).scalar_one_or_none()
                if announce:
                    announce.use_yn = False
                    deactivated += 1

            session.commit()

            self.stats["db_sync"]["inserted"] = inserted
            self.stats["db_sync"]["updated"] = updated
            self.stats["db_sync"]["deactivated"] = deactivated

            self.logger.info(
                "  DB 동기화 완료: 추가 %d건, 갱신 %d건, 마감 %d건",
                inserted,
                updated,
                deactivated,
            )
            return True

        except Exception as e:
            self.logger.error("DB 동기화 실패: %s", e)
            _send_email_notification(
                subject="[Bizi 배치] DB 동기화 실패",
                body=f"DB 동기화 단계에서 오류가 발생했습니다.\n\n{_safe_error_message(e)}",
                logger=self.logger,
            )
            return False
        finally:
            if session is not None:
                session.close()
            if engine is not None:
                engine.dispose()

    @staticmethod
    def _extract_source_id(source_type: str, item: dict) -> str:
        """크롤링 아이템에서 source_id를 추출합니다."""
        if source_type == "bizinfo":
            return str(item.get("pblancId", item.get("id", "")))
        else:
            return str(item.get("pbanc_sn", item.get("id", "")))

    @staticmethod
    def _parse_date_safe(date_str: str | None) -> date | None:
        """날짜 문자열을 date 객체로 변환합니다."""
        if not date_str:
            return None
        date_str = date_str.strip()
        for fmt in ("%Y-%m-%d", "%Y%m%d", "%Y.%m.%d"):
            try:
                return datetime.strptime(date_str, fmt).date()
            except ValueError:
                continue
        return None

    def _build_announce_row(self, source_type: str, item: dict) -> dict[str, Any]:
        """크롤링 아이템을 announce 테이블 row 데이터로 변환합니다."""
        if source_type == "bizinfo":
            source_id = str(item.get("pblancId", item.get("id", "")))
            ann_name = item.get("pblancNm", "")
            target_desc = item.get("지원대상", "")
            exclusion_desc = item.get("제외대상", "")
            amount_desc = item.get("지원금액", "")
            organization = item.get("excInsttNm", "")
            region = item.get("jrsdInsttNm", "")

            # 접수기간 파싱
            date_range = item.get("reqstBeginEndDe", "")
            apply_start = None
            apply_end = None
            if "~" in date_range:
                parts = date_range.replace(" ", "").split("~")
                if len(parts) == 2:
                    apply_start = self._parse_date_safe(parts[0])
                    apply_end = self._parse_date_safe(parts[1])

            pbanc_url = item.get("pblancUrl", "")
            if pbanc_url and not pbanc_url.startswith("http"):
                pbanc_url = f"https://www.bizinfo.go.kr{pbanc_url}"

        else:  # kstartup
            source_id = str(item.get("pbanc_sn", item.get("id", "")))
            ann_name = item.get("biz_pbanc_nm", item.get("intg_pbanc_biz_nm", ""))
            target_desc = item.get("지원대상", item.get("aply_trgt_ctnt", ""))
            exclusion_desc = item.get("제외대상", item.get("aply_excl_trgt_ctnt", ""))
            amount_desc = item.get("지원금액", "")
            organization = item.get("pbanc_ntrp_nm", "")
            region = item.get("supt_regin", "")
            apply_start = self._parse_date_safe(item.get("pbanc_rcpt_bgng_dt"))
            apply_end = self._parse_date_safe(item.get("pbanc_rcpt_end_dt"))
            pbanc_url = item.get(
                "detl_pg_url",
                f"https://www.k-startup.go.kr/web/contents/bizpbanc-ongoing.do?schM=view&pbancSn={source_id}",
            )

        # "정보 없음" 정제
        def _clean(val: str) -> str:
            if not val or val in ("정보 없음", "정보없음", "없음"):
                return ""
            return str(val).strip()

        return {
            "ann_name": _clean(ann_name)[:255],
            "source_type": source_type,
            "source_id": source_id,
            "target_desc": _clean(target_desc) or None,
            "exclusion_desc": _clean(exclusion_desc) or None,
            "amount_desc": _clean(amount_desc) or None,
            "apply_start": apply_start,
            "apply_end": apply_end,
            "region": _clean(region)[:100],
            "organization": _clean(organization)[:200],
            "source_url": (_clean(pbanc_url) or "")[:500],
            "doc_s3_key": item.get("_doc_s3_key", ""),
            "form_s3_key": item.get("_form_s3_key", ""),
            "biz_code": "BA000000",
            "use_yn": True,
        }

    # -------------------------------------------------------------------------
    # 4단계: 전처리 (JSONL 변환)
    # -------------------------------------------------------------------------

    def _preprocess(self, crawled_data: dict[str, list[dict]]) -> bool:
        """크롤링 데이터를 announcements.jsonl로 변환합니다."""
        self.logger.info("[4/5] 전처리 시작...")

        try:
            from scripts.preprocessing.preprocess_announcements import (
                AnnouncementPreprocessor,
            )

            # 크롤링 결과를 임시 JSON 파일로 저장
            temp_dir = PROJECT_ROOT / "data" / "origin" / "batch_temp"
            temp_dir.mkdir(parents=True, exist_ok=True)

            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

            for source_name in ("bizinfo", "kstartup"):
                items = crawled_data.get(source_name, [])
                if not items:
                    continue
                temp_file = temp_dir / f"{source_name}_{timestamp}.json"
                with open(temp_file, "w", encoding="utf-8") as f:
                    json.dump(
                        {
                            "source": source_name,
                            "generated_at": timestamp,
                            "total_count": len(items),
                            "data": items,
                        },
                        f,
                        ensure_ascii=False,
                        indent=2,
                    )

            # 전처리 실행
            output_dir = PROJECT_ROOT / "data" / "preprocessed" / "startup_support"
            preprocessor = AnnouncementPreprocessor(
                input_dir=temp_dir,
                output_dir=output_dir,
            )
            stats = preprocessor.run()

            total = (
                stats.get("bizinfo_processed", 0)
                + stats.get("kstartup_processed", 0)
                - stats.get("duplicates_removed", 0)
            )
            self.stats["preprocessed"] = total

            # 임시 파일 정리
            for f in temp_dir.glob("*.json"):
                f.unlink(missing_ok=True)
            try:
                temp_dir.rmdir()
            except OSError:
                pass

            self.logger.info("  전처리 완료: %d건 JSONL 생성", total)
            return True

        except Exception as e:
            self.logger.error("전처리 실패: %s", e)
            _send_email_notification(
                subject="[Bizi 배치] 전처리 실패",
                body=f"JSONL 전처리 단계에서 오류가 발생했습니다.\n\n{_safe_error_message(e)}",
                logger=self.logger,
            )
            return False

    # -------------------------------------------------------------------------
    # 5단계: VectorDB 갱신
    # -------------------------------------------------------------------------

    def _update_vectordb(self) -> bool:
        """VectorDB에 공고 문서를 upsert하고 마감 공고를 관리합니다."""
        self.logger.info("[5/5] VectorDB 갱신 시작...")

        if self.dry_run:
            self.logger.info("  [DRY RUN] VectorDB 변경 건너뜀")
            return True

        try:
            from scripts.vectordb.builder import VectorDBBuilder

            builder = VectorDBBuilder()
            result = builder.update_announcements(domain="startup_funding")

            self.stats["vectordb"]["upserted"] = result["upserted"]
            self.stats["vectordb"]["newly_closed"] = result["newly_closed"]
            self.stats["vectordb"]["removed"] = result["removed"]

            self.logger.info(
                "  VectorDB 갱신 완료: upsert %d건, 마감표시 %d건, 삭제 %d건",
                result["upserted"],
                result["newly_closed"],
                result["removed"],
            )
            return True

        except Exception as e:
            self.logger.error("VectorDB 갱신 실패: %s", e)
            _send_email_notification(
                subject="[Bizi 배치] VectorDB 갱신 실패",
                body=f"VectorDB 갱신 단계에서 오류가 발생했습니다.\n\n{_safe_error_message(e)}",
                logger=self.logger,
            )
            return False

    # -------------------------------------------------------------------------
    # 결과 리포트
    # -------------------------------------------------------------------------

    def _report(self) -> None:
        """실행 결과를 로깅하고 알림을 보냅니다."""
        elapsed = time.time() - self.start_time

        self.logger.info("")
        self.logger.info("=" * 60)
        self.logger.info("배치 실행 완료 (%.1f초)", elapsed)
        self.logger.info("=" * 60)
        self.logger.info(
            "  크롤링: 기업마당 %d건, K-Startup %d건",
            self.stats["crawled"]["bizinfo"],
            self.stats["crawled"]["kstartup"],
        )
        self.logger.info(
            "  S3 업로드: 공고문 %d건, 신청양식 %d건, 오류 %d건",
            self.stats["s3_upload"]["docs"],
            self.stats["s3_upload"]["forms"],
            self.stats["s3_upload"]["errors"],
        )
        self.logger.info(
            "  DB 동기화: 추가 %d건, 갱신 %d건, 마감 %d건",
            self.stats["db_sync"]["inserted"],
            self.stats["db_sync"]["updated"],
            self.stats["db_sync"]["deactivated"],
        )
        self.logger.info("  전처리: %d건 JSONL", self.stats["preprocessed"])
        self.logger.info(
            "  VectorDB: upsert %d건, 마감표시 %d건, 삭제 %d건",
            self.stats["vectordb"]["upserted"],
            self.stats["vectordb"]["newly_closed"],
            self.stats["vectordb"]["removed"],
        )
        self.logger.info("=" * 60)

        # Email 알림
        total_crawled = (
            self.stats["crawled"]["bizinfo"] + self.stats["crawled"]["kstartup"]
        )
        _send_email_notification(
            subject="[Bizi 배치] 공고 갱신 완료",
            body=(
                f"공고 갱신 배치가 완료되었습니다.\n\n"
                f"크롤링: {total_crawled}건 "
                f"(기업마당 {self.stats['crawled']['bizinfo']}건, "
                f"K-Startup {self.stats['crawled']['kstartup']}건)\n"
                f"S3 업로드: 공고문 {self.stats['s3_upload']['docs']}건, "
                f"신청양식 {self.stats['s3_upload']['forms']}건\n"
                f"DB 동기화: 추가 +{self.stats['db_sync']['inserted']}, "
                f"갱신 {self.stats['db_sync']['updated']}, "
                f"마감 {self.stats['db_sync']['deactivated']}\n"
                f"VectorDB: upsert {self.stats['vectordb']['upserted']}건, "
                f"마감표시 {self.stats['vectordb']['newly_closed']}건, "
                f"삭제 {self.stats['vectordb']['removed']}건\n"
                f"소요시간: {elapsed:.0f}초"
            ),
            logger=self.logger,
        )


# =============================================================================
# CLI 진입점
# =============================================================================


def main() -> int:
    """CLI 진입점."""
    parser = argparse.ArgumentParser(
        description="지원사업 공고 일일 배치 갱신 스크립트"
    )
    parser.add_argument(
        "--count",
        "-c",
        type=int,
        default=0,
        help="크롤링할 공고 수 (기본: 0=전체)",
    )
    parser.add_argument(
        "--skip-vectordb",
        action="store_true",
        help="VectorDB 갱신 건너뛰기",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="실제 DB/VectorDB 변경 없이 시뮬레이션",
    )
    parser.add_argument(
        "--verbose",
        "-v",
        action="store_true",
        help="상세 로깅 활성화",
    )
    args = parser.parse_args()

    updater = AnnouncementBatchUpdater(
        count=args.count,
        skip_vectordb=args.skip_vectordb,
        dry_run=args.dry_run,
        verbose=args.verbose,
    )
    return updater.run()


if __name__ == "__main__":
    sys.exit(main())
