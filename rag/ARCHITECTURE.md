# RAG 아키텍처

> **이 문서는 Bizi RAG 서비스의 상세 아키텍처를 설명합니다.**
> 개발 가이드는 [CLAUDE.md](./CLAUDE.md)를 참조하세요.

## LangGraph 파이프라인 흐름

```
사용자 입력
    │
    ↓
┌─────────────────────────────────────────────────────────────┐
│                  1. 분류 (classify)                          │
│  - LLM API 기반 도메인 분류 (1차)                            │
│  - Fallback: 키워드 매칭 + 벡터 유사도 분류                   │
│  - 키워드 보정(+0.1)을 threshold 판정 전에 적용              │
│  - 도메인 외 질문 시 거부 응답 반환                           │
└────────────────────────┬────────────────────────────────────┘
                         │
                         ↓
┌─────────────────────────────────────────────────────────────┐
│                  2. 분해 (decompose)                         │
│  - 단일 도메인: 분해 없이 통과                               │
│  - 복합 도메인: LLM으로 도메인별 질문 분해 (QuestionDecomposer)│
└────────────────────────┬────────────────────────────────────┘
                         │
        ┌────────────────┼────────────────┐
        ↓                ↓                ↓
┌───────────────┐ ┌───────────────┐ ┌───────────────┐
│ 창업/지원 DB   │ │ 재무/세무 DB   │ │ 인사/노무 DB   │
│   검색         │ │   검색         │ │   검색         │
└───────┬───────┘ └───────┬───────┘ └───────┬───────┘
        │                 │                 │
        └────────────────┬┴─────────────────┘
                         │
                         ↓
┌─────────────────────────────────────────────────────────────┐
│               3. 검색 (retrieve) — RetrievalAgent            │
│  - 쿼리 특성 분석 (SearchStrategySelector, LLM 호출 없음)    │
│  - 적응형 검색 모드 (Hybrid/Vector/BM25/MMR/Exact)           │
│  - 도메인별 문서 예산 할당 (DocumentBudgetCalculator)         │
│  - 규칙 기반 검색 평가 (RuleBasedRetrievalEvaluator)         │
│  - 단계적 재시도 (GraduatedRetryHandler):                    │
│    L1: 파라미터 완화 → L2: Multi-Query → L3: 인접 도메인     │
│  - 법률 보충 검색 (law_common_db)                            │
│  - 복합 도메인 문서 병합 (DocumentMerger, 중복 제거)          │
└────────────────────────┬────────────────────────────────────┘
                         │
                         ↓
┌─────────────────────────────────────────────────────────────┐
│             4. 생성 (generate) — ResponseGeneratorAgent      │
│  - 단일 도메인: 도메인 에이전트 프롬프트 사용                │
│  - 복수 도메인: MULTI_DOMAIN_SYNTHESIS_PROMPT로 LLM 1회 통합 │
│  - 액션 선제안: 생성 전 문서 기반 액션 결정 → 답변에 반영     │
│  - 스트리밍: 토큰 단위 SSE 스트리밍 지원                     │
└────────────────────────┬────────────────────────────────────┘
                         │
                         ↓
┌─────────────────────────────────────────────────────────────┐
│                  5. 평가 (evaluate)                          │
│  - LLM 평가 (선택적, ENABLE_LLM_EVALUATION)                  │
│  - RAGAS 평가 (로깅만, 재시도 없음)                          │
│  - 평가 FAIL 시 generate 재실행 (선택적)                     │
│  - 로그 기록 (logs/ragas.log)                               │
└────────────────────────┬────────────────────────────────────┘
                         │
                         ↓
                 ChatResponse 반환
```

## 통신 아키텍처

