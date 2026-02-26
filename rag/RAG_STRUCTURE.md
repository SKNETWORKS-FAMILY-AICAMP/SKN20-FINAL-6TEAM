# Bizi RAG 시스템 전체 구조

> Bizi RAG 서비스의 전체 아키텍처를 설명하는 문서입니다.
> 작성일: 2026-02-23

---

## 목차

1. [시스템 개요](#1-시스템-개요)
2. [진입점 (main.py)](#2-진입점--mainpy)
3. [API 라우트](#3-api-라우트)
4. [LangGraph 파이프라인 (MainRouter)](#4-langgraph-파이프라인--mainrouter)
5. [1단계: 분류 (classify)](#5-1단계-분류-classify)
6. [2단계: 분해 (decompose)](#6-2단계-분해-decompose)
7. [3단계: 검색 (retrieve)](#7-3단계-검색-retrieve)
8. [4단계: 생성 (generate)](#8-4단계-생성-generate)
9. [5단계: 평가 (evaluate)](#9-5단계-평가-evaluate)
10. [도메인 에이전트](#10-도메인-에이전트)
11. [RAGChain](#11-ragchain)
12. [VectorDB](#12-vectordb)
13. [설정 (Settings)](#13-설정-settings)
14. [프롬프트](#14-프롬프트)
15. [전체 데이터 흐름 예시](#15-전체-데이터-흐름-예시)

---

## 1. 시스템 개요

```
┌─────────────────────────────────────────────────────────────────┐
│                      Frontend (React + Vite)                    │
│                    localhost:5173                                │
└───────────────────────────┬─────────────────────────────────────┘
                            │ axios
                            │ /api/* (인증,사용자,기업)
                            │ /rag/* (채팅,AI응답,문서생성)
                            ↓
┌───────────────────────────────────────────────────┐
│              Nginx (리버스 프록시) :80              │
│  /api/* → Backend :8000                           │
│  /rag/* → RAG :8001                               │
│  /*    → Frontend :5173                           │
└───────────────┬───────────────────┬───────────────┘
                │                   │
                ↓                   ↓
        ┌───────────────┐  ┌─────────────────────────────────┐
        │  Backend       │  │      RAG Service (FastAPI)      │
        │  :8000         │  │      :8001                      │
        │                │  │                                 │
        │ - Google OAuth │  │ - LangGraph 5단계 파이프라인    │
        │ - 사용자/기업   │  │ - 4개 도메인별 벡터DB           │
        │ - 상담 이력     │  │ - 3중 평가 체계                 │
        └───────┬───────┘  │ - Action Executor               │
                │           └───────────┬─────────────────────┘
                ↓                       ↓
        ┌───────────────┐     ┌─────────────────────┐
        │   MySQL (RDS) │     │     ChromaDB         │
        │   bizi_db     │     │   (Vector DB)        │
        └───────────────┘     └─────────────────────┘
```

RAG 서비스는 **독립된 FastAPI 서버**로, Backend와는 별도로 동작합니다.
- Backend가 사용자 컨텍스트를 주입하고 RAG로 중계하는 프록시 역할
- 직접 호출도 가능 (X-API-Key 인증)

---

## 2. 진입점 — `main.py`

FastAPI 서버의 진입점입니다. 서버 시작 시 `lifespan`에서 초기화합니다:

```
서버 시작
  → 도메인 설정 DB 초기화 + 로드
  → ChromaDB 연결 (vector_store)
  → MainRouter 생성 (LangGraph 파이프라인)
  → ActionExecutor 생성 (문서 생성기)
  → Reranker 모델 사전 로딩 (local) 또는 RunPod warmup
  → ChromaDB BM25 인덱스 사전 빌드
  → 설정 요약 로그 출력
```

**미들웨어 스택** (요청 처리 순서):

| 순서 | 미들웨어 | 역할 |
|------|---------|------|
| 1 | CORSMiddleware | 프론트엔드 도메인 허용 |
| 2 | APIKeyMiddleware | `X-API-Key` 헤더로 보호된 엔드포인트 인증 |
| 3 | MetricsMiddleware | 요청/응답 시간 수집 |
| 4 | RateLimitMiddleware | Token Bucket 기반 요청 제한 |

**관련 파일**: `main.py`, `utils/middleware.py`

---

## 3. API 라우트

| 엔드포인트 | 메서드 | 설명 | 파일 |
|-----------|--------|------|------|
| `/api/chat` | POST | 일반 응답 (JSON) | `routes/chat.py` |
| `/api/chat/stream` | POST | SSE 스트리밍 응답 | `routes/chat.py` |
| `/api/documents/generate` | POST | 문서 생성 (근로계약서 등) | `routes/documents.py` |
| `/api/funding/search` | POST | 지원사업 검색 | `routes/funding.py` |
| `/api/evaluate` | POST | 답변 평가 | `routes/evaluate.py` |
| `/api/vectordb/*` | GET/POST | 벡터DB 관리 | `routes/vectordb.py` |
| `/health` | GET | 헬스체크 | `routes/health.py` |
| `/metrics` | GET | 메트릭 조회 | `routes/monitoring.py` |

### 채팅 요청 처리 흐름

```
POST /api/chat
  ↓
1. 캐시 조회 (LRU 500건, TTL 1시간)
  → 히트 시 즉시 반환
  ↓
2. MainRouter.aprocess() 호출 ← 여기가 핵심 파이프라인
  ↓
3. 토큰 사용량 추적 (RequestTokenTracker)
  ↓
4. 응답 로깅 (chat.log)
  ↓
5. 캐시 저장
  ↓
6. ChatResponse 반환
```

---

## 4. LangGraph 파이프라인 — MainRouter

`agents/router.py`에 정의된 LangGraph `StateGraph`로 5단계 파이프라인을 구성합니다.

```
사용자 질문
    │
    ↓
┌────────────┐    ┌────────────┐    ┌────────────┐    ┌────────────┐    ┌────────────┐
│  classify  │ →  │  decompose │ →  │  retrieve  │ →  │  generate  │ →  │  evaluate  │
│  (분류)    │    │  (분해)    │    │  (검색)    │    │  (생성)    │    │  (평가)    │
└────────────┘    └────────────┘    └────────────┘    └────────────┘    └─────┬──────┘
                                                                              │
                                                                         PASS │ FAIL
                                                                              ↓
                                                                    ┌──────────────────┐
                                                                    │ retry_with_       │
                                                                    │ alternatives      │
                                                                    │ (재시도, 1회만)    │
                                                                    └──────────────────┘
                                                                              │
                                                                              ↓
                                                                        ChatResponse
```

### RouterState (상태 딕셔너리)

파이프라인의 각 단계에서 공유하는 상태입니다:

| 필드 | 타입 | 설명 |
|------|------|------|
| `query` | str | 원본 질문 |
| `history` | list[dict] | 대화 이력 |
| `user_context` | UserContext | 사용자/기업 정보 |
| `domains` | list[str] | 분류된 도메인 리스트 |
| `classification_result` | DomainClassificationResult | 분류 상세 결과 |
| `sub_queries` | list[SubQuery] | 분해된 하위 질문 |
| `retrieval_results` | dict[str, RetrievalResult] | 도메인별 검색 결과 |
| `documents` | list[Document] | 최종 병합 문서 |
| `final_response` | str | 생성된 답변 |
| `sources` | list[SourceDocument] | 출처 리스트 |
| `actions` | list[ActionSuggestion] | 추천 액션 |
| `evaluation` | EvaluationResult | 평가 결과 |
| `retry_count` | int | 재시도 횟수 |

### MainRouter가 초기화하는 핵심 객체

```python
self.agents = {
    "startup_funding": StartupFundingAgent(rag_chain=shared_rag_chain),
    "finance_tax":     FinanceTaxAgent(rag_chain=shared_rag_chain),
    "hr_labor":        HRLaborAgent(rag_chain=shared_rag_chain),
    "law_common":      LegalAgent(rag_chain=shared_rag_chain),
}
self.retrieval_agent = RetrievalAgent(...)   # 검색 파트 전담
self.generator = ResponseGeneratorAgent(...) # 생성 파트 전담
self.evaluator = EvaluatorAgent()            # 평가 파트 전담
```

모든 에이전트가 **하나의 RAGChain**을 공유합니다 (벡터DB 연결, Reranker 등).

---

## 5. 1단계: 분류 (classify)

**파일**: `utils/domain_classifier.py`

질문이 어떤 도메인에 해당하는지 판단합니다.

### 분류 파이프라인

```
사용자 질문
    │
    ↓
┌──────────────────────────────────────────────┐
│ [1차] LLM 분류                                │
│   ENABLE_LLM_DOMAIN_CLASSIFICATION=true일 때  │
│   → LLM에게 "이 질문은 어떤 도메인?" 물어봄   │
│   → 성공 시 바로 반환                         │
│   → 실패 시 fallback ↓                       │
└────────────────────┬─────────────────────────┘
                     ↓ (fallback)
┌──────────────────────────────────────────────┐
│ [2차] 키워드 매칭 (kiwipiepy 형태소 분석)     │
│   → 질문을 형태소 분석 → 명사/동사 원형 추출  │
│   → DOMAIN_KEYWORDS와 매칭                    │
│     예: "부가세" → finance_tax               │
│         "해고" → hr_labor                    │
│   → 복합 규칙: 2개 이상 lemma 조합            │
│   → 매칭 시 confidence +0.1 보정             │
└────────────────────┬─────────────────────────┘
                     ↓
┌──────────────────────────────────────────────┐
│ [3차] 벡터 유사도 분류                        │
│   → 질문 임베딩 vs 도메인별 대표 쿼리 비교    │
│   → cosine 유사도 계산                        │
│   → boosted_confidence ≥ 0.6 → 통과          │
│   → < 0.6 → 거부 응답 반환                   │
└──────────────────────────────────────────────┘
```

### 분류 결과

```python
@dataclass
class DomainClassificationResult:
    domains: list[str]           # ["finance_tax"] 또는 ["startup_funding", "finance_tax"]
    confidence: float            # 0.0~1.0
    is_relevant: bool            # True: 상담 범위 내 / False: 범위 외
    method: str                  # 'keyword', 'vector', 'llm', 'fallback'
    matched_keywords: dict|None  # 매칭된 키워드 상세
```

### 키워드 소스

| 소스 | 파일 | 설명 |
|------|------|------|
| MySQL DB | `utils/config/domain_config.py` | 운영 중 동적 관리 가능 |
| 하드코딩 | `utils/config/domain_data.py` | DB 연결 실패 시 fallback |

### 4개 도메인

| 도메인 키 | 설명 | 키워드 예시 |
|-----------|------|-----------|
| `startup_funding` | 창업/지원사업/마케팅 | 창업, 사업자등록, 법인설립, 지원사업, 보조금 |
| `finance_tax` | 재무/세무/회계 | 세금, 부가세, 법인세, 회계, 절세 |
| `hr_labor` | 인사/노무 | 근로, 채용, 해고, 급여, 퇴직금, 4대보험 |
| `law_common` | 법률 일반 | 법률, 판례, 상법, 민법, 소송, 특허 |

---

## 6. 2단계: 분해 (decompose)

**파일**: `utils/question_decomposer.py`

복합 도메인 질문을 도메인별 하위 질문으로 분해합니다.

### 동작

- **단일 도메인**: 분해 없이 원본 쿼리 그대로 통과
- **복합 도메인**: LLM이 도메인별로 독립적인 질문으로 재작성

### 예시

```
입력: "사업자등록 방법과 초기 세무 처리 알려주세요"
도메인: [startup_funding, finance_tax]

    ↓ LLM 호출 (QUESTION_DECOMPOSER_PROMPT)

출력:
  SubQuery(domain="startup_funding", query="사업자등록 방법은 어떻게 되나요?")
  SubQuery(domain="finance_tax",     query="초기 세무 처리는 어떻게 하나요?")
```

### 특징

- **대화 이력 활용**: 최근 3턴의 대화를 참고하여 대명사/생략된 주어 해소
- **LRU 캐시**: 동일 질문+도메인 조합의 재분해 방지
- **JSON 파싱**: LLM 출력을 JSON으로 파싱하여 SubQuery 객체로 변환

---

## 7. 3단계: 검색 (retrieve)

**파일**: `agents/retrieval_agent.py`

**파이프라인에서 가장 복잡한 단계**입니다. LLM 호출 없이 규칙 기반으로 동작합니다 (비용 0, 지연 0).

### 7-1. 전체 검색 흐름

```
쿼리 입력
    │
    ↓
┌─ SearchStrategySelector ─────────────────────┐
│  쿼리 특성 분석 → 검색 모드 추천              │
│  (길이, 사실형 여부, 법조문 포함 등)          │
└──────────────────────┬───────────────────────┘
                       ↓
┌─ DocumentBudgetCalculator ───────────────────┐
│  도메인별 문서 할당량(K) 계산                  │
│  (주 도메인/부 도메인 구분)                    │
└──────────────────────┬───────────────────────┘
                       ↓
┌─ 도메인별 병렬 검색 (asyncio.gather) ────────┐
│  각 도메인:                                   │
│    1. Multi-Query 확장 (항상, 3개 변형)        │
│    2. HybridSearcher (BM25+Vector+RRF)        │
│    3. 문서 K개 반환                            │
│    4. RuleBasedRetrievalEvaluator 평가         │
└──────────────────────┬───────────────────────┘
                       ↓
┌─ 재시도 (FAIL인 도메인만) ───────────────────┐
│  Level 1: 평가 기준 완화 + K+3 증가           │
│  Level 2: Multi-Query 강화                    │
│  Level 3: 인접 도메인 검색                    │
└──────────────────────┬───────────────────────┘
                       ↓
┌─ 법률 보충 검색 ─────────────────────────────┐
│  쿼리에 "법률", "소송", "~법" 패턴 감지       │
│  → law_common_db에서 추가 문서 검색           │
└──────────────────────┬───────────────────────┘
                       ↓
┌─ 문서 병합 + Cross-Domain Reranking ─────────┐
│  복합 도메인:                                  │
│    DocumentMerger → 중복 제거 + 우선순위 정렬  │
│    Reranker → ratio=0.7 (30% 저품질 제거)     │
│  단일 도메인:                                  │
│    문서 수 > retrieval_k면 Rerank → top_k 유지 │
└──────────────────────────────────────────────┘
```

### 7-2. SearchStrategySelector (쿼리 분석)

쿼리 특성을 분석하여 검색 모드를 추천합니다:

| 조건 | 모드 | 설명 |
|------|------|------|
| 기본 | `HYBRID` | BM25 + Vector + RRF 앙상블 |
| 50자 이상 복잡한 질문 | `VECTOR_HEAVY` | vector_weight=0.9 |
| 짧은 사실형 질문 | `BM25_HEAVY` | vector_weight=0.2 |
| 모호한 질문 | `MMR_DIVERSE` | MMR로 다양성 극대화 |
| 법조문 인용 (제X조) | `EXACT_PLUS_VECTOR` | 정확 매칭 우선 |

### 7-3. DocumentBudgetCalculator (문서 예산 할당)

**Bounded 모드** (`ENABLE_FIXED_DOC_LIMIT=true`, 현재 기본):

| 도메인 수 | 도메인당 K | 총 문서 수 |
|-----------|-----------|-----------|
| 1 | 4 (retrieval_k 그대로) | 4 |
| 2 | 5 (주/부 균등) | 10 |
| 3 | 5 | 15 |
| 4 | 3 (min_domain_k) | 12 |

### 7-4. HybridSearcher (BM25 + Vector + RRF)

**파일**: `utils/search.py`

```
쿼리: "부가세 신고 기한이 언제인가요?"

  ┌─── BM25 검색 ──────────────────┐   ┌─── Vector 검색 ────────────────┐
  │ kiwipiepy 형태소 분석           │   │ ChromaDB similarity_search     │
  │ → "부가세", "신고", "기한"      │   │ → BGE-M3 임베딩 유사도         │
  │ → BM25 스코어 계산              │   │ → 유사도 순위 리스트            │
  │ → 순위 리스트 생성              │   │                                │
  └────────────┬───────────────────┘   └────────────┬───────────────────┘
               │                                     │
               └───────────────┬─────────────────────┘
                               ↓
               ┌─── RRF 앙상블 ───────────────────────┐
               │ score = weight × 1/(rank_v + 60)      │
               │       + (1-weight) × 1/(rank_bm25+60) │
               │                                        │
               │ weight = 0.7 (벡터 70%, BM25 30%)     │
               └────────────┬──────────────────────────┘
                            ↓
               ┌─── Re-ranking ───────────────────────┐
               │ Cross-encoder 모델                     │
               │ (BGE-reranker-base 또는 RunPod GPU)   │
               │ → 최종 관련도 점수로 재정렬            │
               └───────────────────────────────────────┘
```

### 7-5. Multi-Query

**파일**: `utils/query.py`

**항상 실행**됩니다 (재시도 시만이 아님):

```
원본: "부가세 신고 기한이 언제인가요?"
        ↓ LLM이 3개 변형 생성 (MULTI_QUERY_PROMPT)
변형1: "부가가치세 신고 납부 기한 일정"
변형2: "VAT 신고 마감일 알려주세요"
변형3: "부가세 분기별 신고 일정"
        ↓
4개 쿼리(원본+변형) 모두로 검색 → 결과 합집합 → 중복 제거 → 최종 K개
```

### 7-6. 단계적 재시도 (GraduatedRetryHandler)

검색 품질이 미달(FAIL)인 도메인에 대해 단계적으로 재시도합니다:

```
Level 1: RELAX_PARAMS    → 평가 기준 완화 + K+3 증가
Level 2: MULTI_QUERY     → LLM 쿼리 확장 강화
Level 3: CROSS_DOMAIN    → 인접 도메인 검색
```

**인접 도메인 매핑** (Level 3에서 사용):

| 원래 도메인 | 인접 도메인 |
|------------|-----------|
| startup_funding | finance_tax |
| finance_tax | startup_funding, law_common |
| hr_labor | law_common |
| law_common | hr_labor, finance_tax |

### 7-7. 법률 보충 검색

**파일**: `utils/legal_supplement.py`

주 도메인 검색 후, 쿼리/문서에서 법률 키워드를 감지하면 `law_common_db`에서 추가 검색합니다.

- `~법` 패턴 자동 감지 (정규식: 산업안전보건법, 건설산업기본법 등)
- 키워드 매칭: "법률", "소송", "손해배상", "판결" 등
- `law_common`이 주 도메인인 경우는 보충 불필요 (이미 직접 검색)

### 7-8. Cross-Domain Reranking

복합 도메인에서 병합된 문서에 대해 Reranker로 최종 필터링합니다:

| 도메인 수 | 총 후보 | Rerank 후 (ratio=0.7) | 필터율 |
|-----------|---------|----------------------|-------|
| 2 | 10 | 7 | 30% 제거 |
| 3 | 15 | 10 | 33% 제거 |
| 4 | 12 | 8 | 33% 제거 |

단일 도메인에서는 `retrieval_k` 기준으로 상위 문서만 유지합니다.

---

## 8. 4단계: 생성 (generate)

**파일**: `agents/generator.py` (ResponseGeneratorAgent)

검색된 문서를 기반으로 최종 답변을 생성합니다.

### 단일 도메인 생성

```
도메인 에이전트의 시스템 프롬프트 사용
  예: FINANCE_TAX_PROMPT (세무 전문가 역할)

문서 → format_context()
  → "[1] 부가가치세법 제48조\n출처: 국세법령정보시스템\n부가가치세 과세표준은..."

액션 힌트 → system prompt에 주입 (ACTION_HINT_TEMPLATE)

ChatPromptTemplate:
  system: {도메인 프롬프트 + 액션 힌트}
  human: {query}

→ LLM 1회 호출 (gpt-4o-mini, temperature=0.1) → 답변 생성
```

### 복합 도메인 생성

```
MULTI_DOMAIN_SYNTHESIS_PROMPT 사용
  → 모든 도메인의 문서를 도메인별로 그룹핑
  → 각 도메인의 하위 질문(SubQuery)과 검색 문서를 나열

예:
  ## startup_funding 영역
  하위 질문: "사업자등록 방법은?"
  [1] 사업자등록 신청 절차...
  [2] 법인설립 방법...

  ## finance_tax 영역
  하위 질문: "초기 세무 처리는?"
  [3] 사업자등록 후 세금 신고...
  [4] 부가세 예정 신고...

→ LLM 1회 호출로 통합 답변 생성 (기존 도메인별 N회 → 1회로 최적화)
```

### 액션 선제안

생성 전에 문서 내용과 질문을 분석하여 추천 액션을 결정합니다:

| 액션 타입 | 설명 | 예시 |
|----------|------|------|
| document_generation | 문서 자동 생성 | 근로계약서, 사업계획서 |
| funding_search | 지원사업 검색 | 기업마당 검색 |
| legal_consultation | 법률 상담 링크 | 대한법률구조공단 |
| tax_calendar | 세무 일정 안내 | 신고 마감일 |

액션은 `ACTION_HINT_TEMPLATE`로 시스템 프롬프트에 주입되어 답변에 자연스럽게 안내됩니다.

### 스트리밍 지원

`astream_generate()` / `astream_generate_multi()`로 SSE(Server-Sent Events) 토큰 단위 스트리밍을 지원합니다. 프론트엔드에서 실시간으로 답변이 한 글자씩 표시됩니다.

---

## 9. 5단계: 평가 (evaluate)

### 3중 평가 체계

| 구분 | 검색 평가 | LLM 평가 | RAGAS 평가 |
|------|----------|---------|-----------|
| **파일** | `utils/retrieval_evaluator.py` | `agents/evaluator.py` | `evaluation/ragas_evaluator.py` |
| **방식** | 규칙 기반 (문서 수, 키워드, 유사도) | LLM이 5개 기준으로 채점 | RAGAS 라이브러리 메트릭 |
| **용도** | 검색 품질 판단 → 재시도 트리거 | 답변 품질 채점 → FAIL 시 재시도 | 정량적 품질 추적 및 분석 |
| **실행 시점** | retrieve 단계 | evaluate 단계 | evaluate 단계 (선택적) |
| **재시도** | GraduatedRetryHandler (L1~L3) | 1회 재시도 | 없음 (로깅만) |

### LLM 평가 (`ENABLE_LLM_EVALUATION=true`)

```
LLM에게 5가지 기준으로 채점 요청 (EVALUATOR_PROMPT):

  - 검색 품질 (0-20점): 참고 컨텍스트가 질문과 관련 있는지
  - 정확성   (0-20점): 정보의 사실 부합 여부
  - 완성도   (0-20점): 질문에 대해 충분히 답변했는지
  - 관련성   (0-20점): 질문 의도와의 일치 여부
  - 출처 명시 (0-20점): 법령/규정 인용 시 출처 여부

총점 100점 만점
  ≥ 70점: PASS → 응답 반환
  < 70점: FAIL → 재시도
```

### 재시도 흐름 (`ENABLE_POST_EVAL_RETRY=true`)

```
평가 FAIL
    ↓
대체 쿼리 2개 생성 (LLM)
    ↓
원본 + 대체 2개 = 3개 후보
    ↓ 각각 검색 + 생성
3개 답변 생성
    ↓
3개 중 LLM 평가 최고점 선택
    ↓
1회만 수행 (무한 루프 방지)
```

### RAGAS 평가 (`ENABLE_RAGAS_EVALUATION=true`)

```
RAGAS 라이브러리로 4개 메트릭 계산:

  - Faithfulness     : 답변이 컨텍스트에 충실한가
  - Answer Relevancy : 답변이 질문에 관련있는가
  - Context Precision: 검색된 컨텍스트가 정확한가
  - Context Recall   : 필요한 컨텍스트가 모두 검색되었나

→ 로깅만 (재시도 트리거 안함)
→ logs/ragas.log에 JSON Lines 형식으로 기록
```

---

## 10. 도메인 에이전트

**파일**: `agents/startup_funding.py`, `agents/finance_tax.py`, `agents/hr_labor.py`, `agents/legal.py`

4개 도메인 에이전트는 모두 `BaseAgent`(`agents/base.py`)를 상속합니다.

| 에이전트 | 파일 | 도메인 | 벡터DB 컬렉션 | 데이터 소스 |
|---------|------|--------|-------------|-----------|
| StartupFundingAgent | `startup_funding.py` | startup_funding | startup_funding_db | 창업진흥원, 기업마당, K-Startup |
| FinanceTaxAgent | `finance_tax.py` | finance_tax | finance_tax_db | 국세청, 세법, 판례(세금) |
| HRLaborAgent | `hr_labor.py` | hr_labor | hr_labor_db | 근로기준법, 해석례, 판례(노동) |
| LegalAgent | `legal.py` | law_common | law_common_db | 법령 원문, 법령 해석례 |

### 각 에이전트가 제공하는 것

```python
class FinanceTaxAgent(BaseAgent):
    domain = "finance_tax"

    ACTION_RULES = [
        ActionRule(
            keywords=["신고", "납부", "마감"],
            action=ActionSuggestion(type="tax_calendar", label="세무 일정 확인", ...),
        ),
        # ...
    ]

    def get_system_prompt(self) -> str:
        return FINANCE_TAX_PROMPT  # prompts.py에서 가져옴
```

- `get_system_prompt()` → 도메인 전문가 프롬프트
- `ACTION_RULES` → 키워드 기반 액션 추천 규칙
- `retrieve_only()` / `aretrieve_only()` → 문서 검색 (BaseAgent에서 상속)
- `suggest_actions()` → ACTION_RULES 기반 액션 추천 (BaseAgent에서 상속)

---

## 11. RAGChain

**파일**: `chains/rag_chain.py`

모든 에이전트가 공유하는 핵심 체인입니다.

```
RAGChain
  ├── vector_store (ChromaVectorStore) ── ChromaDB 연결
  ├── llm (ChatOpenAI) ──────────────── gpt-4o-mini (temperature=0.1)
  ├── hybrid_searcher (HybridSearcher) ─ BM25+Vector 앙상블 (지연 로딩)
  ├── reranker (Reranker) ──────────── Cross-encoder 재정렬 (지연 로딩)
  ├── response_cache (ResponseCache) ── LRU 캐시 (지연 로딩)
  └── query_processor ─────────────── 컨텍스트 압축기 (지연 로딩)
```

### 주요 메서드

| 메서드 | 설명 |
|--------|------|
| `retrieve(query, domain)` | Multi-Query 기반 문서 검색 |
| `_retrieve_documents(query, domain)` | 단일 쿼리 Hybrid Search + Reranking |
| `format_context(documents)` | 문서를 `[1] 제목\n출처\n내용` 형식으로 포맷 |
| `documents_to_sources(documents)` | 문서를 SourceDocument 리스트로 변환 |
| `ainvoke(query, domain, ...)` | 검색 + LLM 생성 (비동기) |
| `astream(query, domain, ...)` | 검색 + LLM 스트리밍 (비동기) |

### 컨텍스트 포맷팅 예시

```
[1] 부가가치세법 제48조
출처: 국세법령정보시스템
사업자는 각 과세기간에 대한 과세표준과 세액을 그 과세기간이 끝난 후 25일 이내에
사업장 관할 세무서장에게 신고하여야 한다...

---

[2] 부가가치세 신고 안내
출처: 국세청 안내자료
부가가치세는 1년에 4번(1/4/7/10월) 신고·납부해야 합니다...
```

---

## 12. VectorDB

### ChromaVectorStore (`vectorstores/chroma.py`)

ChromaDB 클라이언트를 래핑합니다:

- **Remote 모드**: Docker의 ChromaDB 서버에 HTTP 연결 (`CHROMA_HOST:CHROMA_PORT`)
- **Local 모드**: 로컬 파일 기반 PersistentClient
- `RLock` 사용 (교착 방지)

주요 메서드: `similarity_search()`, `max_marginal_relevance_search()`, `similarity_search_with_score()`, `health_check()`

### 벡터DB 구조 (`vectorstores/config.py`)

```
ChromaDB
├── startup_funding_db/          # 창업/지원/마케팅
│   ├── announcements.jsonl              (공고, 청킹 안함)
│   ├── industry_startup_guide.jsonl     (업종 가이드, 청킹 안함)
│   └── startup_procedures.jsonl         (창업 절차, 조건부 청킹)
│
├── finance_tax_db/              # 재무/세무
│   ├── tax_support.jsonl                (세무 지원, 조건부 청킹)
│   └── court_cases_tax.jsonl            (세금 판례, 필수 청킹)
│
├── hr_labor_db/                 # 인사/노무
│   ├── labor_interpretation.jsonl       (노동 해석례, 조건부 청킹)
│   ├── hr_insurance_edu.jsonl           (보험 교육, 조건부 청킹)
│   └── court_cases_labor.jsonl          (노동 판례, 필수 청킹)
│
└── law_common_db/               # 법령 (공통)
    ├── laws_full.jsonl                  (법령 원문, 조건부 청킹)
    └── interpretations.jsonl            (법령 해석례, 조건부 청킹)
```

### 청킹 전략

| 구분 | 대상 | 설정 |
|------|------|------|
| **청킹 안함** | 공고, 업종 가이드 | 이미 짧은 문서 |
| **조건부 청킹** | 법령, 해석례, 세무지원 | 3,500자 넘으면 분할 |
| **필수 청킹** | 판례 (세금/노동) | 항상 1,500자로 분할 |

- 청크 사이즈: 1,500자 (판례) ~ 2,000자 (법령)
- BGE-M3 최대 8,192 토큰 대비 약 13% 사용

### 임베딩

| 모드 | 모델 | 환경 |
|------|------|------|
| Local | HuggingFace `BAAI/bge-m3` | CPU |
| RunPod | RunPod Serverless GPU에서 BGE-M3 | GPU |

설정: `EMBEDDING_PROVIDER=local` 또는 `EMBEDDING_PROVIDER=runpod`

---

## 13. 설정 (Settings)

**파일**: `utils/config/settings.py`

Pydantic `BaseSettings`로 모든 설정을 환경변수에서 로드합니다.

### 핵심 파라미터

| 카테고리 | 파라미터 | 현재 값 | 설명 |
|---------|---------|--------|------|
| **검색** | `retrieval_k` | 4 | 도메인당 검색 문서 수 |
| | `max_retrieval_docs` | 15 | 최대 총 검색 문서 |
| | `min_domain_k` | 3 | 복합 도메인 시 최소 K |
| | `vector_search_weight` | 0.7 | 벡터 70%, BM25 30% |
| **Rerank** | `cross_domain_rerank_ratio` | 0.7 | 복합 도메인 문서 유지 비율 |
| | `rerank_top_k` | 3 | Rerank 후 상위 K |
| **컨텍스트** | `format_context_length` | 4000 | 문서 내용 최대 길이 (자) |
| | `evaluator_context_length` | 4000 | 평가 시 컨텍스트 최대 길이 |
| **생성** | `openai_model` | gpt-4o-mini | LLM 모델 |
| | `openai_temperature` | 0.1 | LLM 온도 (낮을수록 일관적) |
| | `generation_max_tokens` | 2048 | 답변 최대 토큰 |
| **MMR** | `mmr_lambda_mult` | 0.6 | 관련성 60%, 다양성 40% |
| | `mmr_fetch_k_multiplier` | 4 | 초기 후보 = K x 4 |
| **법률 보충** | `legal_supplement_k` | 4 | 보충 검색 문서 수 |
| **평가** | `evaluation_threshold` | 70 | LLM 평가 통과 임계값 |

### Feature Flags (토글)

| 환경변수 | 기본값 | 설명 |
|---------|--------|------|
| `ENABLE_HYBRID_SEARCH` | true | Hybrid Search (BM25+Vector+RRF) |
| `ENABLE_RERANKING` | true | Cross-encoder Re-ranking |
| `ENABLE_FIXED_DOC_LIMIT` | true | 도메인별 고정 문서 개수 제한 |
| `ENABLE_CROSS_DOMAIN_RERANK` | true | 복합 도메인 Cross-Domain Reranking |
| `ENABLE_LLM_EVALUATION` | true | LLM 답변 평가 |
| `ENABLE_RAGAS_EVALUATION` | false | RAGAS 정량 평가 |
| `ENABLE_DOMAIN_REJECTION` | true | 도메인 외 질문 거부 |
| `ENABLE_LEGAL_SUPPLEMENT` | true | 법률 보충 검색 |
| `ENABLE_POST_EVAL_RETRY` | true | 평가 FAIL 시 재시도 |
| `ENABLE_GRADUATED_RETRY` | true | 단계적 재시도 (L1~L3) |
| `ENABLE_ADAPTIVE_SEARCH` | true | 적응형 검색 모드 선택 |
| `ENABLE_ACTION_AWARE_GENERATION` | true | 액션 선제안 |
| `ENABLE_RESPONSE_CACHE` | true | 응답 캐싱 |
| `ENABLE_RATE_LIMIT` | true | Rate Limiting |

---

## 14. 프롬프트

**파일**: `utils/prompts.py`

모든 프롬프트가 한 파일에 집중 관리됩니다.

| 프롬프트 | 용도 |
|---------|------|
| `STARTUP_FUNDING_PROMPT` | 창업/지원 에이전트 시스템 프롬프트 |
| `FINANCE_TAX_PROMPT` | 재무/세무 에이전트 시스템 프롬프트 |
| `HR_LABOR_PROMPT` | 인사/노무 에이전트 시스템 프롬프트 |
| `LEGAL_PROMPT` | 법률 에이전트 시스템 프롬프트 |
| `MULTI_DOMAIN_SYNTHESIS_PROMPT` | 복합 도메인 통합 생성 |
| `EVALUATOR_PROMPT` | 답변 평가 |
| `QUESTION_DECOMPOSER_PROMPT` | 질문 분해 |
| `LLM_DOMAIN_CLASSIFICATION_PROMPT` | LLM 도메인 분류 |
| `MULTI_QUERY_PROMPT` | Multi-Query 변형 생성 |
| `REJECTION_RESPONSE` | 도메인 외 질문 거부 |
| `ACTION_HINT_TEMPLATE` | 액션 힌트 주입 |

### 도메인 프롬프트 공통 규칙

각 도메인 프롬프트에는 아래 규칙이 공통으로 포함됩니다:

**참고 자료 활용 원칙:**
- 모든 사실적 주장은 검색된 문서에서만
- 문장마다 [번호] 형식으로 출처 표기

**답변 집중 원칙:**
- 질문에 직접 답변, 핵심 키워드 포함
- 800자 이내 (복합 질문은 1500자 이내)
- 질문이 3가지를 물으면 3가지 모두 답변

**절대 금지 사항:**
- 자체 지식 사용 금지
- 숫자/비율 날조 금지
- 일반론 금지 ("일반적으로~" 표현 금지)

---

## 15. 전체 데이터 흐름 예시

### 예시 1: 단일 도메인 질문

```
사용자: "부가세 신고 기한이 언제인가요?"

1. classify
   → kiwipiepy: "부가세", "신고", "기한"
   → finance_tax 매칭 (confidence: 0.72)
   → 결과: domains=["finance_tax"]

2. decompose
   → 단일 도메인 → 분해 스킵
   → sub_queries=[SubQuery(domain="finance_tax", query="부가세 신고 기한이 언제인가요?")]

3. retrieve (RetrievalAgent)
   → SearchStrategySelector: BM25_HEAVY (짧은 사실형), K=4
   → DocumentBudgetCalculator: finance_tax=4
   → Multi-Query: 3개 변형 생성
   → HybridSearcher: finance_tax_db에서 4건 검색
   → RuleBasedRetrievalEvaluator: PASS (4건, 키워드 매칭 0.6)
   → 법률 보충: "부가세" → 법률 키워드 아님 → 보충 안함
   → 단일 도메인 Rerank → 상위 4건 유지

4. generate (ResponseGeneratorAgent)
   → FINANCE_TAX_PROMPT + 4건 문서 + 액션 힌트
   → LLM 1회 호출 → 답변 생성
   → 액션: [세무 일정 확인]

5. evaluate (EvaluatorAgent)
   → LLM 채점: 정확성 18 + 완성도 17 + 관련성 19 + 출처 16 + 검색 15 = 85점
   → PASS

6. ChatResponse 반환
   → content: "부가가치세 신고 기한은 다음과 같습니다. [1] ..."
   → sources: [SourceDocument x 4]
   → actions: [세무 일정 확인]
   → domains: ["finance_tax"]
```

### 예시 2: 복합 도메인 질문

```
사용자: "창업하려는데 사업자등록 방법과 초기 세무 처리 알려주세요"

1. classify
   → "사업자등록" → startup_funding, "세무" → finance_tax
   → 결과: domains=["startup_funding", "finance_tax"]

2. decompose
   → LLM 호출 → 2개 SubQuery 생성
   → SubQuery(domain="startup_funding", query="사업자등록 방법은?")
   → SubQuery(domain="finance_tax", query="초기 세무 처리는?")

3. retrieve (RetrievalAgent)
   → DocumentBudgetCalculator: startup_funding=5, finance_tax=5
   → 병렬 검색 (asyncio.gather):
     - startup_funding_db: 5건 검색 (PASS)
     - finance_tax_db: 5건 검색 (PASS)
   → DocumentMerger: 중복 제거 → 10건
   → Cross-Domain Reranking: 10건 x 0.7 = 7건 유지

4. generate (ResponseGeneratorAgent)
   → MULTI_DOMAIN_SYNTHESIS_PROMPT + 7건 문서
   → LLM 1회 통합 생성

5. evaluate → 78점 PASS

6. ChatResponse 반환
   → content: "## 사업자등록\n...\n## 초기 세무 처리\n..."
   → sources: [SourceDocument x 7]
   → domains: ["startup_funding", "finance_tax"]
```

### 예시 3: 법률 보충 검색

```
사용자: "직원 해고 시 법적 절차와 퇴직금 계산"

1. classify → [hr_labor]

2. decompose → 단일 도메인, 스킵

3. retrieve
   → hr_labor_db 검색 → 4건
   → 법률 보충 판단: "해고" + "법적 절차" 감지 → True
   → law_common_db 보충 검색 → 4건 추가
   → 총 8건

4. generate → HR_LABOR_PROMPT + 8건 문서

5. evaluate → PASS

6. ChatResponse 반환
   → 근로기준법 + 판례 기반 답변
```

### 예시 4: 재시도 케이스

```
사용자: "스타트업 마케팅 전략과 초기 회계 처리"

1. classify → [startup_funding, finance_tax]

2. decompose → 2개 SubQuery

3. retrieve (1차)
   → startup_funding: 2건 → 평가 FAIL (문서 부족)
   → finance_tax: 5건 → 평가 PASS

4. retrieve (재시도 - startup_funding만)
   → Level 1 (RELAX_PARAMS): K+3=7, 평가 기준 완화 → 여전히 FAIL
   → Level 2 (MULTI_QUERY): 3개 변형 쿼리로 5건 확보 → PASS

5. generate → 통합 응답

6. evaluate → PASS
```

---

## 파일 구조 요약

```
rag/
├── main.py                          # FastAPI 진입점, 서버 초기화
├── agents/
│   ├── base.py                      # BaseAgent 추상 클래스
│   ├── router.py                    # MainRouter (LangGraph 5단계 파이프라인)
│   ├── retrieval_agent.py           # RetrievalAgent (검색 파트 전담)
│   ├── generator.py                 # ResponseGeneratorAgent (생성 파트 전담)
│   ├── evaluator.py                 # EvaluatorAgent (평가 파트 전담)
│   ├── executor.py                  # ActionExecutor (문서 생성)
│   ├── startup_funding.py           # 창업/지원 에이전트
│   ├── finance_tax.py               # 재무/세무 에이전트
│   ├── hr_labor.py                  # 인사/노무 에이전트
│   └── legal.py                     # 법률 에이전트
├── chains/
│   └── rag_chain.py                 # RAGChain (검색+생성 체인, 에이전트 공유)
├── routes/
│   ├── chat.py                      # /api/chat, /api/chat/stream
│   ├── documents.py                 # /api/documents/generate
│   ├── funding.py                   # /api/funding/search
│   ├── evaluate.py                  # /api/evaluate
│   ├── vectordb.py                  # /api/vectordb/*
│   ├── health.py                    # /health
│   └── monitoring.py                # /metrics
├── schemas/
│   ├── request.py                   # ChatRequest, UserContext, CompanyContext
│   └── response.py                  # ChatResponse, SourceDocument, EvaluationResult
├── utils/
│   ├── config/
│   │   ├── settings.py              # Settings (Pydantic BaseSettings, 모든 설정)
│   │   ├── domain_config.py         # DomainConfig (MySQL 기반 도메인 설정)
│   │   ├── domain_data.py           # 하드코딩 도메인 키워드 (DB fallback)
│   │   └── llm.py                   # create_llm() 헬퍼
│   ├── domain_classifier.py         # VectorDomainClassifier (도메인 분류)
│   ├── question_decomposer.py       # QuestionDecomposer (질문 분해)
│   ├── search.py                    # HybridSearcher (BM25+Vector+RRF)
│   ├── query.py                     # MultiQueryRetriever (Multi-Query)
│   ├── reranker.py                  # Reranker (Cross-encoder)
│   ├── retrieval_evaluator.py       # RuleBasedRetrievalEvaluator (검색 평가)
│   ├── legal_supplement.py          # 법률 보충 검색 판단
│   ├── prompts.py                   # 모든 프롬프트 집중 관리
│   ├── cache.py                     # ResponseCache (LRU), LRUCache
│   ├── sanitizer.py                 # 쿼리 입력 정제
│   ├── token_tracker.py             # 토큰 사용량 추적
│   ├── feedback.py                  # SearchStrategy 데이터클래스
│   ├── chat_logger.py               # 채팅 로그 기록
│   ├── middleware.py                # RateLimitMiddleware, MetricsMiddleware
│   ├── chromadb_warmup.py           # ChromaDB BM25 인덱스 사전 빌드
│   └── runpod_warmup.py             # RunPod GPU 워커 사전 예열
├── vectorstores/
│   ├── chroma.py                    # ChromaVectorStore (ChromaDB 래퍼)
│   ├── config.py                    # 컬렉션 매핑, 청킹 전략 설정
│   └── embeddings.py                # RunPodEmbeddings (GPU 임베딩)
└── evaluation/
    ├── __main__.py                  # RAGAS 배치 평가 러너
    └── ragas_evaluator.py           # RagasEvaluator (한국어 프롬프트 포함)
```
