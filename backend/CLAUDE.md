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
│   ├── settings.py       # 환경 설정 (Pydantic BaseSettings)
│   └── database.py       # SQLAlchemy 연결
├── scripts/
│   └── generate_code_sql.py  # KSIC 업종코드/지역코드 SQL+TS 생성 스크립트
└── apps/
    ├── auth/             # Google OAuth2 인증
    ├── users/            # 사용자 관리
    ├── companies/        # 기업 프로필
    ├── histories/        # 상담 이력
    ├── schedules/        # 일정 관리
    └── common/
        ├── models.py     # SQLAlchemy 모델 (User, Company, History, Code, File, Announce, Schedule)
        └── deps.py       # 의존성 (get_db, get_current_user - JWT Bearer)
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

새 기능 추가 시 아래 파일의 패턴을 따르세요:
- **라우터**: `apps/*/router.py` → 패턴: `.claude/rules/patterns.md`
- **서비스**: `apps/*/service.py` → 패턴: `.claude/rules/patterns.md`
- **모델**: `apps/common/models.py` (User, Company, History, Code, File, Announce, Schedule)
- **스키마**: `apps/*/schemas.py` → 패턴: `.claude/rules/patterns.md`
- **의존성**: `apps/common/deps.py` (get_db, get_current_user - JWT Bearer)
- **설정**: `config/settings.py` (Pydantic BaseSettings), `config/database.py` (SQLAlchemy)

### 라우터 등록 (main.py)
새 라우터 추가 시 `main.py`에 등록:
```python
from apps.{기능}.router import router as {기능}_router
app.include_router({기능}_router)
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
- `U`: 사용자 유형 (U0000001: 관리자, U0000002: 예비창업자, U0000003: 사업자)
- `B`: 업종 코드 — KSIC(한국표준산업분류) 기반, 대분류 21개 + 소분류 232개 (예: BA000000: 농업, BC101000: 도축업)
- `A`: 에이전트 코드 (A0000001~A0000005)
- `H`: 주관기관 코드

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

구현 코드: `apps/auth/router.py` 참조

---

## 파일 수정 가이드

### 새 라우터 추가
1. `apps/{기능}/` 디렉토리 생성
2. `router.py`, `service.py`, `schemas.py` 작성
3. `main.py`에 라우터 등록

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

## 코드 품질
`.claude/rules/coding-style.md`, `.claude/rules/security.md`, `.claude/rules/patterns.md` 참조