```
┌─────────────────────────────────────────────────────────────────┐
│                      Frontend (React + Vite)                    │
│                    localhost:5173                               │
└───────────────────────────┬─────────────────────────────────────┘
                            │ axios (모든 요청)
                            │ /api/* (인증,사용자,기업)
                            │ /rag/* (채팅,AI응답,문서생성)
                            ↓
┌───────────────────────────────────────────────────┐
│              Backend (FastAPI) :8000               │
│                                                    │
│ - Google OAuth2 인증, 사용자/기업 관리              │
│ - 상담 이력 저장, 일정 관리                         │
│ - RAG 프록시 (/rag/*): 사용자 컨텍스트 주입 후 중계 │
└───────────────┬───────────────────┬────────────────┘
                │                   │ httpx 프록시
                ↓                   ↓
        ┌───────────────┐  ┌─────────────────────────────────┐
        │    MySQL      │  │      RAG Service (FastAPI)      │
        │   bizi_db     │  │      localhost:8001             │
        └───────────────┘  │                                 │
                           │ - LangGraph 5단계 파이프라인    │
                           │ - 4개 도메인별 벡터DB           │
                           │ - 평가 모듈 (LLM + RAGAS)       │
                           │ - Action Executor               │
                           └───────────┬─────────────────────┘
                                       │
                                       ↓
                             ┌─────────────────────┐
                             │     ChromaDB        │
                             │   (Vector DB)       │
                             └─────────────────────┘
```

## 벡터DB 구조

```
ChromaDB
├── startup_funding_db/          # 창업/지원/마케팅 전용
│   ├── 창업진흥원 자료
│   ├── 중소벤처기업부 자료
│   ├── 기업마당 공고
│   ├── K-Startup 공고
│   └── 마케팅 가이드
│
├── finance_tax_db/              # 재무/세무 전용
│   ├── 국세청 자료
│   ├── 세법 정보
│   └── 회계 기준
│
├── hr_labor_db/                 # 인사/노무 전용
│   ├── 근로기준법 관련 (법령/시행령/시행규칙)
│   ├── 노동 해석례/판례
│   └── 4대보험 교육자료
│
└── law_common_db/               # 법령/법령해석 (공통)
    ├── 법령 원문
    └── 법령 해석례
```

## 파이프라인 상세

### 1. MainRouter (LangGraph StateGraph)

**역할**: LangGraph StateGraph를 사용한 5단계 파이프라인 조율

```python
class MainRouter:
    """
    LangGraph StateGraph를 사용한 5단계 파이프라인

    주요 속성:
    - domain_classifier: VectorDomainClassifier (지연 로딩)
    - question_decomposer: QuestionDecomposer (지연 로딩)
    - ragas_evaluator: RagasEvaluator (지연 로딩)
    - retrieval_agent: RetrievalAgent (검색 파이프라인 전담)
    - generator: ResponseGeneratorAgent (응답 생성 전담)
    - async_graph: 비동기 StateGraph (async 전용, 동기 graph 제거됨)

    노드 메서드 (async):
    - _aclassify_node(): 도메인 분류
    - _adecompose_node(): 질문 분해
    - _aretrieve_node(): 문서 검색 (→ RetrievalAgent 위임)
    - _agenerate_node(): 답변 생성 (→ ResponseGeneratorAgent 위임)
    - _aevaluate_node(): 품질 평가 (FAIL 시 재시도)
    - _aretry_with_alternatives_node(): 재시도 (대체 쿼리 2개 + 원본, 최고점 반환)
    """
```

### 2. RetrievalAgent (검색 파이프라인 전담)

**역할**: 파이프라인 3단계 검색(retrieve)을 전담하는 오케스트레이터

**핵심 원칙**: LLM 호출 없이 규칙 기반으로 전략 결정 (비용 0, 지연 0)

**구성 요소**:

| 클래스 | 역할 |
|--------|------|
| `SearchStrategySelector` | 쿼리 특성 분석 → 검색 모드 추천 (Hybrid/Vector/BM25/MMR/Exact) |
| `DocumentBudgetCalculator` | 도메인별 문서 할당량(K값) 계산 |
| 단계적 재시도 로직 | 평가 실패 시 L1~L4 단계적 재시도 (RetrievalAgent 내부) |
| 문서 병합 로직 | 복합 도메인 문서 병합, 중복 제거, 우선순위 정렬 (RetrievalAgent 내부) |

