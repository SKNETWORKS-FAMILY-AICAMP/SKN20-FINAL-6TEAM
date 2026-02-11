# RAG 서비스 상세 가이드

> **Bizi RAG 서비스 아키텍처 및 모듈 상세**

---

## 목차

1. [개요](#1-개요)
2. [전체 아키텍처](#2-전체-아키텍처)
3. [프로젝트 구조](#3-프로젝트-구조)
4. [주요 모듈 상세](#4-주요-모듈-상세)
5. [데이터 흐름 예시](#5-데이터-흐름-예시)

---

## 1. 개요

### 1.1 시스템 특징

Bizi RAG는 4개 도메인(창업/지원사업, 재무/세무, 인사/노무, 법률)을 지원하는 멀티 에이전트 RAG 시스템입니다.

**핵심 기능:**
- 멀티 도메인 질문 자동 분해 처리
- 적응형 검색 전략 (Hybrid/Vector/BM25/MMR)
- 3중 평가 체계 (규칙/LLM/RAGAS)
- 4단계 재시도 메커니즘
- 법률 보충 검색

### 1.2 5단계 파이프라인

Bizi RAG는 LangGraph 기반으로 다음 5단계로 동작합니다:

```
┌─────────────────────────────────────────────────────────────┐
│ 1. 분류 (classify)                                           │
│    - 질문이 어떤 도메인에 속하는지 식별                        │
│    - 키워드 매칭 + 벡터 유사도                                │
│    - 도메인 외 질문은 거부 응답 반환                           │
└────────────────────┬────────────────────────────────────────┘
                     ↓
┌─────────────────────────────────────────────────────────────┐
│ 2. 분해 (decompose)                                          │
│    - 복합 질문을 도메인별로 분해                              │
│    - 예: "창업하려는데 세무는?" → 창업 질문 + 세무 질문       │
└────────────────────┬────────────────────────────────────────┘
                     ↓
┌─────────────────────────────────────────────────────────────┐
│ 3. 검색 (retrieve)                                           │
│    - 도메인별 벡터DB에서 관련 문서 검색                       │
│    - 적응형 검색 전략 (Hybrid/Vector/BM25/MMR)               │
│    - 규칙 기반 품질 평가                                      │
│    - 실패 시 4단계 재시도 메커니즘                            │
└────────────────────┬────────────────────────────────────────┘
                     ↓
┌─────────────────────────────────────────────────────────────┐
│ 4. 생성 (generate)                                           │
│    - 검색된 문서 기반 답변 생성                               │
│    - 단일 도메인: 도메인 에이전트 프롬프트 사용               │
│    - 복수 도메인: 통합 프롬프트로 1회 생성                    │
│    - 액션 제안 포함                                           │
└────────────────────┬────────────────────────────────────────┘
                     ↓
┌─────────────────────────────────────────────────────────────┐
│ 5. 평가 (evaluate)                                           │
│    - LLM 평가 (정확성, 완성도, 관련성, 출처)                 │
│    - FAIL 시 generate 재실행 (선택적)                        │
│    - RAGAS 평가 (로깅용)                                     │
└────────────────────┬────────────────────────────────────────┘
                     ↓
                ChatResponse 반환
```

각 단계는 독립적인 노드로 구현되어 있으며, LangGraph StateGraph로 연결됩니다.

---

## 2. 전체 아키텍처

### 2.1 통신 아키텍처

```
┌─────────────────────────────────────────────────────────────┐
│               Frontend (React + Vite)                       │
│                  localhost:5173                             │
└─────────────┬───────────────────────────┬───────────────────┘
              │                           │
              │ axios (REST API)          │ axios (직접 통신)
              │ (인증, 사용자, 기업)       │ (채팅, AI 응답)
              ↓                           ↓
┌─────────────────────────┐    ┌──────────────────────────────┐
│  Backend (FastAPI)      │    │   RAG Service (FastAPI)      │
│  localhost:8000         │    │   localhost:8001             │
│                         │    │                              │
│ - Google OAuth2 인증    │    │ - MainRouter (5단계)         │
│ - 사용자/기업 관리       │    │ - 6개 에이전트               │
│ - 상담 이력 저장         │    │ - 벡터DB 검색                │
│ - 일정 관리             │    │ - 평가 모듈                  │
└────────────┬────────────┘    └────────────┬─────────────────┘
             │                              │
             ↓                              ↓
     ┌──────────────┐             ┌─────────────────────┐
     │    MySQL     │             │     ChromaDB        │
     │  bizi_db  │             │   (Vector DB)       │
     └──────────────┘             └─────────────────────┘
```

**중요:** RAG 서비스는 Backend를 거치지 않고 Frontend와 직접 통신합니다.

**포트:**
- Frontend: 5173
- Backend: 8000
- RAG: 8001
- MySQL: 3306
- ChromaDB: 8002

### 2.2 LangGraph 파이프라인 다이어그램

```python
# LangGraph StateGraph 구조

START
  │
  ↓
classify_node
  │
  ├─→ [도메인 외 질문] → END (거부 응답)
  │
  ↓
decompose_node
  │
  ├─→ [단일 도메인] → sub_queries = [원본 질문]
  │
  ├─→ [복합 도메인] → sub_queries = [질문1, 질문2, ...]
  │
  ↓
retrieve_node (RetrievalAgent 위임)
  │
  ├─→ 도메인별 병렬 검색
  │
  ├─→ 규칙 기반 평가
  │
  ├─→ [평가 FAIL] → 재시도 (L1~L4)
  │
  ↓
generate_node (ResponseGeneratorAgent 위임)
  │
  ├─→ [단일 도메인] → 도메인 에이전트 프롬프트
  │
  ├─→ [복수 도메인] → 통합 프롬프트
  │
  ↓
evaluate_node
  │
  ├─→ LLM 평가
  │
  ├─→ [FAIL + 재시도 활성화] → generate_node 재실행
  │
  ├─→ [PASS 또는 최대 시도] → RAGAS 로깅
  │
  ↓
END
```

### 2.3 벡터DB 구조

ChromaDB에 4개의 독립된 컬렉션이 있습니다:

```
ChromaDB (localhost:8002)
│
├─ startup_funding_db/
│  ├─ 청킹 전략: 800자 / 100자 오버랩
│  ├─ 데이터 소스:
│  │  ├─ 창업진흥원 가이드
│  │  ├─ 중소벤처기업부 자료
│  │  ├─ 기업마당 공고
│  │  ├─ K-Startup 공고
│  │  └─ 마케팅 가이드
│  └─ 문서 수: ~5,000건
│
├─ finance_tax_db/
│  ├─ 청킹 전략: 600자 / 100자 오버랩
│  ├─ 데이터 소스:
│  │  ├─ 국세청 자료
│  │  ├─ 세법 해설
│  │  └─ 회계 기준
│  └─ 문서 수: ~3,000건
│
├─ hr_labor_db/
│  ├─ 청킹 전략: 1000자 / 150자 오버랩
│  ├─ 데이터 소스:
│  │  ├─ 근로기준법
│  │  ├─ 근로기준법 시행령
│  │  └─ 근로기준법 시행규칙
│  └─ 문서 수: ~2,500건
│
└─ law_common_db/
   ├─ 청킹 전략: 1200자 / 200자 오버랩
   ├─ 데이터 소스:
   │  ├─ 상법
   │  ├─ 민법
   │  ├─ 지식재산권법
   │  └─ 법령 해석례
   └─ 문서 수: ~4,000건
```

**임베딩 모델:**
- HuggingFace `jhgan/ko-sroberta-multitask`
- 차원: 768
- 언어: 한국어 특화

---

## 3. 프로젝트 구조

```
rag/
├── main.py                    # FastAPI 진입점 (11개 엔드포인트)
├── cli.py                     # CLI 테스트 모드
├── requirements.txt           # Python 의존성
├── Dockerfile                 # Docker 이미지
│
├── agents/                    # 에이전트 모듈 (9개 파일)
│   ├── __init__.py
│   ├── base.py                # BaseAgent 추상 클래스
│   ├── router.py              # MainRouter (5단계 파이프라인)
│   ├── retrieval_agent.py     # 검색 전담 에이전트
│   ├── generator.py           # 생성 전담 에이전트
│   ├── evaluator.py           # 평가 에이전트
│   ├── startup_funding.py     # 창업/지원 도메인 에이전트
│   ├── finance_tax.py         # 재무/세무 도메인 에이전트
│   ├── hr_labor.py            # 인사/노무 도메인 에이전트
│   ├── legal.py               # 법률 도메인 에이전트
│   └── executor.py            # 문서 생성 액션 실행자
│
├── chains/                    # LangChain 체인 (1개 파일)
│   ├── __init__.py
│   └── rag_chain.py           # RAG 체인 (검색 + 생성)
│
├── utils/                     # 유틸리티 (18개 파일)
│   ├── __init__.py
│   ├── config.py              # Pydantic Settings
│   ├── prompts.py             # 모든 프롬프트 집중 관리
│   ├── domain_classifier.py   # 도메인 분류 (키워드 + 벡터)
│   ├── domain_config_db.py    # MySQL 도메인 설정 로더
│   ├── question_decomposer.py # LLM 질문 분해
│   ├── search.py              # Hybrid Search, BM25, RRF
│   ├── reranker.py            # Cross-encoder Re-ranking
│   ├── retrieval_evaluator.py # 규칙 기반 검색 평가
│   ├── multi_query.py         # Multi-Query 재검색
│   ├── query.py               # LLM 쿼리 재작성
│   ├── legal_supplement.py    # 법률 보충 검색 판단
│   ├── cache.py               # LRU 캐시
│   ├── token_tracker.py       # 토큰 사용량 추적
│   ├── feedback.py            # 피드백 기반 검색 전략
│   ├── middleware.py          # FastAPI 미들웨어
│   ├── logging_utils.py       # 민감정보 마스킹
│   └── exceptions.py          # 커스텀 예외
│
├── vectorstores/              # 벡터DB 관리 (5개 파일)
│   ├── __init__.py
│   ├── chroma.py              # ChromaVectorStore 클래스
│   ├── config.py              # 컬렉션별 청킹 설정
│   ├── embeddings.py          # 임베딩 모델 로더
│   ├── build_vectordb.py      # 벡터DB 빌드 스크립트
│   └── loader.py              # JSONL 데이터 로더
│
├── schemas/                   # Pydantic 스키마 (2개 파일)
│   ├── __init__.py
│   ├── request.py             # 요청 스키마
│   └── response.py            # 응답 스키마
│
├── evaluation/                # 평가 모듈 (3개 파일)
│   ├── __init__.py
│   ├── ragas_evaluator.py     # RAGAS 평가
│   ├── search_quality_eval.py # 검색 품질 평가
│   └── negative_test_cases.py # 네거티브 테스트 케이스
│
├── tests/                     # 테스트 코드 (19개 파일)
├── logs/                      # 로그 파일
│   ├── chat.log               # 채팅 로그
│   └── ragas.log              # RAGAS 평가 로그 (JSON Lines)
│
├── CLAUDE.md                  # 개발 가이드
├── ARCHITECTURE.md            # 아키텍처 문서
├── README.md                  # 사용법
└── RAG_SERVICE_GUIDE.md       # 이 문서
```

**파일 개수 요약:**
- agents/: 9개
- chains/: 1개
- utils/: 18개
- vectorstores/: 5개
- schemas/: 2개
- evaluation/: 3개
- 총 Python 파일: ~60개

---

## 4. 주요 모듈 상세

이제 각 폴더의 파일들을 상세히 설명합니다.

### 4.1 agents/ - 에이전트 모듈

#### 4.1.1 base.py - BaseAgent 추상 클래스

**역할:** 모든 도메인 에이전트가 상속받는 기본 클래스

**주요 클래스:**

```python
class BaseAgent(ABC):
    domain: str = ""

    @abstractmethod
    def get_system_prompt(self) -> str: ...

    @abstractmethod
    def suggest_actions(self, query: str, response: str) -> list[ActionSuggestion]: ...

    def retrieve_only(self, query: str, ...) -> RetrievalResult: ...
    def generate_only(self, query: str, documents: list[Document], ...) -> str: ...
    def process(self, query: str, ...) -> AgentResponse: ...
```

**핵심 메서드:**

| 메서드 | 역할 | 사용처 |
|--------|------|--------|
| `retrieve_only()` | 문서 검색만 수행, 규칙 기반 평가, Multi-Query 재검색 | RetrievalAgent가 호출 |
| `generate_only()` | 주어진 문서로 답변만 생성 | ResponseGeneratorAgent가 호출 |
| `process()` | 검색 + 생성 통합 (레거시, 현재는 거의 사용 안함) | 개별 에이전트 직접 호출 시 |
| `astream()` | 스트리밍 응답 생성 | main.py의 `/api/chat/stream` |

**데이터 클래스:**

```python
@dataclass
class RetrievalResult:
    """검색 결과"""
    documents: list[Document]  # 검색된 문서
    scores: list[float]  # 유사도 점수
    sources: list[SourceDocument]  # 출처 정보
    evaluation: RetrievalEvaluationResult  # 품질 평가
    used_multi_query: bool  # Multi-Query 사용 여부
    retrieve_time: float  # 검색 소요 시간
    domain: str  # 검색 도메인
    query: str  # 검색 쿼리
    rewritten_query: str | None  # 재작성된 쿼리

@dataclass
class RetrievalEvaluationResult:
    """검색 평가 결과"""
    status: RetrievalStatus  # SUCCESS, NEEDS_RETRY, FAILED
    doc_count: int  # 문서 수
    keyword_match_ratio: float  # 키워드 매칭 비율
    avg_similarity_score: float  # 평균 유사도
    reason: str | None  # 실패/재시도 이유
```

**역할 분리 아키텍처:**
- 과거: 각 에이전트가 검색 + 생성을 모두 수행 → 중복 코드, 일관성 부족
- 현재: `RetrievalAgent`(검색 전담), `ResponseGeneratorAgent`(생성 전담) 분리
- BaseAgent는 이 두 에이전트가 호출할 수 있는 기본 메서드 제공

#### 4.1.2 router.py - MainRouter (5단계 파이프라인)

**역할:** LangGraph StateGraph를 사용한 전체 파이프라인 조율

**클래스 구조:**

```python
class MainRouter:
    """메인 라우터 클래스"""

    def __init__(self, vector_store: ChromaVectorStore | None = None):
        # 공유 인스턴스
        self.vector_store = vector_store or ChromaVectorStore()
        shared_rag_chain = RAGChain(vector_store=self.vector_store)

        # 도메인 에이전트 (4개)
        self.agents = {
            "startup_funding": StartupFundingAgent(rag_chain=shared_rag_chain),
            "finance_tax": FinanceTaxAgent(rag_chain=shared_rag_chain),
            "hr_labor": HRLaborAgent(rag_chain=shared_rag_chain),
            "law_common": LegalAgent(rag_chain=shared_rag_chain),
        }

        # 전담 에이전트
        self.retrieval_agent = RetrievalAgent(...)  # 검색 전담
        self.generator = ResponseGeneratorAgent(...)  # 생성 전담
        self.evaluator = EvaluatorAgent()  # 평가 전담

        # 지연 로딩 속성
        self._domain_classifier = None  # VectorDomainClassifier
        self._question_decomposer = None  # QuestionDecomposer
        self._ragas_evaluator = None  # RagasEvaluator

        # 그래프 빌드
        self.graph = self._build_graph()  # 동기
        self.async_graph = self._build_async_graph()  # 비동기
```

**RouterState (파이프라인 상태):**

```python
class RouterState(TypedDict):
    """5단계를 거치며 누적되는 상태"""
    query: str  # 원본 질문
    history: list[dict]  # 대화 이력
    user_context: UserContext | None  # 사용자 컨텍스트

    # 1단계: 분류
    domains: list[str]  # 분류된 도메인 리스트
    classification_result: DomainClassificationResult | None

    # 2단계: 분해
    sub_queries: list[SubQuery]  # 분해된 서브 쿼리

    # 3단계: 검색
    retrieval_results: dict[str, RetrievalResult]  # 도메인별 검색 결과
    documents: list[Document]  # 병합된 문서
    sources: list[SourceDocument]  # 출처

    # 4단계: 생성
    responses: dict[str, Any]  # 도메인별 응답 (레거시)
    final_response: str  # 최종 통합 답변
    actions: list[ActionSuggestion]  # 추천 액션

    # 5단계: 평가
    evaluation: EvaluationResult | None  # LLM 평가
    ragas_metrics: dict[str, float | None] | None  # RAGAS 메트릭

    # 재시도
    retry_count: int  # generate 재시도 횟수

    # 메트릭
    timing_metrics: dict[str, Any]  # 단계별 소요 시간
```

**노드 메서드:**

```python
def _classify_node(self, state: RouterState) -> dict:
    """1. 분류 - 도메인 식별 (키워드 + 벡터), 도메인 외 질문 거부"""
    result = self.domain_classifier.classify(state["query"])
    return {"domains": result.domains, ...}

def _decompose_node(self, state: RouterState) -> dict:
    """2. 분해 - 단일 도메인은 스킵, 복합 도메인은 LLM 분해"""
    if len(state["domains"]) == 1:
        return {"sub_queries": [SubQuery(...)]}
    return {"sub_queries": self.question_decomposer.decompose(...)}

def _retrieve_node(self, state: RouterState) -> dict:
    """3. 검색 - RetrievalAgent 위임 (병렬 검색, 평가, 재시도, 병합)"""
    results = self.retrieval_agent.retrieve_all(state["sub_queries"], ...)
    return {"retrieval_results": results, "documents": merged_docs, ...}

def _generate_node(self, state: RouterState) -> dict:
    """4. 생성 - ResponseGeneratorAgent 위임 (단일/복수 도메인 자동 분기)"""
    result = self.generator.generate(state["query"], state["documents"], ...)
    return {"final_response": result.content, "actions": result.actions}

def _evaluate_node(self, state: RouterState) -> dict:
    """5. 평가 - LLM 평가, FAIL 시 generate 재실행, RAGAS 로깅"""
    evaluation = self.evaluator.evaluate(...)
    if not evaluation.passed and state["retry_count"] < max_retry:
        return {"evaluation": evaluation, "retry_count": state["retry_count"] + 1}
    return {"evaluation": evaluation, "ragas_metrics": ...}
```

**그래프 빌드:**

```python
graph = StateGraph(RouterState)
graph.add_node("classify", self._classify_node)
graph.add_node("decompose", self._decompose_node)
graph.add_node("retrieve", self._retrieve_node)
graph.add_node("generate", self._generate_node)
graph.add_node("evaluate", self._evaluate_node)

graph.set_entry_point("classify")
graph.add_conditional_edges("classify", lambda s: "decompose" if s["domains"] else END)
graph.add_edge("decompose", "retrieve")
graph.add_edge("retrieve", "generate")
graph.add_edge("generate", "evaluate")
graph.add_conditional_edges("evaluate", lambda s: "generate" if needs_retry(s) else END)
```

**주요 메서드:**

```python
def route(self, query, ...) -> ChatResponse:
    """동기 라우팅 (CLI/테스트)"""
    state = self.graph.invoke({"query": query, ...})
    return ChatResponse(...)

async def aroute(self, ...) -> ChatResponse:
    """비동기 라우팅 (API)"""
    state = await self.async_graph.ainvoke(...)
    return ChatResponse(...)

async def astream_route(self, ...) -> AsyncGenerator:
    """스트리밍 라우팅 (SSE)"""
    # classify, decompose, retrieve 사전 실행
    # generate만 스트리밍
    async for token in self.generator.astream_generate(...):
        yield token
```

**사용처:**
- `main.py`의 모든 채팅 엔드포인트가 MainRouter 사용
- `/api/chat` → `router.aroute()`
- `/api/chat/stream` → `router.astream_route()`

#### 4.1.3 retrieval_agent.py - 검색 전담 에이전트

**역할:** 파이프라인 3단계 검색(retrieve)을 전담하는 오케스트레이터

**핵심 원칙:** LLM 호출 없이 규칙 기반으로 전략 결정 (비용 0, 지연 0)

**클래스 구조:**

```python
class RetrievalAgent:
    """검색 전략 에이전트"""

    def __init__(self, agents: dict[str, BaseAgent], rag_chain: RAGChain, vector_store: ChromaVectorStore):
        self.agents = agents  # 도메인 에이전트 4개
        self.rag_chain = rag_chain
        self.vector_store = vector_store
        self.settings = get_settings()

        # 구성 요소 (LLM 없음, 규칙 기반)
        self.strategy_selector = SearchStrategySelector()
        self.budget_calculator = DocumentBudgetCalculator()
        self.retry_handler = GraduatedRetryHandler()
        self.document_merger = DocumentMerger()
        self.evaluator = RuleBasedRetrievalEvaluator()
```

**구성 요소 상세:**

**1) SearchStrategySelector - 쿼리 특성 분석**

```python
class SearchStrategySelector:
    def analyze_query(self, query: str) -> QueryCharacteristics:
        """쿼리 분석 (LLM 없음, 규칙 기반)"""
        # 길이, 키워드 밀도, 법조문 인용 여부 등 분석
        # 규칙 기반 검색 모드 추천:
        # - 법조문 인용 → EXACT_PLUS_VECTOR
        # - 짧은 사실형 → BM25_HEAVY
        # - 복잡한 질문 → VECTOR_HEAVY
        # - 모호한 질문 → MMR_DIVERSE
        # - 기본 → HYBRID
        return QueryCharacteristics(...)
```

**검색 모드:**

| 모드 | 조건 | 설명 | K값 |
|------|------|------|-----|
| `EXACT_PLUS_VECTOR` | 법조문 인용 포함 | 정확 매칭 우선 + 벡터 보조 | 5 |
| `BM25_HEAVY` | 짧은 사실형 질문 | BM25 가중치 높임 (vector_weight=0.2) | 3 |
| `VECTOR_HEAVY` | 복잡한 질문 (50자+) | 벡터 가중치 높임 (vector_weight=0.9) | 7 |
| `MMR_DIVERSE` | 모호한 질문 | MMR로 다양성 극대화 | 10 |
| `HYBRID` | 기본 | BM25 + Vector + RRF (vector_weight=0.7) | 5 |

**2) DocumentBudgetCalculator - 도메인별 문서 할당**

```python
class DocumentBudgetCalculator:
    def calculate(self, sub_queries: list[SubQuery], total_k: int = 12) -> dict[str, DocumentBudget]:
        """질문 길이/복잡도 기반 우선순위 계산 → 비례 배분 (최소 3개)"""
        # 예: 총 K=12, 도메인 2개 → startup_funding=7, finance_tax=5
        return budgets
```

**3) GraduatedRetryHandler - 단계적 재시도**

```python
class GraduatedRetryHandler:
    def get_next_strategy(self, context, evaluation) -> RetryLevel:
        """실패 상황 분석 → 다음 레벨 결정"""
        # 문서 0개 → CROSS_DOMAIN
        # 키워드 매칭 낮음 → MULTI_QUERY
        # 기타 → RELAX_PARAMS
        return level

    def apply_retry(self, level: RetryLevel, ...) -> RetrievalResult:
        """레벨별 재시도 실행:
        L1: RELAX_PARAMS - 기준 완화, K+3
        L2: MULTI_QUERY - LLM 쿼리 확장 (3개)
        L3: CROSS_DOMAIN - 인접 도메인 검색
        L4: PARTIAL_ANSWER - 현재 문서로 진행
        """
        ...
```

**인접 도메인 매핑:**

```python
ADJACENT_DOMAINS = {
    "startup_funding": ["finance_tax"],  # 창업 → 세무
    "finance_tax": ["startup_funding", "law_common"],  # 세무 → 창업, 법률
    "hr_labor": ["law_common"],  # 노무 → 법률
    "law_common": ["hr_labor", "finance_tax"],  # 법률 → 노무, 세무
}
```

**4) DocumentMerger - 문서 병합**

```python
class DocumentMerger:
    """복합 도메인 문서 병합, 중복 제거, 우선순위 정렬"""

    def merge(self, results: dict[str, RetrievalResult]) -> list[Document]:
        """
        1. 중복 제거 (page_content 해시 기반)
        2. 우선순위 정렬 (도메인 우선순위 + 유사도)
        """
        seen_hashes = set()
        merged = []

        # 도메인별 우선순위 정렬
        sorted_domains = sorted(
            results.keys(),
            key=lambda d: results[d].evaluation.avg_similarity_score,
            reverse=True,
        )

        for domain in sorted_domains:
            result = results[domain]
            for doc, score in zip(result.documents, result.scores):
                doc_hash = hashlib.md5(doc.page_content.encode()).hexdigest()

                if doc_hash not in seen_hashes:
                    seen_hashes.add(doc_hash)
                    doc.metadata["merge_score"] = score
                    merged.append(doc)

        # 최종 정렬 (merge_score 기준)
        merged.sort(key=lambda d: d.metadata.get("merge_score", 0.0), reverse=True)

        return merged
```

**주요 메서드:**

```python
def retrieve_all(self, sub_queries: list[SubQuery], user_context: UserContext | None = None) -> dict[str, RetrievalResult]:
    """모든 서브 쿼리에 대해 검색 수행"""

    # 1. 쿼리 특성 분석
    characteristics = {}
    for sq in sub_queries:
        characteristics[sq.domain] = self.strategy_selector.analyze_query(sq.query)

    # 2. 문서 예산 할당
    if len(sub_queries) > 1:
        budgets = self.budget_calculator.calculate(sub_queries)
    else:
        budgets = {sub_queries[0].domain: DocumentBudget(domain=..., allocated_k=5, ...)}

    # 3. 도메인별 병렬 검색
    results = {}
    for sq in sub_queries:
        agent = self.agents[sq.domain]
        char = characteristics[sq.domain]
        budget = budgets[sq.domain]

        # 1차 검색
        result = agent.retrieve_only(
            query=sq.query,
            k=budget.allocated_k,
        )

        # 평가 + 재시도
        retry_context = RetryContext()
        while not result.evaluation.passed and retry_context.attempts < 3:
            next_level = self.retry_handler.get_next_strategy(retry_context, result.evaluation)
            result = self.retry_handler.apply_retry(next_level, agent, sq.query, ...)
            retry_context.attempts += 1

        # 법률 보충 검색 판단
        if sq.domain != "law_common" and needs_legal_supplement(sq.query, result.documents):
            legal_result = self.agents["law_common"].retrieve_only(
                query=sq.query,
                k=self.settings.legal_supplement_k,
            )
            result.documents.extend(legal_result.documents[:3])

        results[sq.domain] = result

    return results
```

**사용처:**
- `MainRouter._retrieve_node()`가 호출
- 검색 파이프라인의 모든 로직이 여기 집중

#### 4.1.4 generator.py - 생성 전담 에이전트

**역할:** 검색된 문서 기반 최종 답변 생성 전담

**클래스 구조:**

```python
class ResponseGeneratorAgent:
    """응답 생성 전담 에이전트"""

    def __init__(self, agents: dict[str, BaseAgent], rag_chain: RAGChain):
        self.settings = get_settings()
        self.agents = agents
        self.rag_chain = rag_chain

    def _get_llm(self) -> ChatOpenAI:
        return ChatOpenAI(
            model=self.settings.openai_model,
            temperature=self.settings.openai_temperature,
            api_key=self.settings.openai_api_key,
            callbacks=[TokenUsageCallbackHandler("생성")],
        )
```

**핵심 기능:**

**1) 액션 선제안 (Action-Aware Generation)**

