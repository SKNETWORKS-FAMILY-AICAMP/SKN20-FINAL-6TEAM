# PHASE 0 — Security Audit: Structure Mapping & Configuration Exposure Report

**Project**: Bizi (통합 창업/경영 상담 챗봇)
**Audit Date**: 2026-02-17
**Audit Scope**: 전체 코드베이스 (backend, frontend, rag, scripts, infra)
**Status**: COMPLETE

---

## 1. 시스템 구조 매핑

### 1.1 서비스 아키텍처

```
Client → Nginx(:80) ──┬── /api/* → Backend(:8000) → SSH Tunnel → AWS RDS
                       ├── /rag/* → RAG(:8001) → ChromaDB(:8000)
                       └── /*     → Frontend(:5173)
```

| 서비스 | 엔트리포인트 | Dockerfile(s) | 외부 노출 |
|--------|-------------|---------------|----------|
| Nginx | nginx.conf / nginx.prod.conf | Dockerfile.nginx | **:80, :443** |
| Backend | backend/main.py | backend/Dockerfile, Dockerfile.prod | 내부 |
| Frontend | frontend/src/main.tsx | frontend/Dockerfile | 내부 |
| RAG | rag/main.py | rag/Dockerfile, Dockerfile.prod | 내부 |
| ChromaDB | chromadb/chroma:1.5.0 | (공식 이미지) | 내부 |
| SSH Tunnel | alpine + openssh | (인라인) | 내부 |
| RunPod | runpod-inference/handler.py | runpod-inference/Dockerfile | 외부 API |

### 1.2 인증 관련 파일

| 파일 | 역할 |
|------|------|
| `backend/apps/auth/router.py` | Google OAuth2 라우터, 테스트 로그인 |
| `backend/apps/auth/services.py` | 토큰 생성/검증, OAuth 콜백 |
| `backend/apps/auth/token_blacklist.py` | JWT 블랙리스트 (로그아웃) |
| `backend/apps/common/deps.py` | `get_current_user` 의존성 (HttpOnly 쿠키) |
| `backend/config/settings.py` | JWT_SECRET_KEY, Cookie 설정 |
| `frontend/src/lib/api.ts` | 401 인터셉터, refresh 큐 |
| `frontend/src/stores/authStore.ts` | 클라이언트 인증 상태 |

### 1.3 RAG 파이프라인 파일

| 파일 | 역할 |
|------|------|
| `rag/agents/router.py` | 메인 라우터 에이전트 (도메인 분류) |
| `rag/agents/base.py` | BaseAgent (벡터 검색 공통) |
| `rag/agents/retrieval_agent.py` | 검색 에이전트 |
| `rag/agents/generator.py` | LLM 응답 생성 |
| `rag/agents/{startup_funding,finance_tax,hr_labor,legal}.py` | 도메인 에이전트 |
| `rag/agents/evaluator.py` | 답변 품질 평가 |
| `rag/agents/executor.py` | 문서 생성 (근로계약서 등) |
| `rag/chains/rag_chain.py` | LangGraph 체인 |
| `rag/utils/prompts.py` | 모든 프롬프트 (집중 관리) |
| `rag/utils/search.py` | Hybrid Search (BM25+Vector) |
| `rag/utils/domain_classifier.py` | 도메인 외 질문 거부 |

### 1.4 VectorDB 관련 파일

| 파일 | 역할 |
|------|------|
| `rag/vectorstores/chroma.py` | ChromaDB 래퍼 |
| `rag/vectorstores/config.py` | 컬렉션별 설정 |
| `rag/vectorstores/embeddings.py` | 임베딩 모델 (로컬/RunPod) |
| `scripts/vectordb/builder.py` | 벡터 인덱스 빌드 |

### 1.5 AWS 관련 설정

| 파일 | 역할 |
|------|------|
| `docker-compose.yaml` | SSH 터널 (Bastion → RDS) |
| `docker-compose.prod.yaml` | 직접 RDS 연결, RunPod |
| `scripts/batch/s3_uploader.py` | S3 파일 업로드 |
| `scripts/batch/update_announcements.py` | 배치 파이프라인 (S3+DB) |

---

## 2. 발견사항 (Findings)

### CRITICAL — 즉시 조치 필요

#### C-01: .env 파일에 실제 프로덕션 자격증명 포함

