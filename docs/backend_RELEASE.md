# Release Notes

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
