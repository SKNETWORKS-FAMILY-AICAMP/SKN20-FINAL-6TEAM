# Bizi 프로젝트 종합 상태 보고서

> 작성일: 2026-02-13
> 최종 갱신: 2026-02-13 (CRITICAL 수정 + LLM 도메인 분류 반영)
> 분석 방법: PM Orchestrator가 각 서비스별 전문 분석을 종합 수행
> 분석 대상 커밋: `8761667` (main branch)

---

## 1. 각 서비스별 현황

### 1.1 Backend (FastAPI) -- 완성도: 85% → 90% ↑

**구현 완료된 기능:**
| 모듈 | 파일 | 기능 | 상태 |
|------|------|------|------|
| `auth/` | router.py, services.py, schemas.py, token_blacklist.py | Google OAuth2, 테스트 로그인, JWT(HttpOnly Cookie), 로그아웃+블랙리스트, 토큰 리프레시(Rotation) | 완료 |
| `users/` | router.py, **service.py**, schemas.py | 사용자 프로필 조회/수정 | 완료 |
| `companies/` | router.py, **service.py**, schemas.py | 기업 프로필 CRUD, 사업자등록증 업로드, 대표기업 설정 | 완료 |
| `histories/` | router.py, **service.py**, schemas.py | 상담 이력 저장/조회, 대화 연결(parent_history_id), 벌크 저장 | 완료 |
| `schedules/` | router.py, **service.py**, schemas.py | 일정 CRUD, 기업별 일정 조회 | 완료 |
| `admin/` | router.py, service.py, schemas.py | 서버 상태 모니터링, 상담 이력 관리(필터/페이지네이션), 평가 통계 | 완료 |
| `common/` | models.py, deps.py | SQLAlchemy 모델 8개, JWT 인증 의존성 | 완료 |
| `config/` | settings.py, database.py | Pydantic BaseSettings, DB 연결 풀 설정 | 완료 |

**2026-02-13 수정 사항:**
- ~~서비스 레이어 부재~~: **전 모듈 service.py 패턴 적용 완료** (C5)
- ~~SQLAlchemy 쿼리 스타일 불일치~~: **전체 `select()` 2.0 스타일 통일 완료** (C6, auth 포함 15건 변환, 잔존 0건)

**미완성/개선 필요 기능:**
- **파일 관리 API 미구현**: DB에 `file` 테이블 정의되어 있으나 전용 라우터/서비스 없음
- **공고(Announce) 관리 API 미구현**: DB에 `announce` 테이블 정의되어 있으나 전용 라우터/서비스 없음
- **Google OAuth2 실 연동 미완료**: `.env.example`에 "미구현 - 테스트 로그인 사용" 명시
- **입력 검증 미흡**: 사업자등록번호 형식 검증 없음, 일정 날짜 범위(end > start) 검증 없음
- **토큰 블랙리스트 세션 관리**: `SessionLocal()` 직접 생성 → DI 전환 필요

**코드 품질:**
- Python 타입 힌트: 대부분 적용됨
- Pydantic v2 스키마: `ConfigDict(from_attributes=True)` 일관 적용
- CSRF 미들웨어: `CSRFMiddleware` 구현됨
- Rate Limiting: `slowapi` 적용 (인증 엔드포인트)
- 커넥션 풀: `pool_pre_ping=True`, `pool_recycle=1800` 설정됨
- **서비스 레이어**: 전 모듈 적용 (admin 패턴 통일)
- **쿼리 스타일**: SQLAlchemy 2.0 `select()` 100% 통일

---

### 1.2 RAG Service (LangChain/LangGraph) -- 완성도: 95% → 97% ↑

