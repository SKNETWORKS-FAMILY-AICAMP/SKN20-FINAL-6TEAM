"""S3 파일 업로드 헬퍼.

공고문/신청양식 파일을 S3에 업로드하고, S3 키를 반환합니다.

S3 키 구조:
    announcements/{source_type}/{source_id}/doc{ext}       ← 공고문
    announcements/{source_type}/{source_id}/form{ext}      ← 신청양식
    logs/{service}/{YYYY}/{MM}/{DD}/{filename}              ← 로그 아카이브
"""

from datetime import datetime
from pathlib import Path

import boto3


class S3Uploader:
    """S3 파일 업로더."""

    CONTENT_TYPE_MAP = {
        ".pdf": "application/pdf",
        ".hwp": "application/x-hwp",
        ".hwpx": "application/x-hwpx",
        ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        ".xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        ".pptx": "application/vnd.openxmlformats-officedocument.presentationml.presentation",
        ".zip": "application/zip",
    }

    def __init__(self, bucket: str, region: str = "ap-northeast-2", endpoint_url: str | None = None):
        self.client = boto3.client("s3", region_name=region, endpoint_url=endpoint_url)
        self.bucket = bucket

    def upload_file(self, file_path: Path, s3_key: str) -> str:
        """로컬 파일을 S3에 업로드하고 키를 반환합니다."""
        content_type = self._detect_content_type(file_path)
        self.client.upload_file(
            str(file_path),
            self.bucket,
            s3_key,
            ExtraArgs={"ContentType": content_type},
        )
        return s3_key

    def generate_key(
        self,
        source_type: str,
        source_id: str,
        category: str,
        filename: str,
    ) -> str:
        """S3 키를 생성합니다.

        Args:
            source_type: "bizinfo" 또는 "kstartup"
            source_id: 공고 ID
            category: "doc" (공고문) 또는 "form" (신청양식)
            filename: 원본 파일명 (확장자 추출용)

        Returns:
            예: announcements/bizinfo/12345/doc.pdf
        """
        ext = Path(filename).suffix or ".bin"
        return f"announcements/{source_type}/{source_id}/{category}{ext}"

    def generate_log_key(
        self,
        service: str,
        filename: str,
        date: datetime | None = None,
    ) -> str:
        """S3 로그 키를 생성합니다.

        Args:
            service: 서비스명 ("backend", "rag", "nginx", "batch")
            filename: 로그 파일명 (예: backend.log.1)
            date: 파일 날짜 (None이면 현재 시각)

        Returns:
            예: logs/backend/2026/02/25/backend.log.1
        """
        if date is None:
            date = datetime.now()
        return f"logs/{service}/{date.strftime('%Y/%m/%d')}/{filename}"

    def upload_log_file(
        self,
        file_path: Path,
        service: str,
        date: datetime | None = None,
    ) -> str:
        """로그 파일을 S3에 업로드하고 S3 키를 반환합니다."""
        s3_key = self.generate_log_key(service, file_path.name, date)
        self.client.upload_file(
            str(file_path),
            self.bucket,
            s3_key,
            ExtraArgs={"ContentType": "text/plain; charset=utf-8"},
        )
        return s3_key

    def _detect_content_type(self, file_path: Path) -> str:
        """파일 확장자로 Content-Type을 추론합니다."""
        return self.CONTENT_TYPE_MAP.get(
            file_path.suffix.lower(), "application/octet-stream"
        )
