# Release Notes

## [2026-02-26] - PRD 요구사항 현황 갱신 + 프로젝트 문서 간소화

### Documentation
- **PRD.md 요구사항 현황 갱신** (`PRD.md`, `backend/main.py`): 요구사항 상태(✅/🔧/❌) 갱신
- **backend/CLAUDE.md·AGENTS.md 간소화**: 코드에서 파악 가능한 디렉토리 구조·패턴 설명 제거, 프로젝트 고유 컨텍스트(Gotchas, 환경변수, 워크플로우)만 유지

## [2026-02-25] - 로깅 시스템 전면 개선 — 보안 마스킹 · 로그 제한 · LOG_LEVEL · X-Request-ID 추적

### Features
- **LOG_LEVEL 동적 제어** (`config/settings.py`, `main.py`, `docker-compose*.yaml`): `LOG_LEVEL` 환경변수 추가 — 재빌드 없이 로그 레벨 변경 가능 (기본값 `INFO`)
- **X-Request-ID 서비스 간 요청 추적** (`main.py`, `apps/rag/router.py`, `config/logging_config.py`): `AuditLoggingMiddleware`에서 요청마다 UUID 생성 → `request.state`·`ContextVar` 동시 저장, 응답 헤더 `X-Request-ID` 추가, RAG 프록시 요청 헤더에 전달, JSON 로그·stdout 포맷에 `request_id` 필드 포함

### Security
- **Backend 민감정보 마스킹** (`config/logging_utils.py` 신규, `main.py`): `SensitiveDataFilter` Backend 전체 적용 — 이메일·휴대폰·주민번호·사업자번호·신용카드·계좌번호를 `backend.log`에 평문 기록 방지

### Performance
- **Docker 로그 용량 제한** (`docker-compose.prod.yaml`, `docker-compose.yaml`): 전 서비스 `json-file` 드라이버 명시 — prod 총 130MB 예산(10m×3개), dev 누락 4개 서비스 동일 설정 추가 (t3.medium 디스크 고갈 방지)

## [2026-02-24] - 기업 프로필 개선 + 지원사업 공고 API + 관리자 모니터링

### Features
- **기업 프로필 개선 및 지원사업 공고 API** (`apps/announces/`, `apps/companies/service.py`): announces CRUD 모듈 신규 추가 (router, service, schemas), 기업 서비스 로직 확장
- **관리자 모니터링 시스템** (`apps/admin/`, `apps/common/`, `config/logging_config.py`): JSON 파일 로깅(/var/log/app/backend.log), job_logs 테이블(스케줄러 실행 이력), `/admin/metrics`(psutil), `/admin/scheduler/status`, `/admin/logs` 엔드포인트 추가, AWS SES 이메일 알림(리소스 90% 초과·스케줄러 실패 시)

### Bug Fixes
- **로그 파일 핸들러 PermissionError 수정** (`config/logging_config.py`): named volume 권한 오류 시 graceful 처리, 컨테이너 기동 실패 방지

### Refactoring
- **전체 품질 개선** (`main.py` 외): 보안/안정성/성능/멀티도메인 Phase 6~9 일괄 적용

### Documentation
- **프로젝트 문서 현행화**: 코드 불일치 27건 수정

## [2026-02-23] - 문서 현행화 + 문서 자동 생성 + 멀티턴 대화

### Features
- **문서 자동 생성 기능** (`apps/rag/router.py`): 근로계약서/사업계획서 다운로드 엔드포인트 추가 — RAG Service 프록시를 통한 문서 생성 API 연동
- **멀티턴 대화 구현** (`apps/histories/`): 세션별 독립 history를 RAG에 전달하여 대화 문맥 유지

### Documentation
- **AGENTS.md 갱신**: RAG 프록시 모듈 및 엔드포인트 구조 반영

## [2026-02-20] - 기업 등록 관리자 보호 강화

### Bug Fixes
- **관리자 유형 변경 보호** (`apps/users/service.py`): `update_user_type()`에 관리자 체크 추가 — `type_code == 'U0000001'`인 경우 `ValueError` 발생하여 관리자 권한 무결성 보장 (프론트엔드 스킵 + 백엔드 이중 보호)

## [2026-02-19] - RAGAS 백그라운드 평가 안정성 개선