```python
def _suggest_actions_for_domains(self, query: str, documents: list[Document], domains: list[str]) -> list[ActionSuggestion]:
    """생성 전에 액션을 미리 결정"""

    actions = []

    for domain in domains:
        agent = self.agents[domain]
        # 각 도메인 에이전트의 suggest_actions 호출
        # 응답 텍스트 없이도 문서만으로 액션 판단 가능
        domain_actions = agent.suggest_actions(query, "")  # response="" (빈 문자열)
        actions.extend(domain_actions)

    return actions

def _build_action_hint(self, actions: list[ActionSuggestion]) -> str:
    """액션을 프롬프트 힌트로 변환"""
    if not actions:
        return ""

    hints = [f"- {action.label}" for action in actions]
    return ACTION_HINT_TEMPLATE.format(actions="\n".join(hints))
```

**2) 단일 도메인 생성**

```python
def generate_single(self, query: str, documents: list[Document], domain: str, ...) -> GenerationResult:
    """단일 도메인 답변 생성"""

    agent = self.agents[domain]

    # 액션 선제안
    actions = self._suggest_actions_for_domains(query, documents, [domain])
    action_hint = self._build_action_hint(actions)

    # 컨텍스트 포맷팅
    context = self.rag_chain.format_context(documents)

    # 프롬프트 구성 (도메인 에이전트의 시스템 프롬프트 사용)
    prompt = ChatPromptTemplate.from_messages([
        ("system", agent.get_system_prompt() + "\n\n" + action_hint),
        ("human", "{query}"),
    ])

    # LLM 호출
    llm = self._get_llm()
    chain = prompt | llm | StrOutputParser()
    content = chain.invoke({"query": query, "context": context, ...})

    return GenerationResult(
        content=content,
        actions=actions,
        sources=self.rag_chain.documents_to_sources(documents),
    )
```