**적응형 검색 모드**:

| 모드 | 조건 | 설명 |
|------|------|------|
| `HYBRID` | 기본 | BM25 + Vector + RRF |
| `VECTOR_HEAVY` | 복잡한 질문 (50자+) | vector_weight=0.9 |
| `BM25_HEAVY` | 짧은 사실형 질문 | vector_weight=0.2 |
| `MMR_DIVERSE` | 모호한 질문 | MMR로 다양성 극대화 |
| `EXACT_PLUS_VECTOR` | 법조문 인용 포함 | 정확 매칭 우선 |

**단계적 재시도 (GraduatedRetryHandler)**:

```
Level 1: RELAX_PARAMS    → 평가 기준 완화 + K 증가 (+3)
Level 2: MULTI_QUERY     → LLM 쿼리 확장 (MultiQueryRetriever)
Level 3: CROSS_DOMAIN    → 인접 도메인 검색
Level 4: PARTIAL_ANSWER  → 현재 문서로 진행 (포기)
```

**인접 도메인 매핑** (Level 3에서 사용):
- startup_funding → finance_tax
- finance_tax → startup_funding, law_common
- hr_labor → law_common
- law_common → hr_labor, finance_tax

### 3. ResponseGeneratorAgent (응답 생성 전담)

**역할**: 검색 결과 기반 최종 답변 생성 전담 에이전트

**주요 기능**:
- 단일 도메인: 도메인 에이전트의 시스템 프롬프트를 사용하여 생성
- 복수 도메인: `MULTI_DOMAIN_SYNTHESIS_PROMPT`로 LLM 1회 통합 생성 (기존 N회 → 1회)
- 액션 선제안: 생성 전에 문서 기반으로 액션을 결정하여 답변에 반영 (`ACTION_HINT_TEMPLATE`)
- 토큰 스트리밍: `astream_generate()` / `astream_generate_multi()`로 SSE 스트리밍 지원

**설정**:
- 통합 생성은 항상 활성화 (토글 제거됨)
- `ENABLE_ACTION_AWARE_GENERATION=true`: 액션 선제안 활성화

### 4. 도메인 에이전트 (4개)

#### 4-1. 창업 및 지원 에이전트 (StartupFundingAgent)

**담당 도메인**: 창업, 지원사업, 마케팅
**데이터 소스**: 창업진흥원, 중소벤처기업부, 기업마당 API, K-Startup API

**주요 기능**:
- 사업자 등록 절차 안내
- 법인 설립 가이드
- 업종별 인허가 정보
- 지원사업 검색/필터
- 기업 조건 매칭
- 마케팅 전략 조언

#### 4-2. 재무 및 세무 에이전트 (FinanceTaxAgent)

**담당 도메인**: 세무, 회계, 재무
**데이터 소스**: 국세청 자료, 세법

**주요 기능**:
- 세금 종류별 안내
- 신고/납부 일정
- 세금 계산 가이드
- 회계 기초 안내
- 재무제표 분석

#### 4-3. 인사 및 노무 에이전트 (HRLaborAgent)

**담당 도메인**: 노무, 인사
**데이터 소스**: 근로기준법, 근로기준법 시행령/시행규칙

**주요 기능**:
- Hierarchical RAG (법령 계층 검색)
- 채용/해고 상담
- 근로시간/휴가 안내
- 임금/퇴직금 계산

#### 4-4. 법률 에이전트 (LegalAgent)

**담당 도메인**: 일반 법률, 소송/분쟁, 지식재산권
**데이터 소스**: law_common_db (상법, 민법, 지식재산권법, 법령 해석례)

**주요 기능**:
- 상법/민법/계약법 가이드
- 소송 절차/손해배상 안내
- 특허/상표/저작권 안내
- 단독 처리 + 다른 도메인의 법률 보충 검색 제공

