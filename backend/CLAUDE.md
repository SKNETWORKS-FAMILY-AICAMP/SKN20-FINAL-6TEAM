# Backend - FastAPI REST API

> **이 문서는 Claude Code를 위한 자기 완결적 개발 가이드입니다.**
> 다른 AI 에이전트는 [AGENTS.md](./AGENTS.md)를 참조하세요.

## 프로젝트 개요
- **프레임워크**: FastAPI
- **ORM**: SQLAlchemy 2.0
- **데이터베이스**: MySQL 8.0 (스키마: final_test)
- **인증**: Google OAuth2 + JWT
- **포트**: 8000

## 디렉토리 구조
```
backend/
├── main.py               # FastAPI 진입점
├── database.sql          # DB 스키마
├── config/
│   ├── settings.py       # 환경 설정
│   └── database.py       # SQLAlchemy 연결
└── apps/
    ├── auth/             # Google OAuth2 인증
    ├── users/            # 사용자 관리
    ├── companies/        # 기업 프로필
    ├── histories/        # 상담 이력
    ├── schedules/        # 일정 관리
    └── common/
        ├── models.py     # SQLAlchemy 모델
        └── deps.py       # 의존성 (get_current_user)
```

## 실행 방법
```bash
cd backend
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate
pip install -r requirements.txt
uvicorn main:app --host 0.0.0.0 --port 8000 --reload
```

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

---

## 코드 작성 가이드

### 1. 라우터 작성
```python
# apps/{기능}/router.py
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from apps.common.deps import get_db, get_current_user
from apps.common.models import User
from .schemas import UserResponse, UserUpdate

router = APIRouter(prefix="/users", tags=["users"])

@router.get("/me", response_model=UserResponse)
async def get_me(
    current_user: User = Depends(get_current_user)
):
    return current_user

@router.put("/me", response_model=UserResponse)
async def update_me(
    user_update: UserUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    current_user.username = user_update.username
    db.commit()
    db.refresh(current_user)
    return current_user
```

**라우터 등록** (main.py):
```python
from apps.users.router import router as users_router
app.include_router(users_router)
```

### 2. 비즈니스 로직 (Service)
```python
# apps/{기능}/service.py
from sqlalchemy.orm import Session
from apps.common.models import User, Company
from .schemas import CompanyCreate

class CompanyService:
    def __init__(self, db: Session):
        self.db = db

    def get_companies_by_user(self, user_id: int):
        return self.db.query(Company)\
            .filter(Company.user_id == user_id)\
            .all()

    def create_company(self, user_id: int, data: CompanyCreate):
        company = Company(
            user_id=user_id,
            com_name=data.company_name,
            biz_num=data.business_number,
            biz_code=data.industry_code
        )
        self.db.add(company)
        self.db.commit()
        self.db.refresh(company)
        return company
```

### 3. SQLAlchemy 모델
```python
# apps/common/models.py
from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Text
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

class History(Base):
    __tablename__ = "history"

    history_id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("user.user_id"), nullable=False)
    agent_code = Column(String(4), ForeignKey("code.code"))
    question = Column(Text)
    answer = Column(Text)
    created_at = Column(DateTime, default=datetime.now)

    # Relationships
    user = relationship("User", back_populates="histories")
```

### 4. Pydantic 스키마
```python
# apps/{기능}/schemas.py
from pydantic import BaseModel, EmailStr
from datetime import datetime

class UserResponse(BaseModel):
    user_id: int
    google_email: str
    username: str
    type_code: str
    created_at: datetime

    class Config:
        from_attributes = True

class UserUpdate(BaseModel):
    username: str

class CompanyCreate(BaseModel):
    company_name: str
    business_number: str
    industry_code: str

class CompanyResponse(BaseModel):
    company_id: int
    company_name: str
    business_number: str
    industry_code: str

    class Config:
        from_attributes = True
```

### 5. 의존성 (Dependencies)
```python
# apps/common/deps.py
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session
from jose import jwt, JWTError
from config.database import SessionLocal
from config.settings import settings
from .models import User

security = HTTPBearer()

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: Session = Depends(get_db)
) -> User:
    token = credentials.credentials
    try:
        payload = jwt.decode(
            token,
            settings.JWT_SECRET_KEY,
            algorithms=[settings.JWT_ALGORITHM]
        )
        user_email: str = payload.get("sub")
        if user_email is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid authentication credentials"
            )
    except JWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication credentials"
        )

    user = db.query(User).filter(User.google_email == user_email).first()
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found"
        )
    return user
```