**3) 복수 도메인 통합 생성**

```python
def generate_multi(self, query: str, documents: list[Document], domains: list[str], ...) -> GenerationResult:
    """복수 도메인 답변 통합 생성 (LLM 1회 호출)"""

    # 과거: 도메인마다 LLM 호출 → 응답 수동 병합 (N회 호출)
    # 현재: 통합 프롬프트로 LLM 1회 호출

    # 액션 선제안
    actions = self._suggest_actions_for_domains(query, documents, domains)
    action_hint = self._build_action_hint(actions)

    # 도메인별 문서 그룹화
    domain_contexts = {}
    for domain in domains:
        domain_docs = [d for d in documents if d.metadata.get("domain") == domain]
        domain_contexts[domain] = self.rag_chain.format_context(domain_docs)

    # 통합 프롬프트 사용
    prompt = ChatPromptTemplate.from_messages([
        ("system", MULTI_DOMAIN_SYNTHESIS_PROMPT + "\n\n" + action_hint),
        ("human", "{query}"),
    ])

    llm = self._get_llm()
    chain = prompt | llm | StrOutputParser()

    content = chain.invoke({
        "query": query,
        "domains": domains,
        "domain_contexts": domain_contexts,
        ...
    })

    return GenerationResult(
        content=content,
        actions=actions,
        sources=self.rag_chain.documents_to_sources(documents),
    )
```

