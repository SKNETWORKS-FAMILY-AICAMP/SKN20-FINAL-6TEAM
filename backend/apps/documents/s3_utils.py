import boto3
from botocore.exceptions import ClientError
from config.settings import settings
import logging

logger = logging.getLogger(__name__)


def generate_presigned_url(s3_key: str, expires_in: int = 3600) -> str | None:
    """S3 오브젝트에 대한 presigned URL 생성."""
    if not s3_key or not settings.AWS_S3_BUCKET:
        return None
    try:
        s3_client = boto3.client("s3")
        url = s3_client.generate_presigned_url(
            "get_object",
            Params={"Bucket": settings.AWS_S3_BUCKET, "Key": s3_key},
            ExpiresIn=expires_in,
        )
        return url
    except ClientError as e:
        logger.error(f"Presigned URL 생성 실패: {e}")
        return None
