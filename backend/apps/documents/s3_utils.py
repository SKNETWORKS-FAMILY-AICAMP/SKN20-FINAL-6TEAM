import logging

import boto3
from botocore.exceptions import ClientError

from config.settings import settings

logger = logging.getLogger(__name__)

_s3_client = None


def _get_s3_client():
    global _s3_client
    if _s3_client is None:
        _s3_client = boto3.client("s3")
    return _s3_client


def generate_presigned_url(s3_key: str, expires_in: int = 3600) -> str | None:
    """S3 오브젝트에 대한 presigned URL 생성."""
    if not s3_key or not settings.AWS_S3_BUCKET:
        return None
    try:
        s3_client = _get_s3_client()
        url = s3_client.generate_presigned_url(
            "get_object",
            Params={"Bucket": settings.AWS_S3_BUCKET, "Key": s3_key},
            ExpiresIn=expires_in,
        )
        return url
    except ClientError as e:
        logger.error(f"Presigned URL 생성 실패: {e}")
        return None