**통합 프롬프트 (MULTI_DOMAIN_SYNTHESIS_PROMPT):**

```python
MULTI_DOMAIN_SYNTHESIS_PROMPT = """
당신은 여러 전문 분야의 지식을 통합하여 답변하는 경영 상담 전문가입니다.

다음 도메인의 정보를 참고하여 답변하세요:
{domains}

각 도메인별 컨텍스트:
{domain_contexts}

**답변 작성 규칙:**
1. 도메인 간 연관성을 명확히 설명하세요
2. 단계별로 구조화하여 작성하세요
3. 각 도메인의 정보를 골고루 활용하세요
4. 출처를 명시하세요

사용자 유형: {user_type}
기업 정보: {company_context}
"""
```

**4) 스트리밍 생성**

```python
async def astream_generate(self, query: str, documents: list[Document], domain: str, ...) -> AsyncGenerator[str, None]:
    """단일 도메인 스트리밍 생성"""

    agent = self.agents[domain]

    # 액션 선제안
    actions = self._suggest_actions_for_domains(query, documents, [domain])
    action_hint = self._build_action_hint(actions)

    # 프롬프트
    prompt = ChatPromptTemplate.from_messages([
        ("system", agent.get_system_prompt() + "\n\n" + action_hint),
        ("human", "{query}"),
    ])

    # LLM 스트리밍
    llm = self._get_llm()
    chain = prompt | llm

    async for chunk in chain.astream({"query": query, "context": context, ...}):
        if hasattr(chunk, "content"):
            yield chunk.content

async def astream_generate_multi(self, ...) -> AsyncGenerator[str, None]:
    """복수 도메인 스트리밍 생성"""
    # 통합 프롬프트 사용
    prompt = ChatPromptTemplate.from_messages([
        ("system", MULTI_DOMAIN_SYNTHESIS_PROMPT + "\n\n" + action_hint),
        ("human", "{query}"),
    ])

    llm = self._get_llm()
    chain = prompt | llm

    async for chunk in chain.astream(...):
        if hasattr(chunk, "content"):
            yield chunk.content
```

**주요 메서드:**

```python
def generate(self, query: str, documents: list[Document], domains: list[str], ...) -> GenerationResult:
    """도메인 수에 따라 자동 분기"""
    if len(domains) == 1:
        return self.generate_single(query, documents, domains[0], ...)
    else:
        return self.generate_multi(query, documents, domains, ...)

async def agenerate(self, ...) -> GenerationResult:
    """비동기 생성"""
    pass

async def astream(self, ...) -> AsyncGenerator[str, None]:
    """스트리밍 생성 (도메인 수에 따라 자동 분기)"""
    if len(domains) == 1:
        async for token in self.astream_generate(...):
            yield token
    else:
        async for token in self.astream_generate_multi(...):
            yield token
```

