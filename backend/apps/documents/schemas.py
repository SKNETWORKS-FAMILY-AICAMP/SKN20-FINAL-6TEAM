from datetime import datetime
from pydantic import BaseModel, ConfigDict, Field


class DocumentCreate(BaseModel):
    """문서 메타데이터 저장 요청 (RAG 서비스에서 호출)."""

    user_id: int | None = None
    company_id: int | None = None
    doc_type_id: str = Field(..., max_length=50)
    file_name: str = Field(..., max_length=255)
    file_path: str = Field(default="", max_length=500)
    s3_key: str = Field(..., max_length=500)
    version: int = Field(default=1, ge=1)
    parent_file_id: int | None = None
    metadata: dict | None = None


class DocumentResponse(BaseModel):
    """문서 메타데이터 응답."""

    model_config = ConfigDict(from_attributes=True)

    file_id: int
    user_id: int | None = None
    company_id: int | None = None
    doc_type_id: str | None = None
    file_name: str
    file_path: str | None = None
    s3_key: str | None = Field(default=None, exclude=True)
    version: int = 1
    parent_file_id: int | None = None
    file_metadata: dict | None = None
    create_date: datetime | None = None
    update_date: datetime | None = None


class DocumentListResponse(BaseModel):
    """문서 목록 응답."""

    items: list[DocumentResponse]
    total: int
