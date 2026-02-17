"""관리자 서비스."""

import logging
import os
import time

import httpx
from sqlalchemy import select, func, and_, or_, text
from sqlalchemy.orm import Session
from datetime import datetime

logger = logging.getLogger(__name__)

from apps.common.models import Code, History, User
from apps.admin.schemas import (
    HistoryListItem,
    HistoryListResponse,
    EvaluationStats,
    HistoryFilterParams,
    ServiceStatus,
    ServerStatusResponse,
)
from apps.histories.schemas import HistoryDetailResponse, EvaluationData

_START_TIME = time.time()

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