- **파일**: `.env` (작업 디렉토리에 존재, git에는 미커밋)
- **위험도**: **CRITICAL**
- **내용**: `.env` 파일에 라이브 프로덕션 자격증명이 평문으로 저장됨:
  - MySQL 비밀번호 (RDS)
  - JWT Secret Key (64자)
  - Google OAuth Client Secret
  - OpenAI API Key (`sk-proj-...`)
  - RunPod API Key (`rpa_...`)
  - AWS Access Key ID (`AKIA...`) + Secret Access Key
  - BizInfo / K-Startup API Keys
  - AWS RDS 엔드포인트 + Bastion Host IP
  - S3 버킷명
- **공격 시나리오**: 개발 머신 침해, 클라우드 동기화(OneDrive/Dropbox), 또는 실수로 git 커밋 시 **전체 인프라 탈취** 가능
  - AWS 키로 RDS 직접 접근, S3 데이터 유출
  - OpenAI 키로 무단 API 사용 (비용 발생)
  - JWT 시크릿으로 임의 토큰 발급 (전체 사용자 가장)
- **완화 요소**: `.gitignore`에 `.env` 포함, git 히스토리에 미커밋
- **권장 조치**: 프로덕션 배포 시 AWS Secrets Manager / SSM Parameter Store 사용, 개발 머신에는 개발용 키만 유지

#### C-02: RAG API 키가 프론트엔드 빌드에 포함 (클라이언트 노출)

- **파일**: `docker-compose.prod.yaml:26`, `Dockerfile.nginx:17`, `frontend/src/lib/rag.ts:7`
- **위험도**: **CRITICAL**
- **내용**: `VITE_RAG_API_KEY`가 Docker 빌드 ARG로 React 번들에 포함됨. Vite는 `import.meta.env.VITE_*`를 **빌드 시 문자열 치환**하므로, 프로덕션 JS 번들에 RAG API 키가 평문으로 포함됨.
- **코드 경로**:
  1. `docker-compose.prod.yaml:26` — `VITE_RAG_API_KEY: ${RAG_API_KEY:-}` (빌드 ARG로 전달)
  2. `Dockerfile.nginx:17` — `ARG VITE_RAG_API_KEY=` (빌드 시 주입)
  3. `frontend/src/lib/rag.ts:7` — `const RAG_API_KEY = import.meta.env.VITE_RAG_API_KEY || ''` (번들에 포함)
  4. `frontend/src/lib/rag.ts:13,53` — `X-API-Key` 헤더에 평문 전송
- **공격 시나리오**: 브라우저 개발자 도구 → 번들 JS 검사 → RAG API 키 추출 → 인증 없이 RAG 서비스 직접 호출 (Rate limiting 우회, 프롬프트 인젝션 등)
- **영향**: RAG 서비스 인증이 실질적으로 무력화됨
- **권장 조치**: RAG 요청을 Backend를 경유하도록 변경 (Backend에서 서버 사이드로 RAG API 키 첨부), 또는 사용자별 JWT 토큰 기반 RAG 인증으로 전환

---

### HIGH — 조기 해결 권장

#### H-01: HTTPS 미적용 (HTTP 평문 통신)

- **파일**: `nginx.prod.conf` (SSL 블록이 주석 처리됨, 108~126행)
- **위험도**: **HIGH**
- **내용**: 프로덕션 nginx 설정에서 SSL/TLS가 비활성화 상태. 모든 트래픽이 HTTP 평문으로 전송됨.
- **공격 시나리오**: JWT 토큰, 사용자 입력, AI 응답이 네트워크에서 도청 가능. MITM 공격으로 세션 탈취.
- **완화 요소**: ACME challenge 경로(`/.well-known/acme-challenge/`)가 준비되어 있어 SSL 적용 의도는 있음
- **권장 조치**: Certbot 설정 완료 후 SSL 블록 활성화, HTTP→HTTPS 리다이렉트 적용

#### H-02: 문서화되지 않은 시크릿 (TAVILY_API_KEY, LAW_API_KEY 등)

