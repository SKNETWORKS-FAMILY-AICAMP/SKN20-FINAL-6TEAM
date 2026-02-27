# 개발된 LLM 연동 웹 애플리케이션 산출물

- 프로젝트: Bizi (통합 창업/경영 상담 챗봇)
- 문서 유형: 개발 산출물
- 작성 기준: 현재 저장소 구현 코드 기준
- 작성일: 2026-02-27

---

## 산출물 목적

운영 모드 기준으로 벡터 데이터베이스(ChromaDB)와 LLM(Language Model)을 연동하여, 창업/세무/노무/법률 도메인에 대한 정보 검색 및 질의응답 시스템을 구현하고 운영 가능한 웹 애플리케이션 형태로 제공한다.

---

## 개요

### 목표

- 도메인 지식 기반의 정확한 질의응답 제공
- 검색 기반 응답(RAG)으로 환각(hallucination) 위험 최소화
- 사용자 프로필/기업 컨텍스트를 반영한 맞춤형 상담 제공
- 웹 UI, 인증, 일정/기업 관리, 알림을 포함한 실사용 가능 서비스 구현

### 주요 기능

- AI 상담: `/` 메인 채팅 화면에서 스트리밍 기반 답변 제공
- 멀티 도메인 RAG: 창업/지원사업, 재무/세무, 인사/노무, 법률
- 인증: Google OAuth2 + JWT(HttpOnly Cookie) 기반 세션 관리
- 기업 관리: 기업 등록/수정/대표 기업 설정 및 대시보드 조회
- 일정 관리: 캘린더/리스트 + 공고 일정 자동 등록/제거 + 메모 기능
- 알림 시스템: D-7, D-3 스케줄 알림 토스트 + 미확인 카운트 + 알림함
- 문서 생성: 근로계약서/사업계획서/범용 문서 생성·수정 API 연동
- 관리자 기능: 메트릭, 스케줄러 상태, 로그 조회

### 기술 스택

| 영역 | 기술 |
|---|---|
| Frontend | React 18, Vite, TypeScript, TailwindCSS, React Router, Zustand, Axios, TanStack Query, Material Tailwind |
| Backend | FastAPI, SQLAlchemy 2.0, PyJWT, Google OAuth2, SlowAPI(rate limit) |
| RAG Service | FastAPI, LangChain, LangGraph, OpenAI GPT-4o-mini, RAGAS(옵션) |
| Vector DB | ChromaDB |
| Database | MySQL 8.0 (`bizi_db`) |
| Infra | Docker Compose(로컬/통합 2모드), Nginx Reverse Proxy, SSH Tunnel(Bastion -> RDS) |

---

## 설치 및 설정

### 1) 실행 전 준비

- Docker / Docker Compose 사용 가능 환경
- `.env` 파일 준비 (`.env.example` 기반)
- AWS DB 연결 시 `.ssh/bizi-key.pem` 및 `BASTION_HOST` 준비
- 외부 연동 키(필요 시): `OPENAI_API_KEY`, `GOOGLE_CLIENT_ID`, `GOOGLE_CLIENT_SECRET`, `RAG_API_KEY` 등

### 2) 환경 변수 설정

```bash
cp .env.example .env
```

필수 점검 항목:

- DB 연결: `MYSQL_HOST`, `MYSQL_USER`, `MYSQL_PASSWORD`, `MYSQL_DATABASE`, `BASTION_HOST`
- 인증: `JWT_SECRET_KEY`
- RAG: `OPENAI_API_KEY`, `RAG_API_KEY`
- 임베딩 제공자: `EMBEDDING_PROVIDER` (`local` 또는 `runpod`)
- RunPod 사용 시: `RUNPOD_API_KEY`, `RUNPOD_ENDPOINT_ID`
- 동작 토글: `ENABLE_TEST_LOGIN`, `ENABLE_HYBRID_SEARCH`, `ENABLE_RERANKING` 등

### 3) 전체 서비스 실행

```bash
# 로컬 개발(경량): mock-rag 사용
docker compose -f docker-compose.local.yaml up --build

# 통합 테스트/운영 유사: rag + chromadb 사용
docker compose up --build
```

기본 접근:

- 웹 진입점: `http://localhost` (Nginx:80)
- Backend 직접(내부): `:8000`
- Frontend 직접(내부): `:5173`
- RAG 직접(내부): `:8001`

### 4) 코드 구현 (주요 코드 설명 포함)

#### 4-1. 요청 라우팅 및 게이트웨이

- Nginx가 단일 진입점 역할 수행
- `/api/*` -> Backend, `/rag/*` -> RAG, `/*` -> Frontend 프록시
- 보안 헤더(CSP 포함), API rate limit, SSE proxy 설정 포함