**구현 완료된 기능:**
| 컴포넌트 | 파일 | 기능 | 상태 |
|---------|------|------|------|
| MainRouter | agents/router.py | LangGraph 5단계 파이프라인 (분류-분해-검색-생성-평가) | 완료 |
| 도메인 에이전트 4개 | agents/{startup_funding,finance_tax,hr_labor,legal}.py | 전문 도메인 상담 | 완료 |
| 평가 에이전트 | agents/evaluator.py | LLM 기반 답변 품질 평가 | 완료 |
| Action Executor | agents/executor.py | 근로계약서, 사업계획서 등 문서 생성 | 완료 |
| 검색 에이전트 | agents/retrieval_agent.py | 적응형 검색, 단계적 재시도, 문서 병합 | 완료 |
| 생성 에이전트 | agents/generator.py | 단일/복수 도메인 통합 생성, 스트리밍 지원 | 완료 |
| Hybrid Search | utils/search.py | BM25 + Vector + RRF 앙상블 | 완료 |
| Reranker | utils/reranker.py | Cross-encoder 기반 재정렬 | 완료 |
| 도메인 분류기 | utils/domain_classifier.py | 벡터 유사도 + 키워드 매칭 + **LLM 분류** | 완료 |
| 질문 분해기 | utils/question_decomposer.py | 복합 질문 도메인별 분해 | 완료 |
| 캐시 | utils/cache.py | LRU 캐시 (500건, 1시간 TTL) | 완료 |
| 법률 보충 검색 | utils/legal_supplement.py | 타 도메인 답변 시 법률 DB 보충 검색 | 완료 |
| RAGAS 평가 | evaluation/ragas_evaluator.py | 정량 품질 평가 (faithfulness, relevancy) | 완료 |
| 메트릭/미들웨어 | utils/middleware.py | Rate Limiting, 메트릭 수집 | 완료 |
| 토큰 추적 | utils/token_tracker.py | OpenAI API 토큰 사용량/비용 추적 | 완료 |
| 민감정보 마스킹 | utils/logging_utils.py | 로그 내 개인정보 마스킹 | 완료 |
| 도메인 설정 DB | utils/config/domain_config.py, domain_data.py | MySQL 기반 도메인 키워드/규칙 관리 | 완료 |
| 벡터DB 빌더 | vectorstores/build_vectordb.py | JSONL -> ChromaDB 컬렉션 빌드 | 완료 |
| SSE 스트리밍 | main.py `/api/chat/stream` | 실시간 토큰 스트리밍 | 완료 |
| **프롬프트 인젝션 방어** | **utils/sanitizer.py** | **24개 패턴 탐지 + 마스킹** | **신규** |

**2026-02-13 수정/추가 사항:**
- **LLM 도메인 분류 활성화**: `classify()` 메서드에 LLM 분기 연결. `.env`에서 `ENABLE_LLM_DOMAIN_CLASSIFICATION=true`로 토글 가능. LLM 실패 시 자동 fallback. 비교 로깅으로 일치율 모니터링.
- **프롬프트 인젝션 방어**: `sanitizer.py` 신규 생성 + 5개 도메인 프롬프트에 가드 추가 + 파이프라인 진입점에 sanitizer 적용
- **SSE 헤더 수정**: `StreamingResponse`에 `X-Accel-Buffering: no` 등 헤더 추가

**코드 품질:**
- 프롬프트 중앙 관리: `utils/prompts.py` + **인젝션 가드 적용**
- 설정 중앙 관리: `utils/config/settings.py` (Pydantic BaseSettings, 40+ 환경변수)
- 싱글톤 패턴 일관: `get_settings()`, `get_reranker()`, `get_domain_classifier()` 등
- 지연 로딩: 도메인 분류기, 질문 분해기, RAGAS 평가기 모두 `@property` 지연 로딩
- 에러 핸들링: try-except + fallback 메시지 패턴 일관 적용
- 비동기 지원: `asyncio.to_thread()` + `asyncio.gather()` 병렬 처리

---

### 1.3 Frontend (React + Vite + TypeScript) -- 완성도: 85%

(변경 없음 - 이전 보고서와 동일)

