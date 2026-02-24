"""AWS SES 이메일 알림 서비스.

EC2 Instance Role의 IAM 권한을 사용하여 자격 증명 없이 인증합니다.
ALERT_EMAIL_TO 또는 SES_FROM이 미설정이면 발송을 건너뜁니다.
"""

import logging

logger = logging.getLogger(__name__)


class EmailService:
    """AWS SES 기반 이메일 알림 서비스 (싱글톤)."""

    def __init__(self) -> None:
        self._client = None

    def _get_client(self):
        """boto3 SES 클라이언트를 지연 생성합니다."""
        if self._client is None:
            try:
                import boto3
                from config.settings import settings
                self._client = boto3.client("ses", region_name=settings.AWS_REGION)
            except ImportError:
                logger.error(
                    "boto3 미설치 — 이메일 알림 비활성화. "
                    "'pip install boto3' 로 설치하세요."
                )
        return self._client

    def send(self, subject: str, body_html: str) -> bool:
        """이메일을 발송합니다.

        Args:
            subject: 이메일 제목 (접두사 '[Bizi Alert]' 자동 추가)
            body_html: HTML 형식 본문

        Returns:
            발송 성공 여부
        """
        from config.settings import settings

        if not settings.ALERT_EMAIL_TO or not settings.SES_FROM:
            logger.debug("ALERT_EMAIL_TO 또는 SES_FROM 미설정 — 이메일 발송 건너뜀")
            return False

        client = self._get_client()
        if client is None:
            return False

        try:
            client.send_email(
                Source=settings.SES_FROM,
                Destination={"ToAddresses": [settings.ALERT_EMAIL_TO]},
                Message={
                    "Subject": {
                        "Data": f"[Bizi Alert] {subject}",
                        "Charset": "UTF-8",
                    },
                    "Body": {
                        "Html": {"Data": body_html, "Charset": "UTF-8"},
                    },
                },
            )
            logger.info("알림 이메일 발송 완료: %s → %s", subject, settings.ALERT_EMAIL_TO)
            return True
        except Exception as e:
            logger.error("이메일 발송 실패: %s", e)
            return False


email_service = EmailService()