### Bug Fixes
- **RAGAS None 값 필터링** (`apps/histories/background.py`): `run_ragas_background()`에서 evaluator 비활성 또는 평가 실패 시 포함되는 `None` 값 제거 — 빈 dict 전달 방지 후 early return

## [2026-02-19] - 도메인 설정 DB 기반 전환 + RAGAS 비동기 평가

### Features
- **도메인 테이블 추가** (`database.sql`): `domain_keyword`, `domain_compound_rule`, `domain_representative_query` 테이블 스키마 추가 (키워드/복합규칙/대표쿼리 DB 기반 관리)
- **RAGAS 비동기 백그라운드 평가** (`apps/histories/background.py`): `run_ragas_background()` — 상담 이력 저장 후 FastAPI BackgroundTask로 RAG 서비스의 `POST /api/evaluate` 호출, 결과를 `evaluation_data`에 자동 머지

### Bug Fixes
- **히스토리 서비스** (`apps/histories/service.py`): `update_evaluation_data()` 메서드 추가 — RAGAS 메트릭을 기존 evaluation_data JSON에 머지
- **히스토리 라우터** (`apps/histories/router.py`): `create_history`에 `BackgroundTasks` 추가 — contexts 존재 시 RAGAS 평가 백그라운드 트리거 (응답 지연 0ms)

### Chores
- **마이그레이션 스크립트 추가** (`scripts/migrate_domain_tables.sql`): 도메인 설정 DB 마이그레이션 SQL 스크립트 추가
- **PyJWT 라이브러리 전환** (`requirements.txt`): `python-jose` → `PyJWT` 라이브러리 교체

## [2026-02-17] - 보안 감사 Phase 0~6 일괄 적용 + RAG 프록시 + 공고 배치

### Features
- **RAG 프록시 라우터** (`apps/rag/`): Backend 경유 RAG 채팅 프록시 (비스트리밍 + SSE 스트리밍), 인증된 사용자의 기업 컨텍스트 자동 주입, `get_optional_user` 의존성으로 게스트/인증 모두 지원
- **토큰 블랙리스트 자동 정리**: `lifespan` 이벤트로 1시간마다 만료 토큰 정리 (`_cleanup_blacklist_loop`)
- **Announce 테이블 확장**: `source_type`, `source_id`, `target_desc`, `exclusion_desc`, `amount_desc`, `apply_start`, `apply_end`, `region`, `organization`, `source_url`, `doc_s3_key`, `form_s3_key` 컬럼 추가 (배치 갱신용)

### Security
- **프로덕션 보안 강제** (`settings.py`): `enforce_production_security` 모델 검증기 — COOKIE_SECURE 강제, MYSQL_PASSWORD 필수, TEST_LOGIN 강제 비활성화, RAG_API_KEY 미설정 경고, CORS localhost 자동 제거
- **jose → PyJWT 전환**: `python-jose` → `PyJWT` 라이브러리 교체 (`jwt.decode`, `InvalidTokenError`)
- **CSRF 미들웨어 개선**: JSON Content-Type은 CSRF-safe 판정, multipart는 X-Requested-With 필수
- **쿠키 삭제 보안**: `clear_auth_cookies`에 `secure`/`samesite` 속성 명시
- **프로덕션 전역 예외 핸들러**: `ENVIRONMENT=production` 시 스택 트레이스 노출 방지
- **Admin Rate Limiting**: `/status` 10/min, `/histories` 30/min, `/histories/stats` 10/min, `/histories/{id}` 30/min
- **테스트 로그인 Rate Limiting**: `/test-login` 5/min, `/logout` 10/min 추가
- **ACCESS_TOKEN_EXPIRE_MINUTES**: 15분 → 5분 단축

### Refactoring
- **Dockerfile.prod 멀티스테이지 빌드**: 단일 스테이지 → 2단계 (builder + runtime), gcc/pkg-config 프로덕션 이미지에서 제거
- **non-root 컨테이너**: `appuser:appgroup` (UID/GID 1001) 사용자로 실행
- **get_optional_user 의존성** (`deps.py`): 게스트 허용 엔드포인트용 선택적 인증 함수 추가

## [2026-02-15] - 전체 프로젝트 리팩토링 (코드 품질 개선)

