import logging

from google.oauth2 import id_token
from google.auth.transport import requests
from config.settings import settings
from fastapi import HTTPException, status

logger = logging.getLogger("auth")


def verify_google_token(token: str) -> dict:
    """Google ID Token을 검증합니다.

    Args:
        token: Google ID Token 문자열

    Returns:
        검증된 토큰 정보 딕셔너리

    Raises:
        HTTPException: 토큰 검증 실패 시
    """
    try:
        id_info = id_token.verify_oauth2_token(
            token, requests.Request(), settings.GOOGLE_CLIENT_ID
        )

        if id_info['iss'] not in ['accounts.google.com', 'https://accounts.google.com']:
            raise ValueError('Wrong issuer.')

        return id_info
    except ValueError as e:
        logger.warning("Google token validation failed: %s", e)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication failed",
            headers={"WWW-Authenticate": "Bearer"},
        )
    except Exception as e:
        logger.error("Google token verification error: %s", e, exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Authentication failed",
        )
