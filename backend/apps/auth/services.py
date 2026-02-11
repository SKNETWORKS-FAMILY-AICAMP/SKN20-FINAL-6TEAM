from google.oauth2 import id_token
from google.auth.transport import requests
from config.settings import settings
from fastapi import HTTPException, status

def verify_google_token(token: str) -> dict:
    """
    Google ID Token 검증
    """
    try:
        # ID 토큰 검증
        id_info = id_token.verify_oauth2_token(
            token, requests.Request(), settings.GOOGLE_CLIENT_ID
        )

        # issuer 확인
        if id_info['iss'] not in ['accounts.google.com', 'https://accounts.google.com']:
            raise ValueError('Wrong issuer.')

        return id_info
    except ValueError as e:
        # 유효하지 않은 토큰
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Invalid Google token: {str(e)}",
            headers={"WWW-Authenticate": "Bearer"},
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Token verification failed: {str(e)}"
        )