관련 파일:

- `nginx.conf`
- `nginx.local.conf`
- `docker-compose.yaml`
- `docker-compose.local.yaml`

#### 4-2. Frontend UI/상태 관리

- 라우트 구성: `frontend/src/App.tsx`
  - `/` 채팅, `/guide`, `/company`, `/schedule`, `/admin`, `/admin/log`
  - `/login` 모달 라우트
- 전역 상태:
  - 인증: `frontend/src/stores/authStore.ts`
  - 채팅: `frontend/src/stores/chatStore.ts`
  - 알림: `frontend/src/stores/notificationStore.ts`
- API 공통 클라이언트:
  - `frontend/src/lib/api.ts` (401 refresh 재시도 큐 포함)

#### 4-3. Backend 도메인 API + RAG 프록시

- 라우터 등록: `backend/main.py`
  - `auth`, `users`, `companies`, `histories`, `schedules`, `admin`, `rag`, `announces`
- 보안/운영:
  - CSRF 미들웨어
  - 요청 추적(`X-Request-ID`) 및 감사 로그
  - 민감정보 마스킹 로그 필터
- RAG 프록시:
  - `backend/apps/rag/router.py`
  - 사용자/기업 컨텍스트를 구성하여 RAG 서비스로 전달
  - 스트리밍(SSE) 중계, 문서 생성/수정 API 중계

#### 4-4. RAG 파이프라인

- 진입점: `rag/main.py`
- 주요 단계:
  1. 질문 분류(classify)
  2. 질문 분해(decompose)
  3. 문서 검색(retrieve)
  4. 응답 생성(generate)
  5. 평가(evaluate)
- 채팅 엔드포인트:
  - `rag/routes/chat.py` (`/api/chat`, `/api/chat/stream`)
- 벡터 저장소:
  - `rag/vectorstores/chroma.py`
  - `rag/vectorstores/config.py`
  - 컬렉션: `startup_funding_db`, `finance_tax_db`, `hr_labor_db`, `law_common_db`

#### 4-5. 일정-공고 연동 구현

- 일정 API: `backend/apps/schedules/router.py`
- 공고 API: `backend/apps/announces/router.py`
- 프론트 자동 등록 UI:
  - `frontend/src/pages/SchedulePage.tsx`
  - 공고 `+` 클릭 시 일정 생성, `-` 클릭 시 일정 제거
  - 자동 등록 메모 + 사용자 추가 메모 병합 저장

### 5) 프롬프트 최적화 관련 내용

#### 5-1. 프롬프트 구성 구조

- 도메인별 시스템 프롬프트 분리:
  - `STARTUP_FUNDING_PROMPT`
  - `FINANCE_TAX_PROMPT`
  - `HR_LABOR_PROMPT`
  - `LEGAL_PROMPT`
- 복합 질의 통합:
  - `MULTI_DOMAIN_SYNTHESIS_PROMPT`
- 질문 분해/확장:
  - `QUESTION_DECOMPOSER_PROMPT`
  - `MULTI_QUERY_PROMPT`

관련 파일:

- `rag/utils/prompts.py`

#### 5-2. 프롬프트 안전성

- 프롬프트 인젝션 방어:
  - 입력 패턴 탐지/정제 + 중증도 기준 차단
  - 관련 파일: `rag/utils/sanitizer.py`, `rag/routes/chat.py`
- 시스템 지시문 보호 가드:
  - `PROMPT_INJECTION_GUARD` 결합 방식 적용

#### 5-3. 검색/생성 품질 최적화 포인트

- Hybrid Search + Reranking 토글 기반 튜닝
- 도메인 분류(벡터/LLM) 및 문서 예산 분배
- 실패 시 단계적 재시도(전략 완화, 다중 쿼리, 인접 도메인 확장)
- 응답 평가(LLM/RAGAS 옵션) 기반 개선 루프

관련 설정 파일:

- `rag/utils/config/settings.py`

주요 운영 파라미터 예:

- `ENABLE_HYBRID_SEARCH`
- `ENABLE_RERANKING`
- `VECTOR_SEARCH_WEIGHT`
- `MULTI_QUERY_COUNT`
- `RERANKER_TYPE`
- `ENABLE_VECTOR_DOMAIN_CLASSIFICATION`
- `ENABLE_LLM_DOMAIN_CLASSIFICATION`
- `ENABLE_QUERY_REWRITE`
- `SESSION_MEMORY_BACKEND`

#### 5-4. 권장 최적화 절차

