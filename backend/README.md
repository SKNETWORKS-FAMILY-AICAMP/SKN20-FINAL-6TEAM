# Backend - FastAPI REST API

> Bizi 플랫폼의 인증, 사용자, 기업, 상담 이력, 일정 관리를 담당하는 REST API 서버입니다.

## 주요 기능

- **Google OAuth2 인증**: 소셜 로그인 + JWT 토큰 발급/갱신
- **사용자 관리**: 사용자 정보 조회/수정, 유형 변경, 회원 탈퇴
- **기업 프로필**: 기업 등록/수정/삭제, 사업자등록증 업로드
- **상담 이력**: 채팅 상담 내역 저장 및 조회
- **일정 관리**: 일정 CRUD
- **관리자 대시보드**: 상담 로그 조회, 평가 통계, 필터링

## 기술 스택

| 구분 | 기술 |
|------|------|
| 프레임워크 | FastAPI |
| ORM | SQLAlchemy 2.0 |
| 데이터베이스 | MySQL 8.0 (AWS RDS, 스키마: `bizi_db`) |
| 인증 | Google OAuth2 + JWT (HttpOnly Cookie) |

## 시작하기

### 사전 요구사항

- Python 3.10+
- MySQL 8.0

### 실행

```bash
cd backend
source ../.venv/bin/activate
pip install -r requirements.txt
uvicorn main:app --host 0.0.0.0 --port 8000 --reload
```

### 환경 변수

`.env` 파일을 프로젝트 루트에 생성합니다. (`.env.example` 참고)

| 변수 | 설명 | 필수 |
|------|------|------|
| `MYSQL_HOST` | MySQL 호스트 | O |
| `MYSQL_PORT` | MySQL 포트 (기본: 3306) | O |
| `MYSQL_DATABASE` | 스키마명 (기본: `bizi_db`) | O |
| `MYSQL_USER` / `MYSQL_PASSWORD` | DB 인증 정보 | O |
| `GOOGLE_CLIENT_ID` / `GOOGLE_CLIENT_SECRET` | Google OAuth2 클라이언트 | O |
| `GOOGLE_REDIRECT_URI` | OAuth 콜백 URL | O |
| `JWT_SECRET_KEY` | JWT 서명 키 | O |
| `JWT_ALGORITHM` | JWT 알고리즘 (기본: HS256) | - |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | Access 토큰 만료 시간 (기본: 5분) | - |
| `REFRESH_TOKEN_EXPIRE_DAYS` | Refresh 토큰 만료 기간 (기본: 7일) | - |
| `RAG_API_KEY` | RAG 서비스 인증 키 | - |
| `RAG_SERVICE_URL` | RAG 서비스 URL (기본: `http://rag:8001`) | - |

## 프로젝트 구조

```
backend/
├── main.py               # FastAPI 진입점
├── database.sql          # DB 스키마 정의
├── config/
│   ├── settings.py       # Pydantic BaseSettings
│   └── database.py       # SQLAlchemy 연결
├── scripts/
│   └── generate_code_sql.py  # KSIC 업종코드/지역코드 SQL+TS 생성
└── apps/
    ├── auth/             # Google OAuth2 인증, 토큰 블랙리스트
    ├── users/            # 사용자 관리
    ├── companies/        # 기업 프로필
    ├── histories/        # 상담 이력
    ├── schedules/        # 일정 관리
    ├── admin/            # 관리자 대시보드, 서버 상태
    ├── rag/              # RAG 채팅 프록시 (Backend 경유)
    └── common/
        ├── models.py     # SQLAlchemy 모델
        └── deps.py       # 의존성 (get_db, get_current_user)
```

## API 엔드포인트

### 인증

| Method | Endpoint | 설명 |
|--------|----------|------|
| POST | `/auth/google` | Google ID Token 검증 + 로그인 |
| POST | `/auth/test-login` | 테스트 로그인 (ENABLE_TEST_LOGIN) |
| POST | `/auth/logout` | 로그아웃 |
| POST | `/auth/refresh` | 토큰 갱신 |
| GET | `/auth/me` | 현재 사용자 정보 |

### 사용자

| Method | Endpoint | 설명 |
|--------|----------|------|
| GET | `/users/me` | 내 정보 조회 |
| PUT | `/users/me` | 내 정보 수정 |
| PUT | `/users/me/type` | 사용자 유형 변경 |
| DELETE | `/users/me` | 회원 탈퇴 |

### 기업

| Method | Endpoint | 설명 |
|--------|----------|------|
| GET | `/companies` | 내 기업 목록 |
| GET | `/companies/{id}` | 기업 상세 조회 |
| POST | `/companies` | 기업 등록 |
| PUT | `/companies/{id}` | 기업 수정 |
| DELETE | `/companies/{id}` | 기업 삭제 (소프트 삭제) |
| POST | `/companies/{id}/upload` | 사업자등록증 업로드 |

### 상담 이력

| Method | Endpoint | 설명 |
|--------|----------|------|
| GET | `/histories` | 상담 이력 조회 |
| POST | `/histories` | 상담 이력 저장 |
| GET | `/histories/{id}` | 상담 상세 조회 |

### 일정

| Method | Endpoint | 설명 |
|--------|----------|------|
| GET | `/schedules` | 일정 목록 조회 |
| POST | `/schedules` | 일정 등록 |
| PUT | `/schedules/{id}` | 일정 수정 |
| DELETE | `/schedules/{id}` | 일정 삭제 |

### RAG 프록시

| Method | Endpoint | 설명 |
|--------|----------|------|
| POST | `/rag/chat` | RAG 채팅 프록시 (비스트리밍) |
| POST | `/rag/chat/stream` | RAG 채팅 프록시 (SSE 스트리밍) |
| GET | `/rag/health` | RAG 서비스 헬스체크 프록시 |

### 관리자 (U0000001 권한 필요)

| Method | Endpoint | 설명 |
|--------|----------|------|
| GET | `/admin/status` | 서버 상태 모니터링 (Backend/RAG/DB) |
| GET | `/admin/histories` | 상담 이력 목록 (페이지네이션, 필터링) |
| GET | `/admin/histories/stats` | 평가 통계 |
| GET | `/admin/histories/{id}` | 상담 이력 상세 |

## DB 스키마 요약

| 테이블 | 설명 |
|--------|------|
| `code` | 코드 마스터 (사용자유형, 업종, 에이전트, 주관기관) |
| `user` | 사용자 (Google 이메일, 유형) |
| `company` | 기업 프로필 |
| `history` | 상담 이력 (질문, 답변, 평가 데이터) |
| `file` | 파일 정보 |
| `announce` | 지원사업 공고 |
| `schedule` | 일정 |
| `token_blacklist` | JWT 토큰 블랙리스트 (jti, expires_at, use_yn) |

상세 스키마: [`database.sql`](./database.sql)

## 관련 문서

- [프로젝트 전체 가이드](../CLAUDE.md)
- [DB 스키마 상세](./database.sql)
- [API 문서 (Swagger)](http://localhost:8000/docs) (서버 실행 후 접근)