**사용처:**
- `MainRouter._generate_node()`가 호출
- `MainRouter.astream_route()`도 호출 (스트리밍)

#### 4.1.5 도메인 에이전트 4개

모든 도메인 에이전트는 `BaseAgent`를 상속하며, 다음 2개 메서드를 구현합니다:
- `get_system_prompt()` - 도메인별 시스템 프롬프트
- `suggest_actions()` - 도메인별 추천 액션

**도메인 에이전트 4개:**

각 에이전트는 `BaseAgent` 상속, `get_system_prompt()`와 `suggest_actions()` 구현

```python
class StartupFundingAgent(BaseAgent):
    domain = "startup_funding"
    # 액션: 지원사업 찾기, 정부24 링크, 사업계획서 템플릿

class FinanceTaxAgent(BaseAgent):
    domain = "finance_tax"
    # 액션: 홈택스 링크, 회계 프로그램 추천

class HRLaborAgent(BaseAgent):
    domain = "hr_labor"
    # 액션: 근로계약서 생성, 취업규칙 생성, 4대보험 정보센터 링크

class LegalAgent(BaseAgent):
    domain = "law_common"
    # 액션: 법률구조공단, KIPRIS 특허검색, 국가법령정보센터, 계약서 검토
```

**프롬프트:** `utils/prompts.py`에 도메인별 시스템 프롬프트 정의 (전문 분야, 답변 규칙, 컨텍스트 포맷)

#### 4.1.6 evaluator.py - 평가 에이전트

**역할:** 생성된 답변의 품질을 LLM으로 평가

```python
class EvaluatorAgent:
    """답변 품질 평가 에이전트"""

    def __init__(self):
        self.settings = get_settings()
        self.llm = ChatOpenAI(
            model=self.settings.openai_model,
            temperature=0.0,  # 평가는 일관성 중요
            api_key=self.settings.openai_api_key,
            callbacks=[TokenUsageCallbackHandler("평가")],
        )

    def evaluate(self, query: str, response: str, documents: list[Document]) -> EvaluationResult:
        """답변 품질 평가"""

        if not self.settings.enable_llm_evaluation:
            # 평가 비활성화 시 항상 PASS
            return EvaluationResult(
                score=1.0,
                passed=True,
                feedback=None,
            )

        # 컨텍스트 포맷팅
        context = "\n\n".join([
            f"[문서 {i+1}]\n{doc.page_content}"
            for i, doc in enumerate(documents[:5])  # 최대 5개
        ])

        # 평가 프롬프트
        prompt = ChatPromptTemplate.from_messages([
            ("system", EVALUATION_PROMPT),
            ("human", "질문: {query}\n\n답변: {response}\n\n참고 문서:\n{context}"),
        ])

        # LLM 평가 (JSON 출력)
        chain = prompt | self.llm | JsonOutputParser()

        try:
            result = chain.invoke({
                "query": query,
                "response": response,
                "context": context,
            })

            score = result.get("score", 0.0)
            passed = score >= self.settings.evaluation_threshold  # 기본 0.7
            feedback = result.get("feedback", "")

            return EvaluationResult(
                score=score,
                passed=passed,
                feedback=feedback,
                details=result,  # 상세 평가 (정확성, 완성도, 관련성, 출처)
            )

        except Exception as e:
            logger.error("[평가] LLM 평가 실패: %s", e)
            # 실패 시 PASS (안전장치)
            return EvaluationResult(score=1.0, passed=True, feedback=None)
```

**평가 프롬프트 (EVALUATION_PROMPT):**

```python
EVALUATION_PROMPT = """
당신은 RAG 시스템 답변 평가자입니다.

다음 4가지 기준으로 답변을 평가하세요:

1. **정확성 (Accuracy)**: 제공된 정보가 사실에 부합하는가? (0.0-1.0)
2. **완성도 (Completeness)**: 질문에 대해 충분히 답변했는가? (0.0-1.0)
3. **관련성 (Relevance)**: 질문 의도에 맞는 답변인가? (0.0-1.0)
4. **출처 명시 (Citation)**: 법령/규정 인용 시 출처가 있는가? (0.0-1.0)

**평가 기준:**
- 참고 문서에 없는 내용을 답변했으면 정확성 감점
- 질문에서 요구한 정보가 빠졌으면 완성도 감점
- 질문과 무관한 내용이 많으면 관련성 감점
- 법령 언급 시 조항 번호가 없으면 출처 감점

**출력 형식 (JSON):**
{
    "accuracy": 0.0-1.0,
    "completeness": 0.0-1.0,
    "relevance": 0.0-1.0,
    "citation": 0.0-1.0,
    "score": (4가지 평균),
    "feedback": "개선 사항 (FAIL 시에만)"
}

**주의:** 평가는 엄격하게 하되, 사소한 표현 차이는 감점하지 마세요.
"""
```

**EvaluationResult 스키마:**

```python
@dataclass
class EvaluationResult:
    """평가 결과"""
    score: float  # 0.0-1.0
    passed: bool  # score >= threshold
    feedback: str | None  # 개선 사항 (FAIL 시)
    details: dict | None  # 상세 평가 (accuracy, completeness, relevance, citation)
```

**사용처:**
- `MainRouter._evaluate_node()`가 호출
- FAIL 시 generate_node 재실행

#### 4.1.7 executor.py - 문서 생성 액션 실행자

**역할:** 사용자가 액션 버튼을 클릭하면 문서를 생성 (PDF, HWP)

```python
class ActionExecutor:
    """액션 실행자"""

    def __init__(self):
        self.settings = get_settings()
        self.template_dir = Path(__file__).parent.parent / "templates"

    def execute(self, action: ActionSuggestion, params: dict) -> dict:
        """액션 실행"""

        if action.type == "document_generation":
            return self._generate_document(action.params["template"], params)

        elif action.type == "funding_search":
            return self._search_funding(params)

        elif action.type == "external_link":
            return {"url": action.params["url"]}

        else:
            raise ValueError(f"Unknown action type: {action.type}")

    def _generate_document(self, template: str, params: dict) -> dict:
        """문서 생성"""

        if template == "employment_contract":
            # 근로계약서 생성
            pdf_path = self._generate_employment_contract(params)
            return {"file_path": str(pdf_path), "file_type": "pdf"}

        elif template == "business_plan":
            # 사업계획서 템플릿
            hwp_path = self._generate_business_plan(params)
            return {"file_path": str(hwp_path), "file_type": "hwp"}

        elif template == "work_rules":
            # 취업규칙 생성
            pdf_path = self._generate_work_rules(params)
            return {"file_path": str(pdf_path), "file_type": "pdf"}

        else:
            raise ValueError(f"Unknown template: {template}")
```

**생성 가능 문서:**

| 템플릿 | 설명 | 파일 형식 |
|--------|------|----------|
| `employment_contract` | 근로계약서 | PDF |
| `work_rules` | 취업규칙 | PDF |
| `payroll` | 급여명세서 | PDF |
| `vacation_ledger` | 연차관리대장 | XLSX |
| `business_plan` | 사업계획서 | HWP |

**사용처:**
- `main.py`의 `/api/actions/execute` 엔드포인트

---

### 4.2 chains/ - RAG 체인

#### 4.2.1 rag_chain.py - RAG 체인

**역할:** 벡터 스토어 검색 + LLM 응답 생성을 하나의 체인으로 묶음

**클래스 구조:**

```python
class RAGChain:
    """RAG 체인 클래스"""

    def __init__(self, vector_store: ChromaVectorStore | None = None):
        self.settings = get_settings()
        self.vector_store = vector_store or ChromaVectorStore()
        self.llm = ChatOpenAI(
            model=self.settings.openai_model,
            temperature=self.settings.openai_temperature,
            api_key=self.settings.openai_api_key,
            callbacks=[TokenUsageCallbackHandler("생성")],
        )

        # 고급 기능 (지연 로딩)
        self._query_processor = None  # QueryProcessor (쿼리 재작성)
        self._response_cache = None  # ResponseCache (LRU 캐시)
        self._hybrid_searcher = None  # HybridSearcher (Hybrid Search)
        self._reranker = None  # Reranker (Re-ranking)
```

**핵심 메서드:**

**1) retrieve() - 문서 검색**