1. 도메인별 테스트셋으로 baseline 측정
2. 검색 파라미터(`K`, 가중치, rerank) 단일 변수 실험
3. 프롬프트 수정 전/후 평가 비교(정확도, 근거성, 응답시간)
4. 운영 로그와 사용자 피드백 기반 회귀 점검

---

## 기본 사용법

### 홈페이지 사용법

#### 시나리오 1: 로그인 후 상담 시작

1. `http://localhost` 접속
2. 우측 상단 로그인 모달에서 Google 로그인
3. 홈(`/`)에서 빠른 질문 버튼 또는 직접 질문 입력
4. 스트리밍 답변, 출처, 액션 버튼(문서 생성 등) 확인

#### 시나리오 2: 기업 정보 기반 맞춤 상담

1. 사이드바에서 `기업 정보` 이동
2. 기업 등록 후 대표 기업 설정
3. 홈으로 돌아와 같은 질문 재요청
4. 사용자 컨텍스트 반영된 답변 비교 확인

#### 시나리오 3: 일정/알림 연동 사용

1. `일정 관리`에서 기업 선택
2. 우측 관련 공고 목록에서 `+` 클릭
3. 팝업에서 추가 메모 입력 후 일정 자동 등록
4. 홈 화면에서 D-7/D-3 알림 토스트 및 알림 아이콘 카운트 확인

---

## 확장 및 커스터마이징

### 1) 도메인 확장

새 도메인 추가 시 권장 순서:

1. 코드/도메인 마스터 데이터 정의(`code`, domain config)
2. 전처리 데이터 수집 후 Chroma 컬렉션 생성
3. 에이전트 추가(`rag/agents/`)
4. 라우터/분류 규칙에 신규 도메인 연결
5. 프롬프트 및 평가 기준 추가

### 2) 검색 전략 커스터마이징

- 하이브리드 가중치 조정(`VECTOR_SEARCH_WEIGHT`)
- reranker 변경(`RERANKER_TYPE`)
- 메타데이터 필터링 정책(지역/유형) 수정
- 캐시 TTL 및 rate limit 정책 조정

### 3) UI/UX 커스터마이징

- 페이지별 알림 노출 정책: `useNotifications`, `notificationStore`
- 일정 화면 레이아웃/자동등록 UX: `SchedulePage.tsx`
- 로그인 모달/사이드바 브랜딩: `LoginPage.tsx`, `Sidebar.tsx`

### 4) 운영 및 관측성 확장

- 관리자 메트릭/로그 API 확장
- `X-Request-ID` 기반 추적 고도화
- JSON 로그 수집 파이프라인(ELK/Loki 등) 연동

---

## 결론

### 성과

- 벡터 DB + LLM + 웹 애플리케이션의 통합 구현 완료
- 인증/권한/도메인 CRUD/채팅/RAG/문서 생성/일정/알림 기능을 단일 서비스로 연결
- 운영 관점에서 추적성(요청 ID), 로깅, 관리자 관측 기능까지 확보
- 프롬프트/검색/평가를 독립 설정으로 운영 가능한 구조 확보

### 향후 발전 방향

- 품질 고도화:
  - 도메인별 정량 평가 자동화(RAGAS 파이프라인 정교화)
  - 응답 근거 추적 및 품질 리그레션 대시보드 강화
- 성능/비용 최적화:
  - 검색 캐시 전략 개선, rerank 조건부 실행 정교화
  - 임베딩/리랭킹 제공자 정책 동적 전환
- 제품 고도화:
  - 기업별 개인화 추천 정확도 개선
  - 문서 자동 생성 템플릿 확대
  - 관리자 운영 자동화(알림 정책, 장애 탐지/복구)

---

## 참고 파일

- 루트 가이드: `AGENTS.md`
- 프론트 라우팅: `frontend/src/App.tsx`
- 프론트 진입점(QueryClient): `frontend/src/main.tsx`
- API 클라이언트: `frontend/src/lib/api.ts`
- 일정 화면: `frontend/src/pages/SchedulePage.tsx`
- 알림 로직: `frontend/src/hooks/useNotifications.ts`
- 백엔드 진입점: `backend/main.py`
- 백엔드 RAG 프록시: `backend/apps/rag/router.py`
- RAG 진입점: `rag/main.py`
- RAG 채팅 라우트: `rag/routes/chat.py`
- 프롬프트 정의: `rag/utils/prompts.py`
- 인젝션 방어: `rag/utils/sanitizer.py`
- 벡터스토어 구현: `rag/vectorstores/chroma.py`
- 벡터스토어 설정: `rag/vectorstores/config.py`
- 실행 구성: `docker-compose.local.yaml`, `docker-compose.yaml`
