"""S3 클라이언트 모듈.

문서 파일 업로드/다운로드를 처리합니다.
"""

import logging
import uuid
from datetime import datetime

import boto3
from botocore.exceptions import ClientError

from utils.config import get_settings

logger = logging.getLogger(__name__)


class S3Client:
    """AWS S3 문서 저장소 클라이언트."""

    def __init__(self) -> None:
        settings = get_settings()
        self.bucket = settings.aws_s3_bucket
        self.forms_prefix = settings.aws_s3_application_forms_prefix
        self.s3 = boto3.client("s3")

    def _generate_key(self, user_id: int, document_type: str, ext: str) -> str:
        """S3 오브젝트 키를 생성합니다."""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        short_uuid = uuid.uuid4().hex[:6]
        return f"documents/{user_id}/{document_type}/{timestamp}_{short_uuid}.{ext}"

    def upload_document(
        self,
        file_content: bytes,
        key: str,
        content_type: str = "application/octet-stream",
    ) -> str:
        """문서를 S3에 업로드합니다.

        Returns:
            s3://bucket/key 형태의 URI
        """
        try:
            self.s3.put_object(
                Bucket=self.bucket,
                Key=key,
                Body=file_content,
                ContentType=content_type,
            )
            logger.info("S3 업로드 완료: s3://%s/%s", self.bucket, key)
            return f"s3://{self.bucket}/{key}"
        except ClientError:
            logger.error("S3 업로드 실패: %s", key, exc_info=True)
            raise

    def get_application_form(self, form_key: str) -> bytes:
        """S3에서 신청 양식 파일을 가져옵니다."""
        try:
            response = self.s3.get_object(Bucket=self.bucket, Key=form_key)
            return response["Body"].read()
        except ClientError:
            logger.error("S3 양식 다운로드 실패: %s", form_key, exc_info=True)
            raise

    def list_application_forms(self) -> list[dict[str, str]]:
        """사용 가능한 신청 양식 목록을 조회합니다."""
        prefix = self.forms_prefix
        try:
            response = self.s3.list_objects_v2(Bucket=self.bucket, Prefix=prefix)
            return [
                {"key": obj["Key"], "name": obj["Key"].split("/")[-1]}
                for obj in response.get("Contents", [])
                if not obj["Key"].endswith("/")
            ]
        except ClientError:
            logger.error("S3 양식 목록 조회 실패", exc_info=True)
            return []


# 싱글턴 인스턴스 (lazy init)
_s3_client: S3Client | None = None


def get_s3_client() -> S3Client:
    """S3 클라이언트 싱글턴을 반환합니다."""
    global _s3_client
    if _s3_client is None:
        _s3_client = S3Client()
    return _s3_client