```python
def retrieve(
    self,
    query: str,
    domain: str,
    k: int | None = None,
    include_common: bool = False,
    search_strategy: SearchStrategy | None = None,
) -> list[Document]:
    """문서 검색"""

    # 1. 쿼리 재작성 (선택적)
    if self.settings.enable_query_rewrite and self.query_processor:
        rewritten_query = self.query_processor.rewrite(query)
    else:
        rewritten_query = query

    # 2. 검색 모드 결정
    if search_strategy:
        # 피드백 기반 전략 사용
        search_mode = search_strategy.mode
        k = search_strategy.k or k or self.settings.default_k
    else:
        # 기본 전략
        search_mode = "hybrid" if self.settings.enable_hybrid_search else "vector"
        k = k or self.settings.default_k

    # 3. 도메인 컬렉션 결정
    collection_name = f"{domain}_db"

    # 4. 검색 실행
    if search_mode == "hybrid":
        # Hybrid Search (BM25 + Vector + RRF)
        documents = self.hybrid_searcher.search(
            query=rewritten_query,
            collection_name=collection_name,
            k=k,
            weight=self.settings.vector_search_weight,
        )
    else:
        # Vector Search (기본)
        documents = self.vector_store.similarity_search(
            query=rewritten_query,
            collection_name=collection_name,
            k=k,
        )

    # 5. Re-ranking (선택적)
    if self.settings.enable_reranking and self.reranker:
        documents = self.reranker.rerank(
            query=rewritten_query,
            documents=documents,
            top_k=k,
        )

    # 6. 공통 법령 DB 병합 (선택적)
    if include_common:
        common_docs = self.vector_store.similarity_search(
            query=rewritten_query,
            collection_name="law_common_db",
            k=3,
        )
        documents = documents + common_docs

    return documents
```

**2) format_context() - 컨텍스트 포맷팅**

```python
def format_context(self, documents: list[Document]) -> str:
    """문서를 LLM 컨텍스트 형식으로 변환"""

    if not documents:
        return "검색된 문서가 없습니다."

    context_parts = []
    for i, doc in enumerate(documents):
        source = doc.metadata.get("source", "알 수 없음")
        content = doc.page_content

        # 너무 긴 문서는 잘라내기
        if len(content) > 2000:
            content = content[:2000] + "..."

        context_parts.append(f"[문서 {i+1}] (출처: {source})\n{content}")

    return "\n\n---\n\n".join(context_parts)
```

**3) documents_to_sources() - 출처 추출**

```python
def documents_to_sources(self, documents: list[Document]) -> list[SourceDocument]:
    """문서에서 출처 정보 추출"""

    sources = []
    for doc in documents:
        sources.append(SourceDocument(
            title=doc.metadata.get("title", "제목 없음"),
            source=doc.metadata.get("source", "출처 없음"),
            url=doc.metadata.get("url"),
            page=doc.metadata.get("page"),
        ))

    # 중복 제거 (title + source 기준)
    unique_sources = []
    seen = set()
    for src in sources:
        key = (src.title, src.source)
        if key not in seen:
            seen.add(key)
            unique_sources.append(src)

    return unique_sources
```

**4) invoke() - 검색 + 생성 통합**

```python
def invoke(
    self,
    query: str,
    domain: str,
    system_prompt: str,
    user_type: str = "예비 창업자",
    company_context: str = "정보 없음",
    search_strategy: SearchStrategy | None = None,
) -> dict:
    """검색 + 생성 통합 실행"""

    start = time.time()

    # 1. 검색
    retrieve_start = time.time()
    documents = self.retrieve(
        query=query,
        domain=domain,
        search_strategy=search_strategy,
    )
    retrieve_time = time.time() - retrieve_start

    # 2. 컨텍스트 포맷팅
    context = self.format_context(documents)

    # 3. 프롬프트 구성
    prompt = ChatPromptTemplate.from_messages([
        ("system", system_prompt),
        ("human", "{query}"),
    ])

    # 4. LLM 생성
    generate_start = time.time()
    chain = prompt | self.llm | StrOutputParser()
    content = chain.invoke({
        "query": query,
        "context": context,
        "user_type": user_type,
        "company_context": company_context,
    })
    generate_time = time.time() - generate_start

    # 5. 출처 추출
    sources = self.documents_to_sources(documents)

    return {
        "content": content,
        "sources": sources,
        "documents": documents,
        "retrieve_time": retrieve_time,
        "generate_time": generate_time,
        "total_time": time.time() - start,
    }
```

**5) astream() - 스트리밍 생성**

```python
async def astream(
    self,
    query: str,
    domain: str,
    system_prompt: str,
    user_type: str = "예비 창업자",
    company_context: str = "정보 없음",
    context_override: str | None = None,
) -> AsyncGenerator[str, None]:
    """스트리밍 생성 (검색은 사전 실행 가정)"""

    # 1. 컨텍스트 준비
    if context_override:
        context = context_override
    else:
        # 검색 수행
        documents = await asyncio.to_thread(
            self.retrieve,
            query,
            domain,
        )
        context = self.format_context(documents)

    # 2. 프롬프트
    prompt = ChatPromptTemplate.from_messages([
        ("system", system_prompt),
        ("human", "{query}"),
    ])

    # 3. 스트리밍 LLM 호출
    chain = prompt | self.llm

    async for chunk in chain.astream({
        "query": query,
        "context": context,
        "user_type": user_type,
        "company_context": company_context,
    }):
        if hasattr(chunk, "content"):
            yield chunk.content
```

**사용처:**
- 모든 에이전트가 RAGChain 인스턴스를 공유
- BaseAgent의 retrieve_context(), generate_only() 등에서 사용

---

### 4.3 utils/ - 유틸리티 모듈

utils 폴더에는 18개 파일이 있습니다. 주요 파일만 상세히 설명합니다.

#### 4.3.1 config.py - 설정 관리

**역할:** Pydantic BaseSettings로 환경 변수 관리

```python
class Settings(BaseSettings):
    """RAG 설정"""

    # OpenAI
    openai_api_key: str
    openai_model: str = "gpt-4o-mini"
    openai_temperature: float = 0.3

    # ChromaDB
    chroma_host: str = "localhost"
    chroma_port: int = 8002
    chroma_persist_directory: str = "./chroma_db"

    # 검색 설정
    default_k: int = 5
    enable_hybrid_search: bool = True
    vector_search_weight: float = 0.7
    enable_reranking: bool = True
    enable_query_rewrite: bool = True

    # 도메인 분류
    enable_domain_rejection: bool = True
    domain_classification_threshold: float = 0.6
    enable_llm_domain_classification: bool = False

    # 평가
    enable_llm_evaluation: bool = True
    evaluation_threshold: float = 0.7
    enable_post_eval_retry: bool = False
    max_retry: int = 2
    enable_ragas_evaluation: bool = False

    # Multi-Query
    enable_multi_query: bool = True
    multi_query_count: int = 3

    # 법률 보충 검색
    enable_legal_supplement: bool = True
    legal_supplement_k: int = 3

    # 캐시
    enable_response_cache: bool = True
    cache_max_size: int = 500
    cache_ttl: int = 3600

    # 타임아웃
    llm_timeout: float = 30.0

    class Config:
        env_file = ".env"

@lru_cache
def get_settings() -> Settings:
    """싱글톤 설정 인스턴스"""
    return Settings()
```

**사용법:**

```python
from utils.config import get_settings

settings = get_settings()
print(settings.openai_model)  # "gpt-4o-mini"
```

#### 4.3.2 prompts.py - 프롬프트 집중 관리

**역할:** 모든 프롬프트를 한 곳에서 관리 (하드코딩 방지)