**구현 완료된 기능:**
| 페이지/컴포넌트 | 파일 | 기능 | 상태 |
|---------------|------|------|------|
| LoginPage | pages/LoginPage.tsx | Google OAuth2 + 테스트 로그인 | 완료 |
| MainPage (채팅) | pages/MainPage.tsx | 채팅 UI, SSE 스트리밍, 마크다운 렌더링, 시즌 추천 질문 | 완료 |
| CompanyPage | pages/CompanyPage.tsx | 기업 프로필 CRUD, 사업자등록증 업로드 | 완료 |
| SchedulePage | pages/SchedulePage.tsx | FullCalendar 캘린더, 일정 CRUD | 완료 |
| AdminDashboardPage | pages/AdminDashboardPage.tsx | 서버 상태 모니터링, 사용자 통계 | 완료 |
| AdminLogPage | pages/AdminLogPage.tsx | 상담 이력 조회, 평가 필터링 | 완료 |
| UsageGuidePage | pages/UsageGuidePage.tsx | 서비스 이용 가이드 | 완료 |
| Sidebar | components/layout/Sidebar.tsx | 네비게이션, 채팅 이력, 설정 | 완료 |
| ChatHistoryPanel | components/layout/ChatHistoryPanel.tsx | 채팅 세션 목록/전환/삭제 | 완료 |
| ProfileDialog | components/profile/ProfileDialog.tsx | 사용자 프로필 수정 (모달) | 완료 |
| CompanyForm | components/company/CompanyForm.tsx | 기업 등록/수정 폼 | 완료 |
| CompanyDashboard | components/company/CompanyDashboard.tsx | 기업 대시보드 | 완료 |
| RegionSelect | components/common/RegionSelect.tsx | 시도/시군구 2단 선택 | 완료 |
| ProtectedRoute | components/common/ProtectedRoute.tsx | 인증/관리자 라우트 가드 | 완료 |
| NotificationBell | components/layout/NotificationBell.tsx | 알림 드롭다운 | 완료 |
| ResponseProgress | components/chat/ResponseProgress.tsx | 응답 생성 중 진행률 | 완료 |

**미완성/개선 필요:**
- **단위 테스트 없음**: Vitest 미설치, 컴포넌트 테스트 파일 0건
- **TanStack Query 미사용**: CLAUDE.md에 언급되나 실제 미사용 (Zustand + 직접 axios 호출)
- **글로벌 에러 바운더리 없음**: 예외 발생 시 흰 화면
- **console.log 잔존**: 10+ 건의 디버그 로그 잔존
- **선제적 알림 시스템 미구현**: NotificationBell UI는 있으나 D-7/D-3 알림 로직 없음

---

### 1.4 Scripts (크롤링/전처리) -- 완성도: 90%

(변경 없음 - 이전 보고서와 동일)

---

### 1.5 Data -- 완성도: 60%

(변경 없음 - 이전 보고서와 동일)

---

### 1.6 Infra (Docker/Nginx) -- 완성도: 80% → 85% ↑

**2026-02-13 수정 사항:**
- **SSE 스트리밍**: `rag/main.py`에 `X-Accel-Buffering: no` 헤더 추가, `nginx.conf`에 `chunked_transfer_encoding on` 추가
- **SSH 터널 보안**: `StrictHostKeyChecking=accept-new` + `ssh-known-hosts` 볼륨 영속화

**Nginx 설정:**
- 리버스 프록시: `/api/*` -> backend:8000, `/rag/*` -> rag:8001, `/*` -> frontend:5173
- SSE 지원: `proxy_buffering off`, `proxy_cache off`, `proxy_read_timeout 300s`, **`chunked_transfer_encoding on`** ✅
- WebSocket (HMR): `Upgrade`, `Connection "upgrade"` 헤더 설정
- `client_max_body_size 10M`

**미비 사항:**
- **TLS/HTTPS 미설정** (HTTP 80만) — CRITICAL, SSL 인증서 필요
- 보안 헤더 누락 (X-Frame-Options, CSP 등)
- Nginx 레이트 리밋 없음
- 프로덕션 빌드 구성 없음 (전체 dev 모드)
- backend, frontend에 Docker 헬스체크 없음

---

## 2~5. 아키텍처 / DB / RAG / 인프라 분석

(기본 구조는 변경 없음 - 이전 보고서 참조)

**주요 변경점:**
- **도메인 분류기**: 벡터 유사도 + 키워드 매칭 → `.env` 토글로 LLM 1차 분류 전환 가능
- **Backend 쿼리**: 전체 SQLAlchemy 2.0 `select()` 스타일 통일
- **서비스 구조**: 전 모듈 Router → Service → DB 3계층 아키텍처 적용

### 4.3 품질 기능 활성화 상태 (갱신)