**액션 제안**: 대한법률구조공단, KIPRIS 특허 검색, 국가법령정보센터 링크

### 5. 평가 모듈 (EvaluatorAgent)

**역할**: 답변 품질 평가 + FAIL 시 generate 재실행

**평가 기준** (5개):
- 정확성: 제공된 정보가 사실에 부합하는지
- 완성도: 질문에 대해 충분히 답변했는지
- 관련성: 질문 의도에 맞는 답변인지
- 출처 명시: 법령/규정 인용 시 출처가 있는지
- 검색 품질: 검색된 문서가 질문에 적합한지

**재시도 흐름**: evaluate → FAIL → 대체 쿼리 2개 생성 → 원본+2개=3개 후보 중 최고점 반환 (1회만, `ENABLE_POST_EVAL_RETRY`로 제어)

### 핵심 유틸리티 모듈

| 모듈 | 클래스 | 역할 |
|------|--------|------|
| `domain_classifier.py` | `VectorDomainClassifier` | 벡터 유사도 기반 도메인 분류 |
| `utils/config/domain_config.py` | `DomainConfig` | MySQL 기반 도메인 키워드/규칙/대표쿼리 관리 |
| `question_decomposer.py` | `QuestionDecomposer` | LLM 기반 복합 질문 분해 |
| `retrieval_evaluator.py` | `RuleBasedRetrievalEvaluator` | 규칙 기반 검색 품질 평가 |
| `utils/query.py` | `MultiQueryRetriever` | Multi-Query 재검색 |
| `legal_supplement.py` | `needs_legal_supplement()` | 법률 보충 검색 판단 (키워드 매칭) |
| `token_tracker.py` | `TokenUsageCallbackHandler` | 토큰 사용량 추적 |

### 6. Action Executor

**역할**: 문서 생성 (PDF, HWP)

**생성 가능 문서**:
- 근로계약서
- 취업규칙
- 사업계획서 템플릿

## 3중 평가 체계

RAG 시스템은 세 가지 평가 방식을 지원합니다:

| 구분 | 검색 평가 (retrieval_evaluator.py) | LLM 평가 (evaluator.py) | RAGAS 평가 (evaluation/) |
|------|-----------------------------------|-------------------------|--------------------------|
| 방식 | 규칙 기반 (문서 수, 키워드, 유사도) | LLM이 5개 기준으로 채점 | RAGAS 라이브러리 메트릭 |
| 용도 | 검색 품질 판단 → 단계적 재시도 트리거 | 답변 품질 채점 → FAIL 시 generate 재실행 | 정량적 품질 추적 및 분석 |
| 실행 | RetrievalAgent 검색 단계에서 자동 실행 | `ENABLE_LLM_EVALUATION=true` | `ENABLE_RAGAS_EVALUATION=true` |
| 재시도 | GraduatedRetryHandler (L1~L4 단계적) | 1회 재시도 (`ENABLE_POST_EVAL_RETRY=true` 기본) | 없음 (로깅만) |
| 로그 | 콘솔 | logs/chat.log | logs/ragas.log (JSON Lines) |

## 도메인 분류 상세

### 분류 파이프라인

```
사용자 질문
    │
    ↓
┌───────────────────────────────────────────┐
│ LLM API 기반 도메인 분류 (1차)              │
│   - ENABLE_LLM_DOMAIN_CLASSIFICATION=true │
│   → 성공 시 바로 반환                      │
│   → 실패 시 아래 fallback                  │
└────────────────────┬──────────────────────┘
                     ↓ (fallback)
┌───────────────────────────────────────────┐
│ 키워드 매칭 (kiwipiepy 형태소 분석)         │
│   - DB 기반 키워드 (domain_config.py)      │
│   - 하드코딩 fallback (domain_data.py)     │
│   - 복합 규칙 (2개 이상 lemma 조합)         │
│   → 매칭 시 +0.1 보정 (boosted_confidence) │
└────────────────────┬──────────────────────┘
                     ↓
┌───────────────────────────────────────────┐
│ 벡터 유사도 (HuggingFace embeddings)       │
│   - 대표 쿼리 벡터 centroid 비교            │
│   → boosted_confidence ≥ 0.6 → 통과       │
│   → boosted_confidence < 0.6 → 거부       │
└───────────────────────────────────────────┘
```