### Refactoring
- `auth/schemas.py` Pydantic v1 `class Config` → v2 `model_config = ConfigDict(from_attributes=True)` 통일
- `admin/router.py` 관리자 코드 인라인 `"U0000001"` → `users/service.py`의 `ADMIN_TYPE_CODE` 상수 import

## [2026-02-13] - 관리자 로그 페이지 개선

### Features
- 관리자 상담 로그에 에이전트 이름 표시 (Code 테이블 JOIN)
- RAGAS 평가 지표 확장: `context_precision`, `context_recall` 추가
- 상담 응답시간(`response_time`) 필드 추가 (history 테이블 + API 응답)

## [2026-02-13] - 감사보고서 26건 일괄 구현 + 프로덕션 배포 환경

### Features
- `Dockerfile.prod` 추가: gunicorn + uvicorn worker (2 workers, t3.medium 기준)
- `.dockerignore` 확장: 프로덕션 빌드 컨텍스트 최소화

### Security
- `AuditLoggingMiddleware` 추가 (M9) — POST/PUT/DELETE/PATCH 요청의 req_id, method, path, status, ip, duration 구조화 로깅
- CORS 프로덕션 검증 (M10) — `@model_validator(mode="after")`로 production 환경 localhost 포함 시 경고

### Bug Fixes
- `is_blacklisted(jti, db)` 호출 버그 수정 — db 파라미터 누락

### Refactoring — 감사보고서 Backend 7건
- **서비스 레이어 추가** (C5): companies, histories, schedules, users 4개 모듈에 service.py 생성, 라우터에서 비즈니스 로직 분리
- **SQLAlchemy 2.0 통일** (C6): 15건의 `db.query()` → `select()` 변환 (auth 포함, 잔존 0건)
- **토큰 블랙리스트 Session DI** (H3): `token_blacklist.py` 3개 함수에 `db: Session` 파라미터 추가, `SessionLocal()` 직접 생성 제거
- **입력 유효성 검증** (H4): `companies/schemas.py` 사업자번호 `@field_validator`, `schedules/schemas.py` 날짜 범위 `@model_validator`
- **하드코딩 제거** (M3): `admin/service.py`의 `RAG_SERVICE_URL` → `settings.py`의 `Settings.RAG_SERVICE_URL` 필드로 이관
- **에러 메시지 한국어 통일** (L2): `auth/router.py`의 영어 에러 메시지 ~15건 한국어 변환
- **RAG_SERVICE_URL 설정** (H8): `backend/config/settings.py`에 `RAG_SERVICE_URL` 필드 추가

## [2026-02-12] - Admin 페이지 분리 및 서버 상태 모니터링

### Features
- Admin 페이지 분리: `/admin` (대시보드) + `/admin/log` (상담 로그)
- `GET /admin/status` 엔드포인트 추가 — Backend/RAG/DB 상태 및 응답시간 반환
- `ServiceStatus`, `ServerStatusResponse` Pydantic 스키마 추가
- `AdminService.get_server_status()`: DB ping, RAG health check, uptime 측정
- `httpx` 의존성 추가 (RAG 서비스 비동기 HTTP 호출용)
- `docker-compose.yaml`에 `ENABLE_TEST_LOGIN` 환경변수 전달 추가

## [2026-02-11] - AWS RDS 마이그레이션 + Nginx 리버스 프록시 + DB 안전성 강화

### Infrastructure
- Docker Compose 전면 재구성: Nginx 리버스 프록시 (외부 유일 진입점, port 80)
- SSH Tunnel 사이드카 추가 (Alpine + openssh-client → Bastion EC2 → AWS RDS)
- 모든 서비스 `ports` → `expose` 변경 (Nginx만 외부 노출)
- 로컬 MySQL 컨테이너 제거 → AWS RDS 전환
- `nginx.conf` 추가: `/api/*` → backend, `/rag/*` → rag, `/*` → frontend
- SSE 스트리밍 지원 (proxy_buffering off, proxy_read_timeout 300s)
- Vite HMR WebSocket 프록시 지원