```python
# 도메인 에이전트 프롬프트
STARTUP_FUNDING_PROMPT = "..."
FINANCE_TAX_PROMPT = "..."
HR_LABOR_PROMPT = "..."
LEGAL_PROMPT = "..."

# 복합 도메인 통합 프롬프트
MULTI_DOMAIN_SYNTHESIS_PROMPT = """
당신은 여러 전문 분야의 지식을 통합하여 답변하는 경영 상담 전문가입니다.
...
"""

# 액션 힌트 템플릿
ACTION_HINT_TEMPLATE = """
사용자에게 다음 액션을 제안할 수 있습니다:
{actions}

답변 마지막에 이 액션들을 자연스럽게 언급하세요.
"""

# 평가 프롬프트
EVALUATION_PROMPT = "..."

# LLM 도메인 분류 프롬프트
LLM_DOMAIN_CLASSIFICATION_PROMPT = "..."

# 질문 분해 프롬프트
QUESTION_DECOMPOSITION_PROMPT = """
다음 복합 질문을 도메인별로 분해하세요:
질문: {query}
도메인: {domains}

각 도메인에 맞는 단일 질문으로 분해하세요.
"""

# 쿼리 재작성 프롬프트
QUERY_REWRITE_PROMPT = """
다음 질문을 검색에 최적화된 형태로 재작성하세요:
원본 질문: {query}

재작성된 질문:
"""

# 도메인 거부 응답
REJECTION_RESPONSE = """
죄송합니다. 해당 질문은 Bizi의 상담 범위에 포함되지 않습니다.

Bizi는 다음 분야의 전문 상담을 제공합니다:
- 창업/지원사업: 사업자등록, 법인설립, 정부 지원사업, 마케팅
- 세무/회계: 부가세, 법인세, 회계 처리
- 인사/노무: 근로계약, 급여, 퇴직금, 4대보험
- 법률: 상법, 민법, 소송, 특허, 저작권

위 분야에 대한 질문을 다시 해주세요.
"""

# 도메인 키워드 (fallback용)
DOMAIN_KEYWORDS = {
    "startup_funding": ["창업", "사업자등록", "법인설립", "업종", ...],
    "finance_tax": ["세금", "부가세", "법인세", "회계", ...],
    "hr_labor": ["근로", "채용", "해고", "급여", ...],
    "law_common": ["법률", "법령", "조문", "판례", ...],
}
```

**사용처:**
- 모든 에이전트, 평가기, 분류기가 참조

#### 4.3.3 domain_classifier.py - 도메인 분류기

**역할:** 질문이 어떤 도메인에 속하는지 분류 (LLM 사용 안함)

**분류 파이프라인:**

```
1차: 키워드 매칭 (kiwipiepy 형태소 분석)
  ↓ +0.1 보정
2차: 벡터 유사도 (HuggingFace embeddings)
  ↓ threshold >= 0.6?
결과: 도메인 리스트 or 거부
```

**클래스:**

```python
class VectorDomainClassifier:
    """벡터 유사도 기반 도메인 분류기"""

    def __init__(self):
        self.settings = get_settings()
        self.embeddings = HuggingFaceEmbeddings(
            model_name="jhgan/ko-sroberta-multitask"
        )

        # Kiwi 형태소 분석기
        self.kiwi = Kiwi()

        # 도메인 설정 (MySQL or fallback)
        self.domain_config = get_domain_config()

        # 대표 쿼리 벡터 캐시
        self._domain_vectors_cache: dict[str, np.ndarray] = {}

    def _get_domain_vector(self, domain: str) -> np.ndarray:
        """도메인 대표 벡터 (centroid) 계산"""

        if domain in self._domain_vectors_cache:
            return self._domain_vectors_cache[domain]

        # DB에서 대표 쿼리 가져오기
        representative_queries = self.domain_config.representative_queries.get(domain, [])

        if not representative_queries:
            # fallback
            representative_queries = DOMAIN_REPRESENTATIVE_QUERIES.get(domain, [])

        # 임베딩
        vectors = self.embeddings.embed_documents(representative_queries)

        # centroid 계산
        centroid = np.mean(vectors, axis=0)

        self._domain_vectors_cache[domain] = centroid
        return centroid

    def _keyword_match(self, query: str) -> dict[str, float]:
        """키워드 매칭 (형태소 분석 기반)"""

        # Kiwi로 lemma 추출
        tokens = self.kiwi.tokenize(query)
        lemmas = {token.form for token in tokens}

        # 도메인별 키워드 매칭
        scores = {}
        for domain, keywords in self.domain_config.keywords.items():
            match_count = sum(1 for kw in keywords if kw in lemmas)
            scores[domain] = match_count / len(keywords) if keywords else 0.0

        return scores

    def _vector_similarity(self, query: str) -> dict[str, float]:
        """벡터 유사도 계산"""

        # 쿼리 임베딩
        query_vector = np.array(self.embeddings.embed_query(query))

        # 도메인별 유사도
        similarities = {}
        for domain in ["startup_funding", "finance_tax", "hr_labor", "law_common"]:
            domain_vector = self._get_domain_vector(domain)
            similarity = np.dot(query_vector, domain_vector) / (
                np.linalg.norm(query_vector) * np.linalg.norm(domain_vector)
            )
            similarities[domain] = float(similarity)

        return similarities

    def classify(self, query: str) -> DomainClassificationResult:
        """도메인 분류 (키워드 + 벡터)"""

        # 1차: 키워드 매칭
        keyword_scores = self._keyword_match(query)

        # 2차: 벡터 유사도
        vector_scores = self._vector_similarity(query)

        # 키워드 보정 (+0.1)
        boosted_scores = {}
        for domain in vector_scores.keys():
            base = vector_scores[domain]
            boost = 0.1 if keyword_scores.get(domain, 0.0) > 0.3 else 0.0
            boosted_scores[domain] = base + boost

        # threshold 필터링
        threshold = self.settings.domain_classification_threshold
        accepted_domains = [
            domain for domain, score in boosted_scores.items()
            if score >= threshold
        ]

        # 결과
        if not accepted_domains:
            return DomainClassificationResult(
                domains=[],
                confidences={},
                is_accepted=False,
                reason="도메인 외 질문",
            )

        # 점수 높은 순 정렬
        accepted_domains.sort(key=lambda d: boosted_scores[d], reverse=True)

        return DomainClassificationResult(
            domains=accepted_domains,
            confidences=boosted_scores,
            is_accepted=True,
            reason=None,
        )

@lru_cache
def get_domain_classifier() -> VectorDomainClassifier:
    """싱글톤 분류기"""
    return VectorDomainClassifier()
```

**DomainClassificationResult:**

```python
@dataclass
class DomainClassificationResult:
    """분류 결과"""
    domains: list[str]  # 분류된 도메인 리스트
    confidences: dict[str, float]  # 도메인별 신뢰도
    is_accepted: bool  # 도메인 내 질문 여부
    reason: str | None  # 거부 이유
```

**사용처:**
- `MainRouter._classify_node()`

#### 4.3.4 search.py - Hybrid Search

**역할:** BM25 + Vector Search를 RRF로 결합

**주요 클래스:**

```python
class HybridSearcher:
    def search(self, query, collection_name, k=10, weight=0.7) -> list[Document]:
        """Vector Search + BM25 → RRF 병합 (weight: 벡터 가중치)"""

    def _reciprocal_rank_fusion(self, vector_results, bm25_results, ...) -> list[Document]:
        """RRF: score = vector_weight/(rank+60) + bm25_weight/(rank+60)"""
```

**주요 유틸리티:**

```python
# reranker.py - Cross-encoder 재정렬
class Reranker:
    model = CrossEncoder("cross-encoder/ms-marco-MiniLM-L-6-v2")
    def rerank(self, query, documents, top_k=5) -> list[Document]: ...

# question_decomposer.py - 질문 분해
class QuestionDecomposer:
    def decompose(self, query, domains) -> list[SubQuery]:
        """단일 도메인 → 스킵, 복수 도메인 → LLM 분해"""

# retrieval_evaluator.py - 규칙 기반 평가
class RuleBasedRetrievalEvaluator:
    def evaluate(self, query, documents, scores) -> RetrievalEvaluationResult:
        """문서 수, 키워드 매칭, 평균 유사도 체크 → SUCCESS/NEEDS_RETRY"""

# multi_query.py - Multi-Query 재검색
class MultiQueryRetriever:
    def retrieve(self, query, domain) -> tuple[list[Document], str]:
        """LLM으로 쿼리 N개 확장 → 각각 검색 → 중복 제거 → 정렬"""

# legal_supplement.py - 법률 보충 검색 판단
LEGAL_KEYWORDS = {"법률", "법령", "조문", "판례", ...}
def needs_legal_supplement(query, documents) -> bool:
    """쿼리/문서에 법률 키워드 있으면 True"""

# token_tracker.py - 토큰 사용량 추적
class TokenUsageCallbackHandler(BaseCallbackHandler):
    """LangChain 콜백, contextvars로 요청별 누적"""
    def on_llm_end(self, response): ...

class RequestTokenTracker:
    """컨텍스트 매니저, get_usage()로 단계별 토큰 반환"""

# cache.py - LRU 캐시
class ResponseCache:
    """max_size=500, ttl=3600, query+user_context 해시 키"""
    def get(self, query, user_context) -> Any | None: ...
    def set(self, query, value, user_context): ...
```

