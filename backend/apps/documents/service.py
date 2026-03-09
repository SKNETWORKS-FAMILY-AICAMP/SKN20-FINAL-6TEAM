import logging

from sqlalchemy import select, func
from sqlalchemy.orm import Session

from apps.common.models import File
from .schemas import DocumentCreate

logger = logging.getLogger(__name__)


class DocumentService:
    def __init__(self, db: Session) -> None:
        self.db = db

    def save_document(self, data: DocumentCreate) -> File:
        """문서 메타데이터를 저장합니다."""
        version = data.version
        if data.parent_file_id:
            parent = self.db.get(File, data.parent_file_id)
            if parent:
                version = parent.version + 1

        doc = File(
            user_id=data.user_id,
            company_id=data.company_id,
            doc_type_id=data.doc_type_id,
            file_name=data.file_name,
            file_path=data.file_path,
            s3_key=data.s3_key,
            version=version,
            parent_file_id=data.parent_file_id,
            file_metadata=data.metadata,
        )
        self.db.add(doc)
        self.db.commit()
        self.db.refresh(doc)
        return doc

    def get_document(self, file_id: int) -> File | None:
        """문서 단건 조회."""
        return self.db.execute(
            select(File).where(
                File.file_id == file_id,
                File.use_yn == True,
            )
        ).scalar_one_or_none()

    def list_by_user(self, user_id: int, offset: int = 0, limit: int = 50) -> tuple[list[File], int]:
        """사용자의 문서 목록 조회."""
        base = select(File).where(
            File.user_id == user_id,
            File.use_yn == True,
        )
        total = self.db.execute(
            select(func.count()).select_from(base.subquery())
        ).scalar_one()

        items = self.db.execute(
            base.order_by(File.create_date.desc()).offset(offset).limit(limit)
        ).scalars().all()

        return list(items), total

    def soft_delete(self, file_id: int, user_id: int) -> bool:
        """문서 소프트 삭제 (use_yn=False)."""
        doc = self.db.execute(
            select(File).where(
                File.file_id == file_id,
                File.user_id == user_id,
                File.use_yn == True,
            )
        ).scalar_one_or_none()

        if not doc:
            return False

        doc.use_yn = False
        self.db.commit()
        return True