### Refactoring
- DB 스키마명 `final_test` → `bizi_db` (settings.py, database.sql)
- `TokenBlacklist` 모델에 `use_yn` 컬럼 추가 — 만료 토큰 소프트 삭제
- `cleanup_expired()`: DELETE → UPDATE `use_yn=False` (소프트 삭제)
- `is_blacklisted()`: `use_yn=True` 필터 조건 추가
- FK ondelete: `CASCADE` → `RESTRICT` (company, history, schedule) — 연쇄 삭제 방지
- User relationships: `cascade="all, delete-orphan"` → `cascade="save-update, merge"`
- SQLAlchemy 커넥션 풀 튜닝: `pool_recycle=1800`, `pool_size=10`, `max_overflow=20`

### Documentation
- CLAUDE.md 갱신 — 소프트 삭제 범위 확대, FK RESTRICT 제약 명시

## [2026-02-11] - JWT HttpOnly 쿠키 전환 + 보안 감사 12건 수정

### Security
- JWT 인증 방식 전환: localStorage Bearer → HttpOnly 쿠키 (access_token + refresh_token)
- Refresh Token 자동 갱신 엔드포인트 (`POST /auth/refresh`)
- 토큰 블랙리스트 인메모리 → DB 전환 (`token_blacklist` 테이블 + `TokenBlacklist` 모델)
- `get_current_user`: Bearer 헤더 → 쿠키에서 토큰 추출 + jti 블랙리스트 검증
- JWT_SECRET_KEY 기본값 제거 + 시작 시 검증 (32자 이상 필수)
- Google OAuth `email_verified` 검증 추가
- 파일 업로드 확장자/크기/Content-Type 화이트리스트 검증
- 관리자 권한(U0000001) 셀프 상승 차단
- CSRF 미들웨어 추가 (Content-Type / X-Requested-With 검증)
- 탈퇴 사용자(`use_yn=False`) 로그인 차단
- 프로덕션 환경 Swagger/ReDoc 비활성화
- CORS methods/headers 최소화
- slowapi Rate Limiting (auth: 10/min, refresh: 30/min, upload: 5/min)
- 인증 이벤트 로깅 (login/logout/refresh)
- 에러 메시지 정규화 (내부 상세 → 서버 로그만)

### Documentation
- CLAUDE.md 갱신 — 인증 방식 HttpOnly 쿠키, TokenBlacklist 모델, CSRF/Rate Limiting 반영

## [2026-02-11] - Google OAuth2 로그인 구현

### Features
- Google ID Token 검증 + 자동 회원가입/로그인 API (`POST /auth/google`)
- `backend/apps/auth/services.py` 신규 추가 (Google token 검증 서비스)
- `GoogleLoginRequest` 스키마 추가
- `google-auth`, `requests` 의존성 추가
- `user.birth` 컬럼 `NOT NULL` → `DEFAULT NULL` 변경

## [2026-02-09] - 법률 도메인 스키마 추가 및 프로젝트 정리

### Features
- 법률 도메인 DB 스키마 추가 및 백엔드 코드 정리

### Chores
- 프로젝트 이름 bizmate → bizi 통일 (테스트 이메일, DB seed 데이터)
- RELEASE.md 경로 변경에 따른 hooks/commands 업데이트

## [2026-02-08] - 초기 릴리즈

### 핵심 기능
- **Google OAuth2 인증**: 소셜 로그인, JWT 토큰 발급/갱신, 로그아웃
- **사용자 관리**: 정보 조회/수정, 유형 변경 (예비창업자/사업자/관리자), 회원 탈퇴
- **기업 프로필 CRUD**: 사업자등록번호 중복 체크, 업종코드 (KSIC), 사업자등록증 업로드
- **상담 이력**: 채팅 상담 내역 저장/조회, 평가 데이터 (JSON) 포함
- **일정 관리**: 일정 CRUD
- **관리자 대시보드 API**: 상담 로그 페이지네이션/필터링, 평가 통계 (도메인별, 점수 범위)
- **코드 마스터 시스템**: KSIC 업종코드 (대분류 21개 + 소분류 232개), 지역코드, 에이전트코드, 주관기관코드

### 기술 스택
- FastAPI + SQLAlchemy 2.0 + MySQL 8.0
- Google OAuth2 + JWT (Bearer)
- Pydantic BaseSettings

### 파일 통계
- 총 파일: 62개
