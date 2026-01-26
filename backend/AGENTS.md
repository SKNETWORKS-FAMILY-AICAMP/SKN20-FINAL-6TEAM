# Backend 개발 가이드 (AI 에이전트용)

> **이 문서는 다른 AI 에이전트가 백엔드 개발을 지원하기 위한 자기 완결적 가이드입니다.**
> Claude Code는 [CLAUDE.md](./CLAUDE.md)를 참조하세요.

## 개요
BizMate의 백엔드는 FastAPI를 사용하며, Google OAuth2 인증과 SQLAlchemy ORM을 사용합니다.
RAG 서비스와 분리되어 사용자 인증, 데이터 관리를 담당합니다.

## 기술 스택
- Python 3.10+
- FastAPI
- SQLAlchemy 2.0
- MySQL 8.0
- Google OAuth2
- JWT (PyJWT)

## 프로젝트 구조
```
backend/
├── main.py               # FastAPI 진입점
├── database.sql          # DB 스키마 (final_test)
├── requirements.txt
├── Dockerfile
│
├── config/
│   ├── __init__.py
│   ├── settings.py       # 환경 설정 (Pydantic Settings)
│   └── database.py       # SQLAlchemy 연결
│
└── apps/
    ├── auth/             # Google OAuth2 인증
    │   ├── __init__.py
    │   ├── router.py     # /auth/* 라우터
    │   ├── service.py    # 인증 비즈니스 로직
    │   └── schemas.py    # Pydantic 스키마
    │
    ├── users/            # 사용자 관리
    │   ├── __init__.py
    │   ├── router.py     # /users/* 라우터
    │   ├── service.py    # 사용자 비즈니스 로직
    │   └── schemas.py
    │
    ├── companies/        # 기업 프로필
    │   ├── __init__.py
    │   ├── router.py     # /companies/* 라우터
    │   ├── service.py    # 기업 비즈니스 로직
    │   └── schemas.py
    │
    ├── histories/        # 상담 이력
    │   ├── __init__.py
    │   ├── router.py     # /histories/* 라우터
    │   ├── service.py
    │   └── schemas.py
    │
    ├── schedules/        # 일정 관리
    │   ├── __init__.py
    │   ├── router.py     # /schedules/* 라우터
    │   ├── service.py
    │   └── schemas.py
    │
    └── common/           # 공통 모듈
        ├── __init__.py
        ├── models.py     # SQLAlchemy 모델 (전체)
        └── deps.py       # 의존성 (get_current_user 등)
```

## 코드 작성 규칙

### 1. 라우터
```python
# apps/{기능}/router.py
from fastapi import APIRouter, Depends
from apps.common.deps import get_current_user

router = APIRouter(prefix="/users", tags=["users"])

@router.get("/me")
async def get_me(current_user = Depends(get_current_user)):
    return current_user
```

### 2. 비즈니스 로직
```python
# apps/{기능}/service.py
from sqlalchemy.orm import Session
from apps.common.models import User

class UserService:
    def __init__(self, db: Session):
        self.db = db

    def get_user_by_email(self, email: str) -> User | None:
        return self.db.query(User).filter(User.google_email == email).first()
```

### 3. SQLAlchemy 모델
```python
# apps/common/models.py
from sqlalchemy import Column, Integer, String, ForeignKey, DateTime, Text
from sqlalchemy.orm import relationship
from datetime import datetime
from config.database import Base

class User(Base):
    __tablename__ = "user"

    user_id = Column(Integer, primary_key=True, autoincrement=True)
    google_email = Column(String(255), unique=True, nullable=False)
    username = Column(String(100), nullable=False)
    type_code = Column(String(4), ForeignKey("code.code"), default="U001")
    created_at = Column(DateTime, default=datetime.now)
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now)

    # Relationships
    companies = relationship("Company", back_populates="user")
    histories = relationship("History", back_populates="user")

class Company(Base):
    __tablename__ = "company"

    company_id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("user.user_id"), nullable=False)
    com_name = Column(String(200), nullable=False)
    biz_num = Column(String(20), unique=True)
    biz_code = Column(String(4), ForeignKey("code.code"))
    created_at = Column(DateTime, default=datetime.now)

    # Relationships
    user = relationship("User", back_populates="companies")
```

