# Bizi 프로젝트 구조 감사 보고서

> 작성일: 2026-02-13
> 최종 갱신: 2026-02-13 (CRITICAL 수정 반영)
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
| HIGH | 8건 | 0건 | 8건 |
| MEDIUM | 10건 | 0건 | 10건 |
| LOW | 7건 | 0건 | 7건 |
| **합계** | **31건** | **5건** | **26건** |

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

## HIGH (8건) -- 미수정

### H1. Nginx 보안 헤더 누락
- **위치**: `nginx.conf`
- **누락**: `X-Frame-Options`, `X-Content-Type-Options`, `CSP`, `Strict-Transport-Security`
- **조치**: 보안 헤더 일괄 추가

### H2. Nginx 레이트 리밋 없음
- **위치**: `nginx.conf`
- **위험**: RAG API (비용 발생), 파일 업로드, 인증 엔드포인트에 전역 제한 없음
- **조치**: `limit_req_zone` 설정 (API: 10r/s, RAG: 5r/s)

### H3. 토큰 블랙리스트 세션 누수
- **위치**: `backend/apps/auth/token_blacklist.py`
- **위험**: `SessionLocal()` 직접 생성 → 커넥션 풀 고갈 가능
- **조치**: `Depends(get_db)` 의존성 주입으로 전환

### H4. 입력 유효성 검증 미흡
- **위치**: Backend 스키마 전반
- **미비 항목**: 사업자등록번호 형식, 날짜 범위(end > start), 생년월일 범위
- **조치**: Pydantic `field_validator` 추가

### H5. RAG 문서 병합 무제한
- **위치**: `rag/agents/retrieval_agent.py` - 법률 보충 검색 후 병합
- **위험**: 문서 수 초과 → LLM 컨텍스트 윈도우 오버플로 + 비용 증가
- **조치**: 병합 후 `max_total` 제한 적용

### H6. RAG 도메인 분류기 레이스 컨디션
- **위치**: `rag/utils/domain_classifier.py` - `_DOMAIN_VECTORS_CACHE`
- **위험**: 동시 요청 시 캐시 초기화 경쟁
- **조치**: `threading.Lock()` 또는 `asyncio.Lock()` 적용

### H7. ChromaDB 재시도 로직 없음
- **위치**: `rag/vectorstores/chroma.py`
- **위험**: 연결 실패, 타임아웃 시 즉시 에러 → 서비스 중단
- **조치**: `tenacity` 라이브러리로 지수 백오프 재시도

### H8. 환경변수 유효성 검증 없음
- **위치**: `rag/main.py`, `backend/config/settings.py`
- **위험**: 잘못된 `OPENAI_API_KEY`, DB 접속정보로 런타임 에러
- **조치**: 앱 시작 시 Pydantic `field_validator`로 포맷/접속 검증

---

## MEDIUM (10건) -- 미수정

### M1. 프론트엔드 console.log 10건
- **위치**: `useChat.ts`, `LoginPage.tsx`, `CompanyForm.tsx`, `AdminLogPage.tsx`, `AdminDashboardPage.tsx`, `SchedulePage.tsx`
- **조치**: Vite 빌드 시 `esbuild.drop: ['console']` 설정 또는 제거

### M2. Docker 전체 Dev 모드 실행
- **위치**: `docker-compose.yaml` - `--reload`, `npm run dev`
- **조치**: `docker-compose.prod.yaml` 분리 (multi-stage 빌드 + workers)

### M3. 하드코딩된 설정값
- **위치**: `admin/service.py:24` (`RAG_SERVICE_URL`)
- **조치**: `backend/config/settings.py`로 이관
- **참고**: `companies/router.py`의 `UPLOAD_DIR`은 C5 서비스 레이어 추가 시 `companies/service.py`로 이동 완료

### M4. RAG 매직 넘버
- **위치**: `retrieval_agent.py` - `k*3`, `+3`, `k=3`
- **조치**: `rag/utils/config/settings.py`에 명명된 상수로 추출

### M5. 불완전한 토큰 트래킹
- **위치**: RAG `/api/chat/stream`, `/api/documents/*`
- **조치**: 스트리밍/문서 생성 경로에도 `RequestTokenTracker` 적용

### M6. 헬스체크 불일치
- **위치**: `docker-compose.yaml` - ssh-tunnel, rag만 헬스체크 있음
- **조치**: backend, frontend에도 헬스체크 추가

### M7. React 글로벌 에러 바운더리 없음
- **위치**: Frontend `App.tsx`
- **조치**: `ErrorBoundary` 컴포넌트 추가 (흰 화면 방지)

### M8. 게스트 모드 우회 가능
- **위치**: Frontend - localStorage 기반 메시지 카운터
- **조치**: 서버 사이드 IP 기반 레이트 리밋 추가

### M9. 감사 로깅 없음
- **위치**: Backend 전체 - 관리자 액션, 로그인 실패, 민감 조회 추적 없음
- **조치**: 감사 로깅 미들웨어 추가