| 기능 | 환경변수 | 기본값 | 구현 상태 |
|------|---------|--------|----------|
| Hybrid Search (BM25+Vector+RRF) | ENABLE_HYBRID_SEARCH | true | 완료 |
| Cross-encoder Re-ranking | ENABLE_RERANKING | true | 완료 |
| 적응형 검색 모드 | ENABLE_ADAPTIVE_SEARCH | true | 완료 |
| 고정 문서 제한 | ENABLE_FIXED_DOC_LIMIT | true | 완료 |
| Cross-Domain Rerank | ENABLE_CROSS_DOMAIN_RERANK | true | 완료 |
| 도메인 외 질문 거부 | ENABLE_DOMAIN_REJECTION | true | 완료 |
| 벡터 도메인 분류 | ENABLE_VECTOR_DOMAIN_CLASSIFICATION | true | 완료 |
| **LLM 도메인 분류** | ENABLE_LLM_DOMAIN_CLASSIFICATION | false | **완료 (1차 분류기 + fallback + 비교 로깅)** |
| LLM 답변 평가 | ENABLE_LLM_EVALUATION | true | 완료 |
| RAGAS 정량 평가 | ENABLE_RAGAS_EVALUATION | false | 완료 (옵션) |
| 평가 후 재시도 | ENABLE_POST_EVAL_RETRY | true | 완료 |
| 단계적 재시도 | ENABLE_GRADUATED_RETRY | true | 완료 |
| 법률 보충 검색 | ENABLE_LEGAL_SUPPLEMENT | true | 완료 |
| 응답 캐시 | ENABLE_RESPONSE_CACHE | true | 완료 |
| Rate Limiting | ENABLE_RATE_LIMIT | true | 완료 |
| Fallback 응답 | ENABLE_FALLBACK | true | 완료 |
| 액션 인식 생성 | ENABLE_ACTION_AWARE_GENERATION | true | 완료 |
| **프롬프트 인젝션 방어** | (항상 활성화) | - | **완료 (sanitizer + prompt guard)** |

---

## 6. 테스트 분석

(변경 없음 - Backend/Frontend 테스트 미존재, RAG 17파일 양호)

---

## 7. 문서화 분석

### 7.3 .claude/rules/ 정합성 (갱신)

| 규칙 파일 | 준수 상태 | 비고 |
|----------|----------|------|
| coding-style.md | 80% | Python 타입힌트 대부분 적용, TS strict 완벽 |
| git-workflow.md | 90% | 커밋 메시지 컨벤션 준수, Co-Author 포함 |
| testing.md | 30% | **규칙은 상세하나 Backend/Frontend 테스트 미존재** |
| security.md | **85%** ↑ | HttpOnly JWT, CSRF 적용. **SSH accept-new, 프롬프트 인젝션 방어 적용**. TLS 미적용 |
| patterns.md | **95%** ↑ | Pydantic, Zustand, Router 패턴 준수. **Service Layer 패턴 전 모듈 적용** |
| agents.md | 95% | 에이전트 라우팅 규칙 정확 |
| performance.md | 80% | 모델 선택 전략, 지연 로딩 적용 |

---

## 8. 개선 필요 사항 (갱신)

### ~~P0 -- 즉시 수정~~ ✅ 완료
- ~~SSE 스트리밍 헤더~~ → 완료
- ~~SSH StrictHostKeyChecking~~ → 완료
- ~~프롬프트 인젝션 방어~~ → 완료
- ~~서비스 레이어 추가~~ → 완료
- ~~SQLAlchemy 2.0 통일~~ → 완료

### P0 -- 남은 CRITICAL (인프라)

| # | 항목 | 영향 범위 | 필요 조치 |
|---|------|---------|----------|
| 1 | **TLS/HTTPS 설정** (C2) | Infra | SSL 인증서 발급 → nginx.conf SSL 설정 → docker-compose 443 포트 → COOKIE_SECURE=True |

### P1 -- 높은 우선순위 (다음 단계)

| # | 항목 | 영향 범위 | 예상 작업량 |
|---|------|---------|-----------|
| 1 | Nginx 보안 헤더 추가 (H1) | Infra | 2h |
| 2 | Nginx 레이트 리밋 (H2) | Infra | 3h |
| 3 | 토큰 블랙리스트 DI 전환 (H3) | Backend | 2h |
| 4 | 입력 유효성 검증 강화 (H4) | Backend | 4h |
| 5 | RAG 문서 병합 제한 (H5) | RAG | 2h |
| 6 | 도메인 분류기 Lock (H6) | RAG | 2h |
| 7 | ChromaDB 재시도 로직 (H7) | RAG | 4h |
| 8 | 환경변수 검증 (H8) | Backend+RAG | 3h |
| 9 | Frontend 에러 바운더리 (M7) | Frontend | 2h |

### P2 -- 중간 우선순위