### 4. Pydantic 스키마
```python
# apps/{기능}/schemas.py
from pydantic import BaseModel

class UserCreate(BaseModel):
    google_email: str
    username: str

class UserResponse(BaseModel):
    user_id: int
    google_email: str
    username: str

    class Config:
        from_attributes = True
```

## 데이터베이스 스키마

### 테이블 구조 (database.sql 참조)
| 테이블 | 설명 | 주요 컬럼 |
|--------|------|----------|
| code | 코드 마스터 | code_id, name, main_code, code |
| user | 사용자 | user_id, google_email, username, type_code |
| company | 기업 | company_id, user_id, com_name, biz_num, biz_code |
| history | 상담 이력 | history_id, user_id, agent_code, question, answer |
| file | 파일 | file_id, file_name, file_path |
| announce | 공고 | announce_id, ann_name, biz_code, host_gov_code |
| schedule | 일정 | schedule_id, company_id, schedule_name, start_date |

### 코드 테이블 (main_code)
- `U`: 사용자 유형 (U001: 예비창업자, U002: 사업자)
- `B`: 업종 코드 (B001: 음식점업, B002: 소매업, ...)
- `A`: 에이전트 코드 (A001: 창업, A002: 세무, ...)
- `H`: 주관기관 코드 (H001: 중소벤처기업부, ...)

## 주요 API

### 인증 (auth)
| Method | Endpoint | 설명 | 요구사항 |
|--------|----------|------|----------|
| GET | `/auth/google` | Google OAuth 로그인 시작 | REQ-UM-012 |
| GET | `/auth/google/callback` | OAuth 콜백 처리 | REQ-UM-012 |
| POST | `/auth/logout` | 로그아웃 | REQ-UM-013 |
| POST | `/auth/refresh` | 토큰 갱신 | REQ-UM-014 |

### 사용자 (users)
| Method | Endpoint | 설명 | 요구사항 |
|--------|----------|------|----------|
| GET | `/users/me` | 내 정보 조회 | REQ-UM-031 |
| PUT | `/users/me` | 내 정보 수정 | REQ-UM-032 |
| PUT | `/users/me/type` | 사용자 유형 변경 | REQ-UM-033 |
| DELETE | `/users/me` | 회원 탈퇴 | REQ-UM-034 |

### 기업 (companies)
| Method | Endpoint | 설명 | 요구사항 |
|--------|----------|------|----------|
| GET | `/companies` | 내 기업 목록 | REQ-CP-001 |
| POST | `/companies` | 기업 등록 | REQ-CP-001 |
| PUT | `/companies/{id}` | 기업 수정 | REQ-CP-002 |
| POST | `/companies/{id}/upload` | 사업자등록증 업로드 | REQ-CP-003 |

### 상담 이력 (histories)
| Method | Endpoint | 설명 | 요구사항 |
|--------|----------|------|----------|
| GET | `/histories` | 상담 이력 조회 | REQ-UI-004 |
| POST | `/histories` | 상담 이력 저장 | - |
| GET | `/histories/{id}` | 상담 상세 조회 | - |

### 일정 (schedules)
| Method | Endpoint | 설명 |
|--------|----------|------|
| GET | `/schedules` | 일정 목록 조회 |
| POST | `/schedules` | 일정 등록 |
| PUT | `/schedules/{id}` | 일정 수정 |
| DELETE | `/schedules/{id}` | 일정 삭제 |

## 인증 흐름

### Google OAuth2
```
1. Frontend: /auth/google 요청
2. Backend: Google OAuth URL 반환
3. 사용자: Google 로그인
4. Google: /auth/google/callback으로 리다이렉트
5. Backend: Google 토큰 검증, 사용자 생성/조회
6. Backend: JWT 토큰 발급
7. Frontend: JWT 저장, 이후 요청에 사용
```

### JWT 인증
```python
# 인증이 필요한 엔드포인트
@router.get("/me")
async def get_me(current_user = Depends(get_current_user)):
    # current_user: User 모델 인스턴스
    return current_user
```