---

### 4.4 vectorstores/ - 벡터DB 관리

**vectorstores 모듈:**

```python
# chroma.py - ChromaDB 클라이언트 래퍼
class ChromaVectorStore:
    client = chromadb.HttpClient(...)
    embeddings = HuggingFaceEmbeddings(...)

    def similarity_search(self, query, collection_name, k=5) -> list[Document]: ...
    def similarity_search_with_score(self, ...) -> list[tuple[Document, float]]: ...
    def get_all_documents(self, collection_name) -> list[Document]: ...

# config.py - 컬렉션별 청킹 설정
COLLECTION_CONFIGS = {
    "startup_funding_db": {"chunk_size": 800, "chunk_overlap": 100, ...},
    "finance_tax_db": {"chunk_size": 600, "chunk_overlap": 100, ...},
    "hr_labor_db": {"chunk_size": 1000, "chunk_overlap": 150, ...},
    "law_common_db": {"chunk_size": 1200, "chunk_overlap": 200, ...},
}

# build_vectordb.py - 벡터DB 빌드 스크립트
# python -m vectorstores.build_vectordb --all
# python -m vectorstores.build_vectordb --db startup_funding_db
```

---

### 4.5 schemas/ - 데이터 모델

```python
# request.py
class ChatRequest(BaseModel):
    message: str
    history: list[dict]
    user_context: UserContext | None

class UserContext(BaseModel):
    user_type: str  # prospective, startup_ceo, sme_owner
    company: CompanyContext | None
    def get_user_type_label(self) -> str: ...

class CompanyContext(BaseModel):
    industry_code: str
    employee_count: int
    years_in_business: int | None
    def to_context_string(self) -> str: ...

# response.py
class ChatResponse(BaseModel):
    content: str
    domain: str
    sources: list[SourceDocument]
    actions: list[ActionSuggestion]
    evaluation: EvaluationResult | None
    timing_metrics: TimingMetrics | None
    token_usage: dict | None

class SourceDocument(BaseModel):
    title: str
    source: str
    url: str | None
    page: int | None

class ActionSuggestion(BaseModel):
    type: str  # funding_search, document_generation, external_link
    label: str
    params: dict

class EvaluationResult(BaseModel):
    score: float
    passed: bool
    feedback: str | None
    details: dict | None
```

---

## 5. 데이터 흐름 예시

### 5.1 단일 도메인 질문 (세무)

**질문:** "부가세 신고 기한이 언제인가요?"

```
1. classify (MainRouter)
   - 키워드 "부가세" → finance_tax
   - 벡터 유사도 0.85
   - 결과: [finance_tax]

2. decompose (MainRouter)
   - 단일 도메인 → 분해 스킵
   - sub_queries = [SubQuery(domain="finance_tax", query="부가세 신고 기한이 언제인가요?")]

3. retrieve (RetrievalAgent)
   - 쿼리 분석: BM25_HEAVY (짧은 사실형 질문)
   - finance_tax_db 검색 (K=3)
   - 문서 3건 검색
   - 규칙 평가: PASS (키워드 매칭 0.6, 평균 유사도 0.75)

4. generate (ResponseGeneratorAgent)
   - FinanceTaxAgent 프롬프트 사용
   - 액션 선제안: "홈택스 바로가기"
   - LLM 생성 (gpt-4o-mini)
   - 출력: "부가세 신고 기한은 다음과 같습니다..."

5. evaluate (EvaluatorAgent)
   - LLM 평가: score=0.92, PASS
   - RAGAS 로깅 (선택적)

6. ChatResponse 반환
```

### 5.2 복합 도메인 질문 (창업 + 세무)

**질문:** "창업하려는데 사업자등록 방법과 초기 세무 처리 알려주세요"

```
1. classify
   - 키워드: "창업", "사업자등록" → startup_funding
   - 키워드: "세무" → finance_tax
   - 결과: [startup_funding, finance_tax]

2. decompose
   - LLM 질문 분해
   - sub_queries = [
       SubQuery(domain="startup_funding", query="사업자등록 방법"),
       SubQuery(domain="finance_tax", query="창업 초기 세무 처리"),
     ]

3. retrieve (RetrievalAgent)
   - 문서 예산 할당: startup_funding=7, finance_tax=5
   - 병렬 검색 (asyncio.gather)
     - startup_funding_db: 7건 검색, 평가 PASS
     - finance_tax_db: 5건 검색, 평가 PASS
   - DocumentMerger: 중복 제거, 우선순위 정렬
   - 최종: 10건

4. generate (ResponseGeneratorAgent)
   - MULTI_DOMAIN_SYNTHESIS_PROMPT 사용
   - 도메인별 컨텍스트 구분
   - 액션 선제안: "정부24 바로가기", "홈택스 바로가기"
   - LLM 1회 통합 생성
   - 출력: "창업 절차와 세무 처리를 단계별로 안내드립니다..."

5. evaluate
   - LLM 평가: score=0.88, PASS

6. ChatResponse 반환
```

### 5.3 재시도 케이스 (검색 실패 → Multi-Query)

**질문:** "스타트업 초기 자금 조달 방법"

```
1-2. classify, decompose
   - [startup_funding]

3. retrieve (RetrievalAgent) - 1차 시도
   - startup_funding_db 검색 (K=5)
   - 문서 1건만 검색
   - 규칙 평가: NEEDS_RETRY (문서 수 부족: 1 < 2)

3-1. retrieve - 재시도 Level 1 (RELAX_PARAMS)
   - K를 8로 증가
   - 평가 기준 완화
   - 문서 2건 검색
   - 규칙 평가: NEEDS_RETRY (키워드 매칭 0.25 < 0.3)

3-2. retrieve - 재시도 Level 2 (MULTI_QUERY)
   - LLM 쿼리 확장:
     - "스타트업 초기 자금 조달 방법"
     - "신생 기업 자금 마련 전략"
     - "창업 초기 투자 유치 방법"
   - 각 쿼리로 검색 → 총 5건 확보
   - 규칙 평가: SUCCESS

4-6. generate, evaluate, 응답 반환
```

### 5.4 법률 보충 검색 케이스

**질문:** "직원 해고 시 법적 절차와 퇴직금 계산"

```
1-2. classify, decompose
   - [hr_labor]

3. retrieve (RetrievalAgent)
   - hr_labor_db 검색 (K=5)
   - 문서 5건 검색, 평가 PASS

   - 법률 보충 판단:
     - 쿼리에 "법적" 키워드 감지
     - needs_legal_supplement() → True

   - law_common_db 보충 검색 (K=3)
     - 문서 3건 추가

   - 최종: hr_labor 5건 + law_common 3건 = 8건

4. generate
   - HRLaborAgent 프롬프트 사용
   - 보충 법률 문서도 컨텍스트에 포함
   - 출력: "해고 절차는 근로기준법 제26조에 따라... (법률 문서 참조)"

5-6. evaluate, 응답 반환
```

---

## 부록: 주요 환경 변수

```bash
# OpenAI
OPENAI_API_KEY=sk-...
OPENAI_MODEL=gpt-4o-mini
OPENAI_TEMPERATURE=0.3

# ChromaDB
CHROMA_HOST=localhost
CHROMA_PORT=8002

# 검색 설정
DEFAULT_K=5
ENABLE_HYBRID_SEARCH=true
VECTOR_SEARCH_WEIGHT=0.7
ENABLE_RERANKING=true
ENABLE_QUERY_REWRITE=true

# 도메인 분류
ENABLE_DOMAIN_REJECTION=true
DOMAIN_CLASSIFICATION_THRESHOLD=0.6

# 평가
ENABLE_LLM_EVALUATION=true
EVALUATION_THRESHOLD=0.7
ENABLE_POST_EVAL_RETRY=false
MAX_RETRY=2

# Multi-Query
ENABLE_MULTI_QUERY=true
MULTI_QUERY_COUNT=3

# 법률 보충
ENABLE_LEGAL_SUPPLEMENT=true
LEGAL_SUPPLEMENT_K=3

# 캐시
ENABLE_RESPONSE_CACHE=true
CACHE_MAX_SIZE=500
CACHE_TTL=3600
```

---

**추가 문서:**
- 개발 가이드: `CLAUDE.md`
- 아키텍처 다이어그램: `ARCHITECTURE.md`
- 사용법: `README.md`