- **파일**: `docker-compose.yaml:123`, `docker-compose.prod.yaml:97`, `scripts/crawling/collect_all_laws.py`, `rag/routes/monitoring.py`
- **위험도**: **HIGH**
- **내용**: 아래 환경변수가 코드에서 사용되나 `.env.example`에 미기재:
  - `TAVILY_API_KEY` — Docker Compose 3개 파일에서 RAG 서비스에 전달
  - `LAW_API_KEY` — 크롤링 스크립트 4곳에서 사용 (국가법령정보센터 API)
  - `SLACK_WEBHOOK_URL` — `scripts/batch/update_announcements.py:123`에서 사용
  - `ADMIN_API_KEY` — `rag/utils/config/settings.py:187`, `rag/routes/monitoring.py:24`에서 사용
- **위험**: 새 팀원이 `.env.example`만 참고할 경우 누락, 또는 시크릿 관리 대상에서 제외
- **조치 완료**: `.env.example`에 누락된 4개 환경변수 추가 (이 감사의 일부로 수정)

#### H-03: 프로덕션에서 COOKIE_SECURE=false 가능성

- **파일**: `backend/config/settings.py:39`
- **위험도**: **HIGH**
- **내용**: `COOKIE_SECURE` 기본값이 `False`. `docker-compose.prod.yaml:63`에서는 `"true"`로 설정하지만, 프로덕션 compose 파일 외 방식으로 배포 시 쿠키가 HTTP로 전송될 수 있음.
- **완화 요소**: `docker-compose.prod.yaml`에서 명시적으로 `COOKIE_SECURE: "true"` 설정됨
- **권장 조치**: `ENVIRONMENT=production`일 때 `COOKIE_SECURE`를 자동으로 `True`로 강제하는 validator 추가

#### H-04: SSH Tunnel StrictHostKeyChecking 미적용

- **파일**: `docker-compose.yaml:35`
- **위험도**: **HIGH**
- **내용**: SSH 터널에서 `StrictHostKeyChecking=accept-new` 사용. 첫 연결 시 호스트 키를 자동 수락하므로 초기 MITM 공격에 취약.
- **완화 요소**: 이후 연결에서는 `known_hosts` 파일로 검증, `ssh-known-hosts` 볼륨으로 영속화
- **권장 조치**: Bastion 호스트의 공개 키를 사전에 `known_hosts`에 배포

---

### MEDIUM — 개선 권장

#### M-01: CORS 기본값에 localhost 포함

- **파일**: `backend/config/settings.py:58`, `rag/utils/config/settings.py:335-336`
- **위험도**: **MEDIUM**
- **내용**: 두 서비스 모두 CORS 기본값이 `["http://localhost:5173", "http://localhost:3000"]`. `ENVIRONMENT=production`일 때 경고만 로그하고 차단하지 않음.
- **공격 시나리오**: 프로덕션에서 CORS_ORIGINS 미설정 시 로컬호스트 오리진 허용 → 개발자 머신에서 프로덕션 API에 CORS 요청 가능
- **권장 조치**: `ENVIRONMENT=production`일 때 localhost 오리진을 자동 제거하거나 시작 실패 처리

#### M-02: RAG API 인증 비활성화 가능

- **파일**: `rag/utils/config/settings.py:184-185`
- **위험도**: **MEDIUM**
- **내용**: `rag_api_key` 기본값이 빈 문자열 → 인증 비활성화. `admin_api_key`도 동일. 환경변수 미설정 시 RAG 서비스가 완전 개방됨.
- **완화 요소**: nginx에서 외부 접근 차단 (내부 네트워크만 접근)
- **권장 조치**: `ENVIRONMENT=production`일 때 `rag_api_key` 미설정 시 시작 실패 또는 경고

#### M-03: MySQL 비밀번호 기본값이 빈 문자열

- **파일**: `backend/config/settings.py:16`, `rag/utils/config/settings.py:108`, `scripts/batch/update_announcements.py:96`
- **위험도**: **MEDIUM**
- **내용**: 세 곳 모두 `MYSQL_PASSWORD` 기본값이 `""`. 프로덕션에서 빈 비밀번호로 DB 접근 시도 가능.
- **비교**: `JWT_SECRET_KEY`는 빈 값/기본값/32자 미만 시 시작 실패하는 검증이 있으나, `MYSQL_PASSWORD`에는 없음
- **권장 조치**: `ENVIRONMENT=production`일 때 `MYSQL_PASSWORD` 빈 값 검증 추가

#### M-04: nginx 개발 설정에서 X-Frame-Options 불일치

