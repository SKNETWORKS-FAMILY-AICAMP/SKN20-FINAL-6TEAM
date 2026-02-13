# Bizi 프로젝트 구조 감사 보고서

> 작성일: 2026-02-13
> 최종 갱신: 2026-02-13 (감사보고서 26건 + RAG 리팩토링 19건 반영, 커밋 `5486466` 기준)
> 분석 도구: Claude Code (pm-orchestrator + 전문 서브에이전트 6종)

## 감사 범위
- Backend (FastAPI + SQLAlchemy)
- RAG Service (LangChain/LangGraph + ChromaDB)
- Frontend (React + Vite + TypeScript)
- Infrastructure (Docker Compose + Nginx + SSH Tunnel)

---

## 발견 요약

| 등급 | 발견 | 수정 완료 | 잔여 |
|------|------|----------|------|
| CRITICAL | 6건 | **5건** | 1건 (C2: TLS) |
| HIGH | 8건 | **8건** | 0건 |
| MEDIUM | 10건 | **9건** | 1건 (M8: 게스트 우회) |
| LOW | 7건 | **5건** | 2건 (L6/L7: 테스트 스위트) |
| **합계** | **31건** | **27건** | **4건** |

---

## CRITICAL (6건)

### ~~C1. SSE 스트리밍 Nginx 통과 시 실패~~ -- ✅ 수정 완료

- **수정일**: 2026-02-13
- **수정 내용**:
  - `rag/main.py`: StreamingResponse에 `X-Accel-Buffering: no`, `Cache-Control: no-cache`, `Connection: keep-alive` 헤더 추가
  - `nginx.conf`: `/rag/` location에 `chunked_transfer_encoding on` 추가

### C2. TLS/HTTPS 미적용 -- ⏳ 미수정 (인프라 작업 필요)

