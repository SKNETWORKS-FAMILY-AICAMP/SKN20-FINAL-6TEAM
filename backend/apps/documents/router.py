import hmac
import logging

from fastapi import APIRouter, Depends, HTTPException, Header, Query, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from config.database import get_db
from config.settings import settings
from apps.common.deps import get_current_user
from apps.common.models import File, User
from .schemas import DocumentCreate, DocumentResponse, DocumentListResponse
from .service import DocumentService
from .s3_utils import generate_presigned_url

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/documents", tags=["documents"])


def get_document_service(db: Session = Depends(get_db)) -> DocumentService:
    return DocumentService(db)


def _verify_api_key(x_api_key: str | None = Header(default=None)) -> None:
    """RAG 서비스에서 호출 시 X-API-Key 검증."""
    if not settings.RAG_API_KEY:
        return
    if not hmac.compare_digest(x_api_key or "", settings.RAG_API_KEY):
        raise HTTPException(status_code=401, detail="Invalid API key")


@router.post("/save", response_model=DocumentResponse, status_code=status.HTTP_201_CREATED)
async def save_document(
    body: DocumentCreate,
    _: None = Depends(_verify_api_key),
    service: DocumentService = Depends(get_document_service),
) -> DocumentResponse:
    """문서 메타데이터 저장 (RAG 서비스에서 호출)."""
    doc = service.save_document(body)
    return DocumentResponse.model_validate(doc)


@router.get("/{file_id}", response_model=DocumentResponse)
async def get_document(
    file_id: int,
    current_user: User = Depends(get_current_user),
    service: DocumentService = Depends(get_document_service),
) -> DocumentResponse:
    """문서 단건 조회."""
    doc = service.get_document(file_id)
    if not doc or doc.user_id != current_user.user_id:
        raise HTTPException(status_code=404, detail="문서를 찾을 수 없습니다.")
    return DocumentResponse.model_validate(doc)


@router.get("/user/{user_id}", response_model=DocumentListResponse)
async def list_user_documents(
    user_id: int,
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=100),
    current_user: User = Depends(get_current_user),
    service: DocumentService = Depends(get_document_service),
) -> DocumentListResponse:
    """사용자 문서 목록 조회."""
    if current_user.user_id != user_id:
        raise HTTPException(status_code=403, detail="접근 권한이 없습니다.")
    items, total = service.list_by_user(user_id, offset, limit)
    return DocumentListResponse(
        items=[DocumentResponse.model_validate(doc) for doc in items],
        total=total,
    )


@router.get("/{file_id}/download")
async def download_document(
    file_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict[str, str]:
    """파일 presigned URL 반환."""
    result = db.execute(
        select(File).where(File.file_id == file_id, File.use_yn == True)
    )
    file = result.scalar_one_or_none()
    if not file:
        raise HTTPException(status_code=404, detail="파일을 찾을 수 없습니다")
    if file.user_id != current_user.user_id:
        raise HTTPException(status_code=403, detail="접근 권한이 없습니다")

    download_url = generate_presigned_url(file.s3_key)
    if not download_url:
        raise HTTPException(status_code=503, detail="다운로드 URL 생성에 실패했습니다")

    return {"download_url": download_url}


@router.delete("/{file_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_document(
    file_id: int,
    current_user: User = Depends(get_current_user),
    service: DocumentService = Depends(get_document_service),
) -> None:
    """문서 소프트 삭제."""
    if not service.soft_delete(file_id, current_user.user_id):
        raise HTTPException(status_code=404, detail="문서를 찾을 수 없습니다.")