- **파일**: `nginx.conf:24` vs `nginx.prod.conf:43`
- **위험도**: **MEDIUM**
- **내용**: 개발 설정은 `DENY`, 프로덕션은 `SAMEORIGIN`. 개발/프로덕션 동작 불일치.
- **참고**: 프로덕션에서 `SAMEORIGIN`은 합리적 (iframe 임베딩 허용 시). 단, 의도적인 차이인지 확인 필요.

#### M-05: CSP에 unsafe-inline, unsafe-eval 포함

- **파일**: `nginx.conf:28` (개발 설정)
- **위험도**: **MEDIUM**
- **내용**: `script-src 'self' 'unsafe-inline' 'unsafe-eval'` — XSS 방어 효과 크게 감소. Vite 개발 서버에서 필요하나, 프로덕션 nginx 설정(`nginx.prod.conf`)에서는 **CSP 헤더 자체가 누락**됨.
- **위험**: 프로덕션에서 CSP가 없으므로 XSS 공격 방어 레이어 부재
- **권장 조치**: `nginx.prod.conf`에 프로덕션용 CSP 헤더 추가 (`unsafe-inline`/`unsafe-eval` 없이)

---

### LOW — 개선 고려

#### L-01: ENABLE_TEST_LOGIN 환경변수

- **파일**: `backend/config/settings.py:47`, `docker-compose.yaml:69`
- **위험도**: **LOW**
- **내용**: 테스트 로그인 엔드포인트 활성화 플래그. `docker-compose.prod.yaml:67`에서 `"false"`로 하드코딩되어 있어 프로덕션 위험 낮음.
- **완화 요소**: 프로덕션 compose에서 강제 비활성화

#### L-02: 프로덕션 nginx에서 server_tokens 미비활성화

- **파일**: `nginx.prod.conf`
- **위험도**: **LOW**
- **내용**: `server_tokens off;` 미설정. HTTP 응답에 nginx 버전 노출.
- **권장 조치**: `nginx.prod.conf`에 `server_tokens off;` 추가

#### L-03: Docker 이미지 `node:20-alpine` 버전 미고정

- **파일**: `Dockerfile.nginx:8`
- **위험도**: **LOW**
- **내용**: 특정 마이너 버전 미고정 (`node:20-alpine`). 빌드 재현성 저하 및 예기치 않은 취약점 도입 가능.
- **권장 조치**: `node:20.x.x-alpine` 형태로 마이너 버전 고정

---

## 3. 환경 변수 전체 인벤토리

### 3.1 시크릿 (총 18개)

| 변수 | 사용 위치 | .env.example | 검증 |
|------|----------|-------------|------|
| `MYSQL_PASSWORD` | backend, rag, scripts | O | 없음 (빈 문자열 허용) |
| `JWT_SECRET_KEY` | backend | O | **있음** (32자+, 기본값 거부) |
| `GOOGLE_CLIENT_ID` | backend, frontend | O | 없음 |
| `GOOGLE_CLIENT_SECRET` | backend | O | 없음 |
| `OPENAI_API_KEY` | rag, scripts | O | 있음 (sk- 형식 경고) |
| `RAG_API_KEY` | rag, frontend | O | 없음 (빈=비활성화) |
| `BIZINFO_API_KEY` | rag, scripts | O | 없음 |
| `KSTARTUP_API_KEY` | rag, scripts | O | 없음 |
| `RUNPOD_API_KEY` | rag | O | 없음 |
| `RUNPOD_ENDPOINT_ID` | rag | O | 없음 |
| `UPSTAGE_API_KEY` | rag (prod) | O | 없음 |
| `AWS_ACCESS_KEY_ID` | scripts (주석) | O (주석) | 없음 |
| `AWS_SECRET_ACCESS_KEY` | scripts (주석) | O (주석) | 없음 |
| `VITE_RAG_API_KEY` | frontend | 간접 | **클라이언트 노출 (C-02)** |
| `TAVILY_API_KEY` | docker-compose (3곳) | **O** (추가됨) | 없음 |
| `LAW_API_KEY` | scripts/crawling (4곳) | **O** (추가됨) | 없음 |
| `SLACK_WEBHOOK_URL` | scripts/batch | **O** (추가됨) | 없음 |
| `ADMIN_API_KEY` | rag/monitoring | **O** (추가됨) | 없음 |

### 3.2 안전한 관행 확인 (Positive Findings)