- **위치**: `nginx.conf` - HTTP 80 포트만 리슨
- **위험**: JWT 쿠키, OAuth 토큰, 사용자 데이터가 평문 전송
- **필요 조치**:
  1. SSL 인증서 발급 (Let's Encrypt certbot 또는 AWS ACM)
  2. `nginx.conf`에 `listen 443 ssl` 추가 + 인증서 경로 설정
  3. HTTP 80 → HTTPS 301 리다이렉트 설정
  4. `docker-compose.yaml`에 443 포트 노출 + 인증서 볼륨 마운트
  5. `backend/config/settings.py`의 `COOKIE_SECURE=True` 설정
- **참고 nginx.conf 예시**:
  ```nginx
  server {
      listen 80;
      server_name your-domain.com;
      return 301 https://$host$request_uri;
  }

  server {
      listen 443 ssl;
      server_name your-domain.com;

      ssl_certificate /etc/nginx/ssl/fullchain.pem;
      ssl_certificate_key /etc/nginx/ssl/privkey.pem;
      ssl_protocols TLSv1.2 TLSv1.3;
      ssl_ciphers HIGH:!aNULL:!MD5;

      # ... 기존 location 블록 유지
  }
  ```

### ~~C3. SSH 터널 MITM 취약점~~ -- ✅ 수정 완료

- **수정일**: 2026-02-13
- **수정 내용**:
  - `docker-compose.yaml`: `StrictHostKeyChecking=no` → `accept-new` 변경
  - `UserKnownHostsFile=/root/.ssh/known_hosts` 명시
  - `ssh-known-hosts` 네임드 볼륨 추가 (컨테이너 재시작 간 호스트 키 영속화)
- **동작**: 초회 접속 시 자동 등록, 이후 키 변경 시 MITM 탐지/차단

### ~~C4. RAG 프롬프트 인젝션~~ -- ✅ 수정 완료

- **수정일**: 2026-02-13
- **수정 내용**:
  - `rag/utils/sanitizer.py` (신규): 24개 인젝션 패턴 탐지 (영어 14 + 한국어 10), `[FILTERED]` 마스킹
  - `rag/utils/prompts.py`: 사용자 입력이 포함되는 5개 도메인 프롬프트에 `PROMPT_INJECTION_GUARD` 추가
  - `rag/agents/router.py`: `_classify_node()` + `astream()` 양쪽 진입점에 sanitizer 적용
- **보호 범위**: 일반 채팅 + 스트리밍 채팅 모든 경로

### ~~C5. Backend 서비스 레이어 부재~~ -- ✅ 수정 완료

- **수정일**: 2026-02-13
- **수정 내용**:
  - `backend/apps/companies/service.py` (신규): `CompanyService` 클래스
  - `backend/apps/histories/service.py` (신규): `HistoryService` 클래스
  - `backend/apps/schedules/service.py` (신규): `ScheduleService` 클래스
  - `backend/apps/users/service.py` (신규): `UserService` 클래스
  - 4개 라우터 리팩토링: 비즈니스 로직 → 서비스, `Depends()` 주입 패턴 적용

### ~~C6. SQLAlchemy 쿼리 스타일 불일치~~ -- ✅ 수정 완료

- **수정일**: 2026-02-13
- **수정 내용**:
  - 15건의 `db.query()` 레거시 패턴 → `select()` 2.0 스타일 변환
  - 대상 파일: `companies/service.py`, `histories/service.py`, `schedules/service.py`, `users/service.py`, `common/deps.py`, `auth/router.py`
  - Backend 전체 `db.query()` 잔존: **0건**

---

## HIGH (8건) -- ✅ 전체 수정 완료

### ~~H1. Nginx 보안 헤더 누락~~ -- ✅ 수정 완료
- **수정일**: 2026-02-13
- **수정 내용**: `nginx.conf`에 `X-Frame-Options: DENY`, `X-Content-Type-Options: nosniff`, `X-XSS-Protection`, `Referrer-Policy`, `CSP` 헤더 추가

### ~~H2. Nginx 레이트 리밋 없음~~ -- ✅ 수정 완료
- **수정일**: 2026-02-13
- **수정 내용**: `nginx.conf`에 `limit_req_zone` 설정 (api: 10r/s burst=20, rag: 5r/s burst=10)

### ~~H3. 토큰 블랙리스트 세션 누수~~ -- ✅ 수정 완료
- **수정일**: 2026-02-13
- **수정 내용**: `token_blacklist.py` 3개 함수에 `db: Session` 파라미터 추가, `SessionLocal()` 직접 생성 제거, `auth/router.py`에서 `Depends(get_db)` 세션 전달

### ~~H4. 입력 유효성 검증 미흡~~ -- ✅ 수정 완료
- **수정일**: 2026-02-13
- **수정 내용**: `companies/schemas.py`에 사업자번호 `@field_validator` 추가, `schedules/schemas.py`에 `end_date >= start_date` `@model_validator` 추가

### ~~H5. RAG 문서 병합 무제한~~ -- ✅ 수정 완료
- **수정일**: 2026-02-13
- **수정 내용**: `retrieval_agent.py`에 법률 보충 문서 병합 후 `max_retrieval_docs` 초과 시 슬라이싱

### ~~H6. RAG 도메인 분류기 레이스 컨디션~~ -- ✅ 수정 완료
- **수정일**: 2026-02-13
- **수정 내용**: `domain_classifier.py`에 `threading.Lock()` + double-check 패턴 적용

### ~~H7. ChromaDB 재시도 로직 없음~~ -- ✅ 수정 완료
- **수정일**: 2026-02-13
- **수정 내용**: `chroma.py`의 `_get_client()`, `similarity_search()`에 `@retry(stop=stop_after_attempt(3), wait=wait_exponential(min=1, max=10))` 적용

### ~~H8. 환경변수 유효성 검증 없음~~ -- ✅ 수정 완료
- **수정일**: 2026-02-13
- **수정 내용**: `rag/utils/config/settings.py`에 `mysql_host`, `mysql_database` 필수 검증 + VectorDB 디렉토리 경고

---

## MEDIUM (10건) -- 8건 수정 완료

### ~~M1. 프론트엔드 console.log~~ -- ✅ 수정 완료
- **수정일**: 2026-02-13
- **수정 내용**: `CompanyForm.tsx` console.log 삭제, `vite.config.ts`에 production 모드 `esbuild.drop: ['console', 'debugger']` 설정

### ~~M2. Docker RAG --reload 누락~~ -- ✅ 수정 완료
- **수정일**: 2026-02-13
- **수정 내용**: `docker-compose.local.yaml` RAG command에 `--reload` 추가

### ~~M3. 하드코딩된 설정값~~ -- ✅ 수정 완료
- **수정일**: 2026-02-13
- **수정 내용**: `admin/service.py`의 `RAG_SERVICE_URL` → `backend/config/settings.py`의 `Settings.RAG_SERVICE_URL` 필드로 이관

### ~~M4. RAG 매직 넘버~~ -- ✅ 수정 완료
- **수정일**: 2026-02-13
- **수정 내용**: `retrieval_agent.py`의 `+3` → `settings.retry_k_increment`, `k=3` → `settings.cross_domain_k`, `max(2, ...)` → `settings.min_domain_k`

### ~~M5. 불완전한 토큰 트래킹~~ -- ✅ 수정 완료
- **수정일**: 2026-02-13
- **수정 내용**: `rag/main.py`의 `/api/documents/contract`, `/api/documents/business-plan`에 `RequestTokenTracker` 적용

### ~~M6. 헬스체크 불일치~~ -- ✅ 수정 완료
- **수정일**: 2026-02-13
- **수정 내용**: `docker-compose.yaml`, `docker-compose.local.yaml`에 Backend, Frontend 헬스체크 추가

### ~~M7. React 글로벌 에러 바운더리 없음~~ -- ✅ 수정 완료
- **수정일**: 2026-02-13
- **수정 내용**: `ErrorBoundary.tsx` 생성 + `App.tsx`에 `<ErrorBoundary>` 래핑

### M8. 게스트 모드 우회 가능 -- ⏳ 미수정
- **위치**: Frontend - localStorage 기반 메시지 카운터
- **조치**: 서버 사이드 IP 기반 레이트 리밋 추가

### ~~M9. 감사 로깅 없음~~ -- ✅ 수정 완료
- **수정일**: 2026-02-13
- **수정 내용**: `backend/main.py`에 `AuditLoggingMiddleware` 추가 (POST/PUT/DELETE/PATCH 요청의 req_id, method, path, status, ip, duration 구조화 로깅)

### ~~M10. CORS 프로덕션 설정 확인 필요~~ -- ✅ 수정 완료
- **수정일**: 2026-02-13
- **수정 내용**: `backend/config/settings.py`에 `@model_validator(mode="after")`로 production 환경 CORS localhost 포함 시 경고

---

## LOW (7건) -- 5건 수정/확인 완료

### L1. 문서 불일치 -- ✅ 확인 완료 (이미 정상)
- Root `CLAUDE.md`에 스키마명은 `bizi_db`로 정상 확인됨

### ~~L2. 에러 메시지 언어 불일치~~ -- ✅ 수정 완료
- **수정일**: 2026-02-13
- **수정 내용**: `auth/router.py`의 영어 에러 메시지 전체 한국어 변환

### ~~L3. TanStack Query 미사용~~ -- ✅ 수정 완료
- **수정일**: 2026-02-13
- **수정 내용**: `frontend/CLAUDE.md`의 TanStack Query 참조를 실제 상태(미사용, Zustand+axios)로 수정

### ~~L4. 데드 코드~~ -- ✅ 수정 완료
- **수정일**: 2026-02-13
- **수정 내용**: `authStore.ts`에서 `localStorage.removeItem('accessToken')` 삭제

### L5. Dockerfile 빌드 도구 미정리 -- ✅ 확인 완료 (이미 최적화)
- 탐색 결과 RAG Dockerfile에서 이미 빌드 도구 정리 완료

### L6. Backend 테스트 디렉토리 없음 -- ⏳ 미수정 (별도 태스크)
- `backend/tests/` 테스트 스위트 작성 필요 (수일 소요)

### L7. Frontend 컴포넌트 단위 테스트 없음 -- ⏳ 미수정 (별도 태스크)
- Vitest 단위 테스트 설정 필요 (수일 소요)

---

## 긍정적 발견 사항

| 항목 | 평가 |
|------|------|
| TypeScript strict 모드 | `any` 타입 0건, 완벽한 타입 안전성 |
| HttpOnly JWT 쿠키 | 프론트엔드에서 토큰 접근 불가 |
| CSRF 미들웨어 | `X-Requested-With` 헤더 검증 |
| SSE 스트리밍 프론트엔드 | `requestAnimationFrame` 기반 60fps 스로틀링 (우수) |
| 멀티세션 채팅 | Zustand persist로 세션 영속화 |
| Soft Delete | 전체 엔티티 `use_yn` 플래그 사용 |
| 벡터 검색 품질 | Hybrid Search + Reranking + Adaptive Strategy |
| 모듈화된 에이전트 | LangGraph 기반 5단계 파이프라인 |
| 상수 중앙 관리 | `constants.ts`에 모든 상수 집중 |
| Pydantic v2 스키마 | `ConfigDict(from_attributes=True)` 일관 적용 |
| Nginx SSE 설정 | `proxy_buffering off` + `X-Accel-Buffering: no` 헤더 (수정 완료) |
| **Backend 서비스 레이어** | **전 모듈 service.py 패턴 적용 (수정 완료)** |
| **SQLAlchemy 2.0 통일** | **Backend 전체 `select()` 스타일 (수정 완료)** |
| **프롬프트 인젝션 방어** | **sanitizer + prompt guard 적용 (수정 완료)** |
| **SSH 터널 보안** | **`StrictHostKeyChecking=accept-new` + 호스트 키 영속화 (수정 완료)** |
| **LLM 도메인 분류** | **`.env` 토글로 LLM 1차 분류기 전환 가능 (신규 구현)** |

---

## 수정 로드맵 (갱신)

### ~~Phase 0: 긴급 수정~~ -- ✅ 완료
| # | 작업 | 상태 |
|---|------|------|
| 1 | SSE 스트리밍 수정 (C1) | ✅ 완료 |
| 2 | SSH MITM 취약점 수정 (C3) | ✅ 완료 |
| 3 | 프롬프트 인젝션 방어 (C4) | ✅ 완료 |
| 4 | Backend 서비스 레이어 추가 (C5) | ✅ 완료 |
| 5 | SQLAlchemy 2.0 통일 (C6) | ✅ 완료 |
| 6 | LLM 도메인 분류 .env 토글 연결 | ✅ 완료 |

### ~~Phase 1: 보안 강화~~ -- ✅ 완료 (C2 제외)
| # | 작업 | 상태 |
|---|------|------|
| 1 | **TLS/HTTPS 설정** (C2) - SSL 인증서 필요 | ⏳ 미수정 |
| 2 | ~~Nginx 보안 헤더 추가 (H1)~~ | ✅ 완료 |
| 3 | ~~Nginx 레이트 리밋 (H2)~~ | ✅ 완료 |
| 4 | ~~토큰 블랙리스트 DI 전환 (H3)~~ | ✅ 완료 |
| 5 | ~~입력 유효성 검증 추가 (H4)~~ | ✅ 완료 |

### ~~Phase 2: 안정성 개선~~ -- ✅ 전체 완료
| # | 작업 | 상태 |
|---|------|------|
| 1 | ~~RAG 문서 병합 제한 (H5)~~ | ✅ 완료 |
| 2 | ~~도메인 분류기 Lock (H6)~~ | ✅ 완료 |
| 3 | ~~ChromaDB 재시도 로직 (H7)~~ | ✅ 완료 |
| 4 | ~~환경변수 검증 (H8)~~ | ✅ 완료 |
| 5 | ~~Docker 헬스체크 통일 (M6)~~ | ✅ 완료 |
| 6 | ~~에러 바운더리 (M7)~~ | ✅ 완료 |

### ~~Phase 3: 코드 품질~~ -- 부분 완료 (테스트 제외)
| # | 작업 | 상태 |
|---|------|------|
| 1 | Backend 단위/통합 테스트 작성 | ⏳ 미수정 (별도 태스크) |
| 2 | Frontend Vitest 단위 테스트 설정 | ⏳ 미수정 (별도 태스크) |
| 3 | ~~console.log 정리 (M1)~~ | ✅ 완료 |
| 4 | ~~Docker 프로덕션 빌드 (M2)~~ | ✅ 완료 |
| 5 | ~~하드코딩 설정 중앙화 (M3, M4)~~ | ✅ 완료 |
| 6 | ~~감사 로깅 (M9)~~ | ✅ 완료 |

### Phase 4: 기능 확장 (잔여)
| # | 작업 | 우선순위 | 예상 시간 |
|---|------|---------|----------|
| 1 | **TLS/HTTPS 설정** (C2) | CRITICAL | 4h |
| 2 | File/Announce 관리 API 구현 | MEDIUM | 2-3d |
| 3 | 선제적 알림 시스템 (D-7, D-3) | MEDIUM | 2-3d |
| 4 | Google OAuth2 실 연동 완료 | MEDIUM | 1d |
| 5 | Backend/Frontend 테스트 스위트 작성 | MEDIUM | 5-8d |
| 6 | 데이터 갱신 자동화 (크롤링 스케줄러) | LOW | 2-3d |
| 7 | 게스트 모드 우회 방지 (M8) | LOW | 1d |

---

## 변경 이력

| 날짜 | 변경 내용 |
|------|----------|
| 2026-02-13 | 초기 감사 보고서 작성 (31건 발견) |
| 2026-02-13 | CRITICAL 5건 수정 완료 (C1, C3, C4, C5, C6). LLM 도메인 분류 .env 토글 연결 |
| 2026-02-13 | HIGH 8건 전체 수정 (H1-H8), MEDIUM 8건 수정 (M1-M7, M9-M10), LOW 4건 수정 (L2-L4), SSE 미들웨어 ASGI 전환 |
| 2026-02-13 | 로드맵 Phase 1-3 완료 상태 갱신, 발견 요약 27/31건 수정 완료로 업데이트. 커밋 `5486466` 기준 |

---

## 분석 방법론
- **Explore 에이전트 3개**: Backend / RAG / Frontend+Infra 병렬 탐색
- **Security Reviewer**: 보안 심층 감사 (24개 보안 항목)
- **Architecture Planner**: 구조적 이슈 분석 + 수정 로드맵 설계
- **Streaming 전문 탐색**: Nginx + RAG SSE + Frontend fetch 전체 경로 추적
- **fastapi-architect**: C5 서비스 레이어 + C6 SQLAlchemy 2.0 변환
- **rag-specialist**: C4 프롬프트 인젝션 방어 + LLM 도메인 분류 연결