## 파일 수정 시 확인사항

### 새 라우터 추가
1. `apps/{기능}/router.py` 생성
2. `main.py`에 라우터 등록:
```python
from apps.{기능}.router import router as {기능}_router
app.include_router({기능}_router)
```

### 새 모델 추가
1. `apps/common/models.py`에 모델 클래스 추가
2. 외래키 관계 정의
3. `database.sql`에 테이블 정의 추가

### 새 스키마 추가
1. `apps/{기능}/schemas.py`에 Pydantic 모델 추가
2. Request/Response 스키마 분리

## 환경 변수 (.env)
```bash
MYSQL_HOST=localhost
MYSQL_PORT=3306
MYSQL_DATABASE=final_test
MYSQL_USER=root
MYSQL_PASSWORD=

GOOGLE_CLIENT_ID=your-client-id
GOOGLE_CLIENT_SECRET=your-secret
GOOGLE_REDIRECT_URI=http://localhost:8000/auth/google/callback

JWT_SECRET_KEY=your-secret-key
JWT_ALGORITHM=HS256
JWT_EXPIRE_MINUTES=60
```

### 환경 설정 구현
```python
# config/settings.py
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    MYSQL_HOST: str = "localhost"
    MYSQL_PORT: int = 3306
    MYSQL_DATABASE: str = "final_test"
    MYSQL_USER: str = "root"
    MYSQL_PASSWORD: str = ""

    GOOGLE_CLIENT_ID: str
    GOOGLE_CLIENT_SECRET: str
    GOOGLE_REDIRECT_URI: str

    JWT_SECRET_KEY: str
    JWT_ALGORITHM: str = "HS256"
    JWT_EXPIRE_MINUTES: int = 60

    class Config:
        env_file = ".env"

settings = Settings()
```

```python
# config/database.py
from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from config.settings import settings

SQLALCHEMY_DATABASE_URL = (
    f"mysql+pymysql://{settings.MYSQL_USER}:{settings.MYSQL_PASSWORD}"
    f"@{settings.MYSQL_HOST}:{settings.MYSQL_PORT}/{settings.MYSQL_DATABASE}"
)

engine = create_engine(SQLALCHEMY_DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

# 의존성
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
```

## 테스트
```bash
pytest tests/
pytest tests/ -v --cov=apps
```

## 보안 요구사항
- 비밀번호 암호화: bcrypt (REQ-SC-001)
- 민감정보 암호화: AES-256 (REQ-SC-002)
- 통신 암호화: HTTPS/TLS (REQ-SC-003)
- JWT 인증 (REQ-SC-011)
- 세션 관리 (REQ-SC-012)
- 권한 분리 (REQ-SC-013)

---

## 코드 품질 가이드라인 (필수 준수)

### 절대 금지 사항
- **하드코딩 금지**: DB 연결 정보, API 키, 포트 번호 등을 코드에 직접 작성 금지 → `settings.py` 환경 변수 사용
- **매직 넘버/매직 스트링 금지**: `if status == 1`, `sleep(3)` 등 의미 없는 값 직접 사용 금지
- **중복 코드 금지**: 동일한 로직은 service 클래스 또는 유틸 함수로 추출
- **SQL 인젝션 취약 코드 금지**: raw SQL 대신 SQLAlchemy ORM 쿼리 사용
- **보안 정보 노출 금지**: 비밀번호, 토큰, API 키를 코드/로그에 노출 금지

### 필수 준수 사항
- **환경 변수 사용**: 모든 설정값은 `.env` 파일 + `config/settings.py`로 관리
- **상수 정의**: 반복되는 값은 상수로 정의 (예: 코드 테이블 값)
- **타입 힌트 사용**: 함수 파라미터와 반환값에 타입 힌트 필수
- **Pydantic 스키마**: API 요청/응답은 반드시 Pydantic 모델로 검증
- **에러 처리**: HTTPException으로 적절한 상태 코드와 메시지 반환
- **의미 있는 네이밍**: 함수, 클래스, 변수명은 역할을 명확히 표현