### 6. 데이터베이스 설정
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
```

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

---

## 주요 API 엔드포인트

### 인증 (auth)
| Method | Endpoint | 설명 |
|--------|----------|------|
| GET | `/auth/google` | Google OAuth 로그인 시작 |
| GET | `/auth/google/callback` | OAuth 콜백 처리 |
| POST | `/auth/logout` | 로그아웃 |
| POST | `/auth/refresh` | 토큰 갱신 |

### 사용자 (users)
| Method | Endpoint | 설명 |
|--------|----------|------|
| GET | `/users/me` | 내 정보 조회 |
| PUT | `/users/me` | 내 정보 수정 |
| PUT | `/users/me/type` | 사용자 유형 변경 |
| DELETE | `/users/me` | 회원 탈퇴 |

### 기업 (companies)
| Method | Endpoint | 설명 |
|--------|----------|------|
| GET | `/companies` | 내 기업 목록 |
| GET | `/companies/{id}` | 기업 상세 조회 |
| POST | `/companies` | 기업 등록 |
| PUT | `/companies/{id}` | 기업 수정 |
| DELETE | `/companies/{id}` | 기업 삭제 (소프트 삭제: `use_yn=False`) |
| POST | `/companies/{id}/upload` | 사업자등록증 업로드 |

### 상담 이력 (histories)
| Method | Endpoint | 설명 |
|--------|----------|------|
| GET | `/histories` | 상담 이력 조회 |
| POST | `/histories` | 상담 이력 저장 |
| GET | `/histories/{id}` | 상담 상세 조회 |

### 일정 (schedules)
| Method | Endpoint | 설명 |
|--------|----------|------|
| GET | `/schedules` | 일정 목록 조회 |
| POST | `/schedules` | 일정 등록 |
| PUT | `/schedules/{id}` | 일정 수정 |
| DELETE | `/schedules/{id}` | 일정 삭제 |

---

## 데이터베이스 스키마

### 주요 테이블
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
- `U`: 사용자 유형 (U001: 관리자, U002: 예비창업자, U003: 사업자)
- `B`: 업종 코드 (B001: 음식점업, B002: 소매업, ...)
- `A`: 에이전트 코드 (A001: 창업, A002: 세무, A003: 지원사업, A004: 노무, A005: 법률, A006: 마케팅)
- `H`: 주관기관 코드 (H001: 중소벤처기업부, ...)

---

## Google OAuth2 인증 흐름
```
1. Frontend → GET /auth/google
2. Backend → Google OAuth URL 반환
3. 사용자 → Google 로그인
4. Google → GET /auth/google/callback 리다이렉트
5. Backend → Google 토큰 검증, 사용자 생성/조회
6. Backend → JWT 토큰 발급
7. Frontend → JWT 저장 (localStorage)
8. Frontend → 이후 요청 시 Authorization: Bearer {token}
```

### OAuth2 구현 예시
```python
# apps/auth/router.py
from fastapi import APIRouter, Depends
from authlib.integrations.starlette_client import OAuth
from config.settings import settings

router = APIRouter(prefix="/auth", tags=["auth"])
oauth = OAuth()

oauth.register(
    name='google',
    client_id=settings.GOOGLE_CLIENT_ID,
    client_secret=settings.GOOGLE_CLIENT_SECRET,
    server_metadata_url='https://accounts.google.com/.well-known/openid-configuration',
    client_kwargs={'scope': 'openid email profile'}
)

@router.get("/google")
async def login_google():
    redirect_uri = settings.GOOGLE_REDIRECT_URI
    return await oauth.google.authorize_redirect(redirect_uri)

@router.get("/google/callback")
async def auth_callback(code: str, db: Session = Depends(get_db)):
    token = await oauth.google.authorize_access_token()
    user_info = token.get('userinfo')

    # 사용자 생성 또는 조회
    user = db.query(User).filter(User.google_email == user_info['email']).first()
    if not user:
        user = User(
            google_email=user_info['email'],
            username=user_info['name']
        )
        db.add(user)
        db.commit()

    # JWT 발급
    access_token = create_access_token(data={"sub": user.google_email})
    return {"access_token": access_token, "token_type": "bearer"}
```

---

## 파일 수정 가이드

### 새 라우터 추가
1. `apps/{기능}/` 디렉토리 생성
2. `router.py`, `service.py`, `schemas.py` 작성
3. `main.py`에 라우터 등록:
```python
from apps.{기능}.router import router as {기능}_router
app.include_router({기능}_router)
```

### 새 모델 추가
1. `apps/common/models.py`에 클래스 추가
2. 관계(relationship) 정의
3. `database.sql`에 CREATE TABLE 추가

### 새 스키마 추가
- Request 스키마: 입력 검증용
- Response 스키마: 출력 직렬화용
- `Config.from_attributes = True` 설정

---

## 중요 참고사항
- **인증**: JWT 토큰은 Bearer 방식
- **세션**: SQLAlchemy Session은 요청마다 생성/종료
- **에러 처리**: HTTPException 사용
- **스키마**: 스키마명 `final_test` 고정
- **포트**: 8000 (Frontend는 5173에서 CORS 허용)

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
