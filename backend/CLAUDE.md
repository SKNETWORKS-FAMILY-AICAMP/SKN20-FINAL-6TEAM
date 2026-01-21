# Backend - FastAPI REST API

## 개요
BizMate의 백엔드는 FastAPI를 사용하며, Google OAuth2 인증과 SQLAlchemy ORM을 사용합니다.
사용자 인증, 데이터 관리를 담당하며, RAG 서비스와는 분리되어 운영됩니다.

## 기술 스택
- Python 3.10+
- FastAPI
- SQLAlchemy 2.0
- MySQL 8.0
- Google OAuth2 인증
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
    │   ├── router.py
    │   ├── service.py
    │   └── schemas.py
    ├── users/            # 사용자 관리
    ├── companies/        # 기업 프로필
    ├── histories/        # 상담 이력 저장
    ├── schedules/        # 일정 관리
    └── common/
        ├── models.py     # SQLAlchemy 모델
        └── deps.py       # 의존성 (get_current_user 등)
```

## 실행 방법
```bash
cd backend
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate
pip install -r requirements.txt
uvicorn main:app --host 0.0.0.0 --port 8000 --reload
```

## 주요 API

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
| POST | `/companies` | 기업 등록 |
| PUT | `/companies/{id}` | 기업 수정 |
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

## 데이터베이스

### 스키마
- 스키마명: `final_test`
- 상세 정의: `database.sql` 참조

### 테이블 구조
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

## 환경 변수
```
MYSQL_HOST=localhost
MYSQL_PORT=3306
MYSQL_DATABASE=final_test
MYSQL_USER=root
MYSQL_PASSWORD=

GOOGLE_CLIENT_ID=
GOOGLE_CLIENT_SECRET=
GOOGLE_REDIRECT_URI=http://localhost:8000/auth/google/callback

JWT_SECRET_KEY=your-secret-key
JWT_ALGORITHM=HS256
JWT_EXPIRE_MINUTES=60
```

## 인증 흐름
```
1. Frontend → /auth/google 요청
2. Backend → Google OAuth URL 반환
3. 사용자 → Google 로그인
4. Google → /auth/google/callback 리다이렉트
5. Backend → Google 토큰 검증, 사용자 생성/조회
6. Backend → JWT 토큰 발급
7. Frontend → JWT 저장, 이후 요청에 사용
```