### 도메인 설정 관리 (MySQL)

| 테이블 | 역할 |
|--------|------|
| `code` (에이전트 코드) | 도메인-에이전트 매핑 (A0000001~A0000005) |
| `domain_keyword` | 도메인별 키워드 (noun/verb) |
| `domain_compound_rule` | 복합 규칙 (필수 lemma 조합, JSON) |
| `domain_representative_query` | 대표 쿼리 (벡터 centroid 계산용) |

`utils/config/domain_config.py`의 `get_domain_config()` 싱글톤으로 캐시됨.
DB 연결 실패 시 `utils/config/domain_data.py`의 하드코딩 값으로 fallback.

## 데이터 흐름 예시

### 단일 도메인 질문
```
Q: "부가세 신고 기한이 언제인가요?"

1. classify → 키워드 "부가세" 매칭 → finance_tax (신뢰도 0.72)
2. decompose → 단일 도메인이므로 분해 스킵
3. retrieve (RetrievalAgent):
   - 쿼리 분석: BM25_HEAVY (짧은 사실형), K=3
   - finance_tax_db 검색 → 문서 3건, 평가 PASS
4. generate (ResponseGeneratorAgent):
   - FinanceTaxAgent 프롬프트 사용, 액션 선제안
5. evaluate → RAGAS 로깅
6. ChatResponse 반환
```

### 복합 도메인 질문
```
Q: "창업하려는데 사업자등록 방법과 초기 세무 처리 알려주세요"

1. classify → [startup_funding, finance_tax] (키워드 + 벡터)
2. decompose → 2개 SubQuery 생성
   - startup_funding: "사업자등록 방법"
   - finance_tax: "초기 세무 처리"
3. retrieve (RetrievalAgent):
   - 예산 할당: startup_funding=7건, finance_tax=5건
   - 병렬 검색 (asyncio.gather)
   - DocumentMerger: 중복 제거 + 우선순위 정렬
4. generate (ResponseGeneratorAgent):
   - MULTI_DOMAIN_SYNTHESIS_PROMPT로 LLM 1회 통합 생성
5. evaluate → RAGAS 로깅
6. ChatResponse 반환
```

### 단계적 재시도 케이스
```
Q: "창업 절차와 초기 세무 처리"

1. classify → [startup_funding, finance_tax]
2. decompose → 2개 SubQuery 생성
3. retrieve (1차):
   - startup_funding: 문서 1건 → 평가 FAIL
   - finance_tax: 문서 3건 → 평가 PASS
4. retrieve (재시도 - startup_funding):
   - Level 1 (RELAX_PARAMS): K+3 증가, 평가 기준 완화 → FAIL
   - Level 2 (MULTI_QUERY): 3개 변형 쿼리로 문서 4건 확보 → PASS
5. generate → 통합 응답 생성
6. evaluate → RAGAS 로깅
7. ChatResponse 반환
```

### 법률 보충 검색 케이스
```
Q: "직원 해고 시 법적 절차와 퇴직금 계산"

1. classify → [hr_labor] (키워드 "해고", "퇴직금")
2. decompose → 단일 도메인, 분해 스킵
3. retrieve (RetrievalAgent):
   - hr_labor_db 검색 → 문서 5건
   - 법률 보충 판단: "해고" + "법적 절차" 감지
   - law_common_db 보충 검색 → 3건 추가
4. generate → hr_labor 프롬프트 + 보충 법률 문서 포함
5. evaluate → RAGAS 로깅
6. ChatResponse 반환
```
