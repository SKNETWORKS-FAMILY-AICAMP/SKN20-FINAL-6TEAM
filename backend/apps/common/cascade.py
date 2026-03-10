"""기업/사용자 연관 데이터 소프트 삭제 헬퍼."""

from sqlalchemy import select, update
from sqlalchemy.orm import Session

from apps.common.models import Company, File, History, Schedule


def soft_delete_company_children(db: Session, company_id: int) -> None:
    """기업에 속한 Schedule, File을 벌크 소프트 삭제합니다.

    Args:
        db: SQLAlchemy 세션
        company_id: 대상 기업 ID
    """
    db.execute(
        update(Schedule)
        .where(Schedule.company_id == company_id, Schedule.use_yn.is_(True))
        .values(use_yn=False)
        .execution_options(synchronize_session=False)
    )
    db.execute(
        update(File)
        .where(File.company_id == company_id, File.use_yn.is_(True))
        .values(use_yn=False)
        .execution_options(synchronize_session=False)
    )


def soft_delete_company_children_batch(db: Session, company_ids: list[int]) -> None:
    """여러 기업에 속한 Schedule, File을 배치 소프트 삭제합니다.

    Args:
        db: SQLAlchemy 세션
        company_ids: 대상 기업 ID 리스트
    """
    db.execute(
        update(Schedule)
        .where(Schedule.company_id.in_(company_ids), Schedule.use_yn.is_(True))
        .values(use_yn=False)
        .execution_options(synchronize_session=False)
    )
    db.execute(
        update(File)
        .where(File.company_id.in_(company_ids), File.use_yn.is_(True))
        .values(use_yn=False)
        .execution_options(synchronize_session=False)
    )


def soft_delete_user_cascade(db: Session, user_id: int) -> None:
    """사용자의 모든 연관 데이터를 소프트 삭제합니다 (회원 탈퇴용).

    CompanyService를 우회하여 벌크 처리합니다 (성능: N개 기업에 대한
    개별 SELECT+검증 없이 2~4회 UPDATE로 완료).

    Args:
        db: SQLAlchemy 세션
        user_id: 대상 사용자 ID
    """
    # 1. 사용자의 활성 기업 ID 수집
    company_ids = list(
        db.execute(
            select(Company.company_id).where(
                Company.user_id == user_id, Company.use_yn.is_(True)
            )
        ).scalars()
    )

    # 2. 기업의 자식(Schedule, File) + 기업 자체 소프트 삭제
    if company_ids:
        soft_delete_company_children_batch(db, company_ids)
        db.execute(
            update(Company)
            .where(Company.company_id.in_(company_ids), Company.use_yn.is_(True))
            .values(use_yn=False)
            .execution_options(synchronize_session=False)
        )

    # 3. 상담 이력 소프트 삭제
    db.execute(
        update(History)
        .where(History.user_id == user_id, History.use_yn.is_(True))
        .values(use_yn=False)
        .execution_options(synchronize_session=False)
    )

    # 4. 사용자 직접 소유 파일 소프트 삭제 (기업 소속 파일은 위에서 처리 완료)
    db.execute(
        update(File)
        .where(File.user_id == user_id, File.use_yn.is_(True))
        .values(use_yn=False)
        .execution_options(synchronize_session=False)
    )
