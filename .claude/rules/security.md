# Security Rules

## API 키 및 비밀 정보

### 하드코딩 금지 (CRITICAL)
- API 키, 비밀번호, 토큰을 코드에 직접 작성 금지
- 환경 변수(.env) 또는 시크릿 매니저 사용

```python
# CRITICAL - 절대 금지
OPENAI_API_KEY = "sk-xxx..."  # 절대 금지!

# Good
import os
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
```

### .env 파일 관리
- `.env`는 반드시 `.gitignore`에 포함
- `.env.example`에 필요한 키 목록만 기재 (값은 비워두기)

---

## SQL 인젝션 방지

### Raw SQL 금지
- SQLAlchemy ORM 사용 권장
- 불가피하게 raw SQL 사용 시 파라미터 바인딩 필수

```python
# CRITICAL - 절대 금지
query = f"SELECT * FROM users WHERE id = {user_id}"

# Good - SQLAlchemy ORM
user = session.query(User).filter(User.id == user_id).first()

# Good - 파라미터 바인딩
query = text("SELECT * FROM users WHERE id = :user_id")
result = session.execute(query, {"user_id": user_id})
```

---

## 입력 검증

### 시스템 경계에서 검증 필수
- API 엔드포인트 입력
- 외부 API 응답
- 사용자 업로드 파일

```python
from pydantic import BaseModel, EmailStr, Field

class UserCreateRequest(BaseModel):
    email: EmailStr  # 이메일 형식 자동 검증
    password: str = Field(..., min_length=8, max_length=128)
    name: str = Field(..., min_length=1, max_length=100)
```

### XSS 방지 (Frontend)
- 사용자 입력을 HTML에 직접 삽입 금지
- React의 기본 이스케이핑 기능 활용
- innerHTML 직접 조작 금지
- 필요시 DOMPurify 같은 sanitize 라이브러리 사용

---

## 인증 및 인가

### JWT 토큰 관리
- Access Token: 짧은 만료 시간 (15분~1시간)
- Refresh Token: 긴 만료 시간 (7일~30일)
- HttpOnly 쿠키 또는 secure storage 사용

### 권한 검증
- 모든 보호된 엔드포인트에서 권한 확인
- Depends() 의존성 주입 사용

```python
from fastapi import Depends, HTTPException
from apps.auth.deps import get_current_user

@router.get("/protected")
async def protected_endpoint(
    current_user: User = Depends(get_current_user)
):
    if not current_user.is_admin:
        raise HTTPException(status_code=403, detail="관리자만 접근 가능")
```

---

## 파일 업로드 보안

### 검증 항목
- 파일 크기 제한
- 허용된 MIME 타입만
- 파일명 sanitize
- 저장 경로는 웹루트 외부

```python
ALLOWED_EXTENSIONS = {".pdf", ".docx", ".xlsx"}
MAX_FILE_SIZE = 10 * 1024 * 1024  # 10MB

def validate_file(file: UploadFile) -> bool:
    # 확장자 검증
    ext = Path(file.filename).suffix.lower()
    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(400, "허용되지 않은 파일 형식")

    # 크기 검증
    file.file.seek(0, 2)
    size = file.file.tell()
    file.file.seek(0)
    if size > MAX_FILE_SIZE:
        raise HTTPException(400, "파일 크기 초과")
```

---

## 로깅 보안

### 민감 정보 로깅 금지
- 비밀번호, 토큰, 개인정보 로그 출력 금지
- 필요시 마스킹 처리

```python
# Bad
logger.info(f"User login: {email}, password: {password}")

# Good
logger.info(f"User login: {email}")
```

---

## CORS 설정

### 프로덕션 환경
- `allow_origins`에 와일드카드(*) 사용 금지
- 허용된 도메인만 명시

```python
# Development
allow_origins=["http://localhost:5173"]

# Production
allow_origins=["https://bizi.example.com"]
```

---

## 의존성 보안

### 정기 점검
- `pip audit` 또는 `npm audit` 정기 실행
- 알려진 취약점이 있는 패키지 업데이트
