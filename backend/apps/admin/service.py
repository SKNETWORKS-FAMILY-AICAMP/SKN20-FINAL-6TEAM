"""관리자 서비스."""

import asyncio
import logging
import time
from pathlib import Path

import httpx
import psutil
from sqlalchemy import select, func, and_, text
from sqlalchemy.orm import Session
from datetime import datetime

logger = logging.getLogger(__name__)

from apps.common.models import Code, History, JobLog, User
from apps.admin.schemas import (
    HistoryListItem,
    HistoryListResponse,
    EvaluationStats,
    HistoryFilterParams,
    JobLogResponse,
    LogPageResponse,
    MetricsResponse,
    ServiceStatus,
    ServerStatusResponse,
)
from apps.histories.schemas import HistoryDetailResponse, EvaluationData

_START_TIME: float = time.time()

from config.settings import settings as _app_settings

RAG_SERVICE_URL = _app_settings.RAG_SERVICE_URL


class AdminService:
    """관리자 서비스 클래스."""

    def __init__(self, db: Session):
        self.db = db

    async def get_server_status(self) -> ServerStatusResponse:
        """서버 상태를 조회합니다.

        Backend DB ping, RAG 서비스 health check을 수행합니다.

        Returns:
            서버 상태 응답
        """
        services: list[ServiceStatus] = []

        # 1. Database 상태
        db_status = self._check_database()
        services.append(db_status)

        # 2. RAG 서비스 상태
        rag_status = await self._check_rag_service()
        services.append(rag_status)

        # 3. Backend 자체 (응답 가능하면 healthy)
        services.insert(0, ServiceStatus(
            name="backend",
            status="healthy",
            response_time_ms=0,
            details={"version": "1.0.0"},
        ))

        # 전체 상태 결정
        statuses = [s.status for s in services]
        if all(s == "healthy" for s in statuses):
            overall = "healthy"
        elif any(s == "unhealthy" for s in statuses):
            overall = "degraded"
        else:
            overall = "degraded"

        return ServerStatusResponse(
            overall_status=overall,
            services=services,
            uptime_seconds=time.time() - _START_TIME,
            checked_at=datetime.now(),
        )

    def _check_database(self) -> ServiceStatus:
        """DB ping으로 데이터베이스 상태를 확인합니다."""
        try:
            start = time.time()
            self.db.execute(text("SELECT 1"))
            elapsed_ms = (time.time() - start) * 1000
            return ServiceStatus(
                name="database",
                status="healthy",
                response_time_ms=round(elapsed_ms, 2),
            )
        except Exception as e:
            logger.error("Database health check failed: %s", e)
            return ServiceStatus(
                name="database",
                status="unhealthy",
                details={"error": "Service temporarily unavailable"},
            )

    async def _check_rag_service(self) -> ServiceStatus:
        """RAG 서비스 health check을 수행합니다."""
        try:
            start = time.time()
            async with httpx.AsyncClient(timeout=5.0) as client:
                resp = await client.get(f"{RAG_SERVICE_URL}/health")
            elapsed_ms = (time.time() - start) * 1000

            if resp.status_code == 200:
                return ServiceStatus(
                    name="rag",
                    status="healthy",
                    response_time_ms=round(elapsed_ms, 2),
                    details=resp.json() if resp.headers.get("content-type", "").startswith("application/json") else {},
                )
            return ServiceStatus(
                name="rag",
                status="degraded",
                response_time_ms=round(elapsed_ms, 2),
                details={"status_code": resp.status_code},
            )
        except Exception as e:
            logger.error("RAG service health check failed: %s", e)
            return ServiceStatus(
                name="rag",
                status="unhealthy",
                details={"error": "Service temporarily unavailable"},
            )

    def get_histories(
        self,
        page: int = 1,
        page_size: int = 20,
        filters: HistoryFilterParams | None = None,
    ) -> HistoryListResponse:
        """관리자용 상담 이력 목록 조회.

        Args:
            page: 페이지 번호 (1부터 시작)
            page_size: 페이지당 항목 수
            filters: 필터 파라미터

        Returns:
            상담 이력 목록 응답
        """
        # 기본 쿼리 (Code 테이블 JOIN으로 agent_name 조회)
        stmt = (
            select(History, User.google_email, User.username, Code.name.label("agent_name"))
            .join(User, History.user_id == User.user_id)
            .outerjoin(Code, History.agent_code == Code.code)
            .where(History.use_yn == True)
        )

        # 필터 적용
        if filters:
            conditions = []

            if filters.start_date:
                conditions.append(History.create_date >= filters.start_date)
            if filters.end_date:
                conditions.append(History.create_date <= filters.end_date)
            if filters.agent_code:
                conditions.append(History.agent_code == filters.agent_code)
            if filters.user_id:
                conditions.append(History.user_id == filters.user_id)

            # JSON 필드 필터링 (MySQL JSON 함수 사용)
            if filters.domain:
                conditions.append(
                    func.json_contains(
                        History.evaluation_data,
                        f'"{filters.domain}"',
                        "$.domains",
                    )
                )
            if filters.min_score is not None:
                conditions.append(
                    func.json_extract(History.evaluation_data, "$.llm_score")
                    >= filters.min_score
                )
            if filters.max_score is not None:
                conditions.append(
                    func.json_extract(History.evaluation_data, "$.llm_score")
                    <= filters.max_score
                )
            if filters.passed_only is not None:
                conditions.append(
                    func.json_extract(History.evaluation_data, "$.llm_passed")
                    == filters.passed_only
                )

            if conditions:
                stmt = stmt.where(and_(*conditions))

        # 전체 개수 조회
        count_stmt = select(func.count()).select_from(stmt.subquery())
        total = self.db.execute(count_stmt).scalar() or 0

        # 페이징 적용
        offset = (page - 1) * page_size
        stmt = (
            stmt.order_by(History.create_date.desc())
            .offset(offset)
            .limit(page_size)
        )

        # 실행
        results = self.db.execute(stmt).all()

        # 결과 변환
        items = []
        for history, user_email, username, agent_name in results:
            eval_data = history.evaluation_data or {}

            item = HistoryListItem(
                history_id=history.history_id,
                user_id=history.user_id,
                agent_code=history.agent_code,
                agent_name=agent_name,
                question=history.question,
                answer_preview=(
                    history.answer[:200] + "..."
                    if history.answer and len(history.answer) > 200
                    else history.answer
                ),
                create_date=history.create_date,
                faithfulness=eval_data.get("faithfulness"),
                answer_relevancy=eval_data.get("answer_relevancy"),
                context_precision=eval_data.get("context_precision"),
                context_recall=eval_data.get("context_recall"),
                llm_score=eval_data.get("llm_score"),
                llm_passed=eval_data.get("llm_passed"),
                response_time=eval_data.get("response_time"),
                domains=eval_data.get("domains", []),
                user_email=user_email,
                username=username,
            )
            items.append(item)

        total_pages = (total + page_size - 1) // page_size if total > 0 else 1

        return HistoryListResponse(
            items=items,
            total=total,
            page=page,
            page_size=page_size,
            total_pages=total_pages,
        )

    def get_history_detail(self, history_id: int) -> HistoryDetailResponse | None:
        """상담 이력 상세 조회.

        Args:
            history_id: 상담 이력 ID

        Returns:
            상담 이력 상세 응답 또는 None
        """
        stmt = (
            select(History, User.google_email, User.username, Code.name.label("agent_name"))
            .join(User, History.user_id == User.user_id)
            .outerjoin(Code, History.agent_code == Code.code)
            .where(History.history_id == history_id, History.use_yn == True)
        )

        result = self.db.execute(stmt).first()
        if not result:
            return None

        history, user_email, username, agent_name = result
        eval_data = history.evaluation_data

        return HistoryDetailResponse(
            history_id=history.history_id,
            user_id=history.user_id,
            agent_code=history.agent_code,
            agent_name=agent_name,
            question=history.question,
            answer=history.answer,
            parent_history_id=history.parent_history_id,
            evaluation_data=EvaluationData(**eval_data) if eval_data else None,
            create_date=history.create_date,
            update_date=history.update_date,
            user_email=user_email,
            username=username,
        )

    # ─── 모니터링 메서드 ─────────────────────────────────────────

    def get_system_metrics(self) -> MetricsResponse:
        """psutil로 현재 서버 리소스 사용량을 반환합니다.

        Returns:
            CPU/Memory/Disk 수치 응답
        """
        cpu = psutil.cpu_percent(interval=0.5)
        mem = psutil.virtual_memory()
        disk = psutil.disk_usage("/")

        return MetricsResponse(
            cpu_percent=round(cpu, 1),
            memory_percent=round(mem.percent, 1),
            disk_percent=round(disk.percent, 1),
            memory_total_gb=round(mem.total / (1024 ** 3), 2),
            memory_used_gb=round(mem.used / (1024 ** 3), 2),
            disk_total_gb=round(disk.total / (1024 ** 3), 2),
            disk_used_gb=round(disk.used / (1024 ** 3), 2),
            timestamp=datetime.now(),
        )

    def get_scheduler_status(self, limit: int = 50) -> list[JobLogResponse]:
        """최근 스케줄러 작업 실행 이력을 반환합니다.

        Args:
            limit: 최대 반환 건수 (기본 50)

        Returns:
            JobLogResponse 리스트 (최신 순)
        """
        stmt = select(JobLog).order_by(JobLog.started_at.desc()).limit(limit)
        logs = self.db.execute(stmt).scalars().all()
        return [JobLogResponse.model_validate(log) for log in logs]

    def get_log_content(
        self,
        file: str,
        page: int = 1,
        page_size: int = 100,
    ) -> LogPageResponse:
        """지정된 서비스의 로그 파일을 최신 순으로 페이징하여 반환합니다.

        Args:
            file: 로그 파일명 (backend | rag)
            page: 페이지 번호 (1-based, 1=가장 최신)
            page_size: 페이지당 줄 수 (기본 100)

        Returns:
            로그 라인 목록 (최신 순)

        Raises:
            ValueError: 허용되지 않은 파일명
        """
        _ALLOWED = {"backend", "rag"}
        if file not in _ALLOWED:
            raise ValueError(f"허용되지 않은 로그 파일: {file!r}")

        log_path = Path(f"/var/log/app/{file}.log")
        if not log_path.exists():
            return LogPageResponse(
                total_lines=0, page=page, page_size=page_size, lines=[], file=file
            )

        # deque로 최대 10,000줄만 메모리에 유지 (로테이션 파일 기준 적정값)
        from collections import deque
        _MAX_LINES = 10_000
        with log_path.open(errors="replace") as f:
            dq = deque(f, maxlen=_MAX_LINES)
        reversed_lines = [line.rstrip("\n") for line in reversed(dq)]
        total = len(reversed_lines)
        start = (page - 1) * page_size
        page_lines = reversed_lines[start : start + page_size]

        return LogPageResponse(
            total_lines=total,
            page=page,
            page_size=page_size,
            lines=page_lines,
            file=file,
        )

    async def send_resource_alert(
        self, cpu: float, memory: float, disk: float
    ) -> None:
        """리소스 임계치 초과 시 이메일 알림을 발송합니다 (fire-and-forget).

        Args:
            cpu: CPU 사용률 (%)
            memory: 메모리 사용률 (%)
            disk: 디스크 사용률 (%)
        """
        from apps.common.email_service import email_service

        body_html = f"""
        <h2 style="color:#d32f2f;">⚠️ Bizi 서버 리소스 경고</h2>
        <p>다음 리소스가 임계치(90%)를 초과했습니다.</p>
        <table border="1" cellpadding="6" style="border-collapse:collapse;">
          <tr><th>항목</th><th>현재 사용률</th><th>임계치</th></tr>
          <tr><td>CPU</td><td>{cpu:.1f}%</td><td>90%</td></tr>
          <tr><td>메모리</td><td>{memory:.1f}%</td><td>90%</td></tr>
          <tr><td>디스크</td><td>{disk:.1f}%</td><td>90%</td></tr>
        </table>
        <p style="color:#555;">측정 시각: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</p>
        <p>즉시 서버 상태를 확인하세요.</p>
        """
        await asyncio.to_thread(
            email_service.send, "서버 리소스 임계치 초과 경고", body_html
        )

    async def send_job_failure_alert(self, job_name: str, error_msg: str) -> None:
        """스케줄러 작업 실패 시 이메일 알림을 발송합니다 (fire-and-forget).

        Args:
            job_name: 실패한 작업 이름
            error_msg: 오류 메시지
        """
        from apps.common.email_service import email_service

        body_html = f"""
        <h2 style="color:#d32f2f;">❌ Bizi 스케줄러 작업 실패</h2>
        <table border="1" cellpadding="6" style="border-collapse:collapse;">
          <tr><th>작업명</th><td>{job_name}</td></tr>
          <tr><th>오류 메시지</th><td style="color:#d32f2f;">{error_msg}</td></tr>
          <tr><th>발생 시각</th><td>{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</td></tr>
        </table>
        <p>로그를 확인하여 원인을 분석하세요.</p>
        """
        await asyncio.to_thread(
            email_service.send, f"스케줄러 작업 실패: {job_name}", body_html
        )

    def get_evaluation_stats(
        self,
        start_date: datetime | None = None,
        end_date: datetime | None = None,
    ) -> EvaluationStats:
        """평가 통계 조회.

        Args:
            start_date: 시작일
            end_date: 종료일

        Returns:
            평가 통계
        """
        # 기본 조건
        conditions = [History.use_yn == True]
        if start_date:
            conditions.append(History.create_date >= start_date)
        if end_date:
            conditions.append(History.create_date <= end_date)

        base_where = and_(*conditions)

        # 전체 상담 수
        total_count = self.db.execute(
            select(func.count()).select_from(History).where(base_where)
        ).scalar() or 0

        # 평가된 상담 수 (evaluation_data가 NULL이 아닌 경우)
        evaluated_count = self.db.execute(
            select(func.count())
            .select_from(History)
            .where(base_where, History.evaluation_data.isnot(None))
        ).scalar() or 0

        # LLM 평가 통과/실패 수
        passed_count = self.db.execute(
            select(func.count())
            .select_from(History)
            .where(
                base_where,
                func.json_extract(History.evaluation_data, "$.llm_passed") == True,
            )
        ).scalar() or 0

        failed_count = self.db.execute(
            select(func.count())
            .select_from(History)
            .where(
                base_where,
                func.json_extract(History.evaluation_data, "$.llm_passed") == False,
            )
        ).scalar() or 0

        # 평균 점수 계산
        avg_faithfulness = self.db.execute(
            select(
                func.avg(
                    func.json_extract(History.evaluation_data, "$.faithfulness")
                )
            )
            .select_from(History)
            .where(base_where, History.evaluation_data.isnot(None))
        ).scalar()

        avg_answer_relevancy = self.db.execute(
            select(
                func.avg(
                    func.json_extract(History.evaluation_data, "$.answer_relevancy")
                )
            )
            .select_from(History)
            .where(base_where, History.evaluation_data.isnot(None))
        ).scalar()

        avg_llm_score = self.db.execute(
            select(
                func.avg(func.json_extract(History.evaluation_data, "$.llm_score"))
            )
            .select_from(History)
            .where(base_where, History.evaluation_data.isnot(None))
        ).scalar()

        # 도메인별 통계 (간단 구현: 전체 조회 후 집계)
        domain_counts: dict[str, int] = {}
        histories_with_domains = self.db.execute(
            select(History.evaluation_data)
            .where(base_where, History.evaluation_data.isnot(None))
        ).scalars().all()

        for eval_data in histories_with_domains:
            if eval_data and "domains" in eval_data:
                for domain in eval_data["domains"]:
                    domain_counts[domain] = domain_counts.get(domain, 0) + 1

        return EvaluationStats(
            total_count=total_count,
            evaluated_count=evaluated_count,
            passed_count=passed_count,
            failed_count=failed_count,
            avg_faithfulness=float(avg_faithfulness) if avg_faithfulness else None,
            avg_answer_relevancy=float(avg_answer_relevancy) if avg_answer_relevancy else None,
            avg_llm_score=float(avg_llm_score) if avg_llm_score else None,
            domain_counts=domain_counts,
        )