### M10. CORS 프로덕션 설정 확인 필요
- **위치**: `backend/main.py`, `rag/main.py`
- **조치**: `ENVIRONMENT=production`일 때 `allow_origins`를 도메인 단일 지정 확인

---

## LOW (7건) -- 미수정

### L1. 문서 불일치
- Root `CLAUDE.md`에 스키마명 `final_test` → 실제 코드는 `bizi_db`

### L2. 에러 메시지 언어 불일치
- auth: 영어 ("Not authenticated"), admin: 한국어 ("관리자 권한이 필요합니다")

### L3. TanStack Query 미사용
- 문서에 참조되나 실제 Zustand + axios 직접 사용

### L4. 데드 코드
- `authStore`에서 `localStorage.removeItem('accessToken')` (HttpOnly 쿠키 사용 중)

### L5. Dockerfile 빌드 도구 미정리
- RAG Dockerfile에 `build-essential` 설치 후 미제거 → 이미지 사이즈 증가

### L6. Backend 테스트 디렉토리 없음
- `backend/tests/` 미존재 (테스트 규칙은 문서화됨)

### L7. Frontend 컴포넌트 단위 테스트 없음
- E2E(Playwright)만 존재, Vitest 단위 테스트 없음

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

### Phase 1: 보안 강화 (다음 단계)
| # | 작업 | 우선순위 | 예상 시간 |
|---|------|---------|----------|
| 1 | **TLS/HTTPS 설정** (C2) - SSL 인증서 + nginx.conf 수정 | CRITICAL | 4h |
| 2 | Nginx 보안 헤더 추가 (H1) | HIGH | 2h |
| 3 | Nginx 레이트 리밋 (H2) | HIGH | 3h |
| 4 | 토큰 블랙리스트 DI 전환 (H3) | HIGH | 2h |
| 5 | 입력 유효성 검증 추가 (H4) | HIGH | 4h |

### Phase 2: 안정성 개선
| # | 작업 | 우선순위 | 예상 시간 |
|---|------|---------|----------|
| 1 | RAG 문서 병합 제한 (H5) | HIGH | 2h |
| 2 | 도메인 분류기 Lock (H6) | HIGH | 2h |
| 3 | ChromaDB 재시도 로직 (H7) | HIGH | 4h |
| 4 | 환경변수 검증 (H8) | HIGH | 3h |
| 5 | Docker 헬스체크 통일 (M6) | MEDIUM | 2h |
| 6 | 에러 바운더리 (M7) | MEDIUM | 2h |

### Phase 3: 코드 품질 & 테스트
| # | 작업 | 우선순위 | 예상 시간 |
|---|------|---------|----------|
| 1 | Backend 단위/통합 테스트 작성 | MEDIUM | 3-5d |
| 2 | Frontend Vitest 단위 테스트 설정 | MEDIUM | 2-3d |
| 3 | console.log 정리 (M1) | MEDIUM | 1h |
| 4 | Docker 프로덕션 빌드 (M2) | MEDIUM | 4h |
| 5 | 하드코딩 설정 중앙화 (M3, M4) | MEDIUM | 3h |
| 6 | 감사 로깅 (M9) | MEDIUM | 4h |

### Phase 4: 기능 확장 (점진적)
| # | 작업 | 우선순위 | 예상 시간 |
|---|------|---------|----------|
| 1 | File/Announce 관리 API 구현 | MEDIUM | 2-3d |
| 2 | 선제적 알림 시스템 (D-7, D-3) | MEDIUM | 2-3d |
| 3 | Google OAuth2 실 연동 완료 | MEDIUM | 1d |
| 4 | 데이터 갱신 자동화 (크롤링 스케줄러) | LOW | 2-3d |
| 5 | Dockerfile 최적화 (multi-stage) | LOW | 2h |
| 6 | Nginx gzip 압축 설정 | LOW | 1h |
| 7 | 에러 메시지 언어 통일 (L2) | LOW | 2h |
| 8 | 데드 코드 제거 (L4) | LOW | 0.5h |

---

## 변경 이력

| 날짜 | 변경 내용 |
|------|----------|
| 2026-02-13 | 초기 감사 보고서 작성 (31건 발견) |
| 2026-02-13 | CRITICAL 5건 수정 완료 (C1, C3, C4, C5, C6). LLM 도메인 분류 .env 토글 연결 |

---

## 분석 방법론
- **Explore 에이전트 3개**: Backend / RAG / Frontend+Infra 병렬 탐색
- **Security Reviewer**: 보안 심층 감사 (24개 보안 항목)
- **Architecture Planner**: 구조적 이슈 분석 + 수정 로드맵 설계
- **Streaming 전문 탐색**: Nginx + RAG SSE + Frontend fetch 전체 경로 추적
- **fastapi-architect**: C5 서비스 레이어 + C6 SQLAlchemy 2.0 변환
- **rag-specialist**: C4 프롬프트 인젝션 방어 + LLM 도메인 분류 연결