| # | 항목 | 영향 범위 | 예상 작업량 |
|---|------|---------|-----------|
| 1 | Backend 단위/통합 테스트 작성 | Backend | 3-5d |
| 2 | Frontend Vitest 단위 테스트 설정 | Frontend | 2-3d |
| 3 | Docker 프로덕션 빌드 (M2) | Infra | 4h |
| 4 | File/Announce 관리 API 구현 | Backend | 2-3d |
| 5 | 선제적 알림 시스템 (D-7, D-3) | Frontend+Backend | 2-3d |
| 6 | console.log 정리 (M1) | Frontend | 1h |
| 7 | Google OAuth2 실 연동 완료 | Backend | 1d |
| 8 | 감사 로깅 미들웨어 (M9) | Backend | 4h |

### P3 -- 낮은 우선순위

| # | 항목 | 영향 범위 | 예상 작업량 |
|---|------|---------|-----------|
| 1 | 데이터 갱신 자동화 (크롤링 스케줄러) | Scripts | 2-3d |
| 2 | RAG 매직 넘버 상수화 (M4) | RAG | 2h |
| 3 | Dockerfile 최적화 (multi-stage) | Infra | 2h |
| 4 | Nginx gzip 압축 설정 | Infra | 1h |
| 5 | 에러 메시지 언어 통일 (L2) | Backend | 2h |
| 6 | 데드 코드 제거 (L4) | Frontend | 0.5h |

---

## 종합 평가 (갱신)

### 프로젝트 성숙도 점수

| 영역 | 이전 | 현재 | 변동 | 판단 근거 |
|------|------|------|------|----------|
| 아키텍처 설계 | 9/10 | **9/10** | - | 마이크로서비스 구조, 관심사 분리, 명확한 통신 경로 |
| Backend 구현 | 7/10 | **8/10** | **↑1** | **서비스 레이어 전 모듈 적용, SQLAlchemy 2.0 통일** |
| RAG 시스템 | 9/10 | **9.5/10** | **↑0.5** | **LLM 도메인 분류 토글, 프롬프트 인젝션 방어, SSE 헤더 수정** |
| Frontend 구현 | 8/10 | **8/10** | - | 기능 완성도 높음, 타입 안전성 우수. 테스트/에러 처리 부족 |
| 인프라 | 6/10 | **6.5/10** | **↑0.5** | **SSH 보안 강화, SSE Nginx 설정 완료**. TLS 미적용 |
| 테스트 | 4/10 | **4/10** | - | RAG만 양호, Backend/Frontend 테스트 전무 |
| 문서화 | 9/10 | **9/10** | - | 매우 상세한 CLAUDE.md, ARCHITECTURE.md, 규칙 체계 |
| 보안 | 6/10 | **7.5/10** | **↑1.5** | **프롬프트 인젝션 방어, SSH accept-new 적용**. TLS 미적용 |
| **종합** | **7.3/10** | **7.8/10** | **↑0.5** | **CRITICAL 5건 해결로 프로덕션 준비도 향상. TLS + 테스트가 주요 잔여 과제** |

### 핵심 강점
1. RAG 시스템의 높은 완성도 (5단계 파이프라인, 20+ 설정 가능 품질 기능)
2. TypeScript strict 모드 완벽 준수 (any 0건)
3. HttpOnly JWT + CSRF 미들웨어의 견고한 인증 아키텍처
4. SSE 기반 실시간 스트리밍 채팅
5. 매우 상세한 문서화 체계 (CLAUDE.md, ARCHITECTURE.md, rules/)
6. **Backend 전 모듈 서비스 레이어 + SQLAlchemy 2.0 통일** (신규)
7. **프롬프트 인젝션 방어 체계** (신규)
8. **LLM 도메인 분류 .env 토글 전환** (신규)

### 핵심 약점 (잔여)
1. **TLS/HTTPS 미적용** — 프로덕션 배포의 최대 블로커
2. Backend/Frontend 테스트 전무 (규칙은 정의되어 있으나 미이행)
3. 프로덕션 빌드/배포 파이프라인 미구성
4. Nginx 보안 헤더/레이트 리밋 미설정

---

## 변경 이력

| 날짜 | 변경 내용 |
|------|----------|
| 2026-02-13 | 초기 종합 상태 보고서 작성 (성숙도 7.3/10) |
| 2026-02-13 | CRITICAL 5건 수정 + LLM 도메인 분류 연결 반영 (성숙도 7.8/10) |