| 항목 | 상태 | 위치 |
|------|------|------|
| `.env` gitignore | **OK** | `.gitignore:1` |
| `.env.example`에 실제 자격증명 없음 | **OK** | 플레이스홀더만 |
| JWT 시크릿 시작 시 검증 | **OK** | `backend/config/settings.py:24-36` |
| SQLAlchemy 파라미터 숨김 | **OK** | `hide_parameters=True` |
| Pydantic BaseSettings 사용 | **OK** | backend, rag 모두 |
| HttpOnly 쿠키 (JWT) | **OK** | `backend/apps/common/deps.py` |
| CSRF 헤더 | **OK** | `X-Requested-With` |
| nginx Rate Limiting | **OK** | 개발/프로덕션 모두 적용 |
| 보안 헤더 (X-Frame-Options 등) | **OK** | nginx.conf, nginx.prod.conf |
| `.ssh/` gitignore | **OK** | `.gitignore` |
| `*.pem` gitignore | **OK** | `.gitignore` |
| ChromaDB 외부 미노출 | **OK** | `expose`만 사용, `ports` 없음 |
| 프로덕션 테스트 로그인 비활성화 | **OK** | `docker-compose.prod.yaml:67` |
| Docker 네트워크 분리 (프로덕션) | **OK** | `networks: backend` |

---

## 4. 우선순위별 권장 조치 요약

| 우선순위 | ID | 요약 | 예상 영향 | 권장 Phase |
|---------|-----|------|----------|-----------|
| **CRITICAL** | C-01 | 프로덕션 자격증명 즉시 로테이션 | 전체 인프라 탈취 방지 | Phase 5 (AWS) |
| **CRITICAL** | C-02 | RAG API 키 프론트엔드 노출 제거 | RAG 인증 무력화 방지 | Phase 2 (RAG) |
| **HIGH** | H-01 | SSL/TLS 활성화 | 도청/세션 탈취 방지 | Phase 4 (Nginx) |
| **HIGH** | H-02 | 미문서화 시크릿 `.env.example`에 추가 | 시크릿 관리 일관성 | **Phase 0 (완료)** |
| **HIGH** | H-03 | COOKIE_SECURE 프로덕션 강제 | 쿠키 탈취 방지 | Phase 1 (Auth) |
| **HIGH** | H-04 | SSH known_hosts 사전 배포 | 초기 MITM 방지 | Phase 4 (Docker) |
| **MEDIUM** | M-01 | CORS 프로덕션 시 localhost 차단 | 교차 오리진 공격 방지 | Phase 3 (API) |
| **MEDIUM** | M-02 | RAG 인증 프로덕션 필수화 | 무인증 접근 방지 | Phase 2 (RAG) |
| **MEDIUM** | M-03 | MySQL 비밀번호 검증 추가 | 빈 비밀번호 배포 방지 | Phase 3 (API) |
| **MEDIUM** | M-04 | X-Frame-Options 통일 | 일관된 보안 정책 | Phase 4 (Nginx) |
| **MEDIUM** | M-05 | 프로덕션 CSP 헤더 추가 | XSS 방어 레이어 추가 | Phase 4 (Nginx) |
| **LOW** | L-01 | 테스트 로그인 플래그 유지 관리 | 방어 심층화 | Phase 1 (Auth) |
| **LOW** | L-02 | server_tokens off | 정보 노출 최소화 | Phase 4 (Nginx) |
| **LOW** | L-03 | Docker 이미지 버전 고정 | 빌드 재현성 | Phase 4 (Docker) |

---

## 5. 다음 단계

Phase 0 완료. 다음 Phase 진행 순서:

| Phase | 범위 | 핵심 항목 |
|-------|------|----------|
| **Phase 1** | Auth & Session Security | Google OAuth, JWT, 쿠키 보안, 미들웨어 일관성 |
| **Phase 2** | Multi-User Isolation & RAG Security | 벡터DB 격리, 프롬프트 인젝션, C-02 수정 |
| **Phase 3** | API & Input Surface Hardening | 입력 검증, 파일 업로드, SQL 인젝션 |
| **Phase 4** | Docker & Nginx Hardening | 컨테이너 보안, 네트워크 격리, SSL |
| **Phase 5** | AWS & Data Layer Security | RDS, S3, IAM, 시크릿 관리 |
| **Phase 6** | Global Consistency & Architectural Risk | 종합 위험 평가 |
