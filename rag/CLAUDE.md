# RAG Service - Agentic RAG 시스템

> AI 에이전트(Claude Code) 전용 코드 작성 가이드입니다.
> 기술 스택, 실행 방법, API 엔드포인트, CLI 사용법, RAGAS 설정 등 일반 정보는 [README.md](./README.md)를 참조하세요.
> 아키텍처 다이어그램은 [ARCHITECTURE.md](./ARCHITECTURE.md)를 참조하세요.
> 파이프라인 상세(RouterState, 5단계 흐름, 벡터DB별 에이전트, 청킹 전략, 프롬프트 설계)는 아래를 참조하세요:
> @.claude/docs/rag-pipeline.md

**중요**: RAG 서비스는 Backend 프록시(`/rag/*`)를 경유하여 통신합니다. Backend가 사용자 컨텍스트를 주입하고 RAG Service로 중계합니다. X-API-Key 인증으로 직접 호출도 가능합니다.

---

## 코드 작성 가이드

새 기능 추가 시 아래 파일의 패턴을 따르세요:
- **에이전트**: `agents/*.py` → `BaseAgent` 상속, 패턴: `.claude/rules/patterns.md`
- **라우터**: `routes/*.py` → FastAPI 엔드포인트, `routes/__init__.py`의 `all_routers`에 등록
- **체인**: `chains/rag_chain.py` → RAG 체인 정의
- **스키마**: `schemas/request.py`, `schemas/response.py`
- **유틸리티**: `utils/*.py` (config, prompts, cache, search 등)
- **프롬프트**: `utils/prompts.py` (모든 프롬프트 집중 관리)
- **설정**: `utils/config/` 패키지 (settings.py, domain_data.py, domain_config.py, llm.py)
- **벡터DB 설정**: `vectorstores/config.py` (컬렉션별 청킹/소스 매핑)

### 새 에이전트 추가
1. `agents/{domain}.py` 생성 — `BaseAgent` 상속
2. `ACTION_RULES` 클래스 변수에 `ActionRule` 리스트 선언 (키워드 기반 액션 추천)
3. `agents/router.py`에 에이전트 등록
4. `utils/prompts.py`에 프롬프트 추가
5. `vectorstores/config.py`에 컬렉션 매핑 추가
6. 도메인 키워드 → `DOMAIN_KEYWORDS` dict에 추가

### 새 벡터DB 컬렉션 추가
1. `vectorstores/config.py`에 설정 추가
2. 데이터 파일을 `data/preprocessed/` 하위에 JSONL 형식으로 준비
3. `python -m scripts.vectordb --domain {name}` 실행 (프로젝트 루트에서)

---

## 도메인 분류 기준

```python
# 약식 목록 — 전체 키워드(도메인당 25~35개)는 utils/config/domain_data.py 참조
DOMAIN_KEYWORDS = {
    'startup_funding': ['창업', '사업자등록', '법인설립', '지원사업', '보조금', '정책자금', '마케팅', ...],
    'finance_tax': ['세금', '부가세', '법인세', '회계', '세무', '재무', '결산', ...],
    'hr_labor': ['근로', '채용', '해고', '급여', '퇴직금', '연차', '인사', '노무', '4대보험', ...],
    'law_common': ['법률', '법령', '판례', '상법', '민법', '소송', '특허', '상표', '저작권', ...],
}
```

---

## 도메인 외 질문 거부

### 동작 방식
1. LLM API 기반 도메인 분류 (`ENABLE_LLM_DOMAIN_CLASSIFICATION=true`)
2. Fallback: 키워드 매칭 (kiwipiepy 형태소 분석) + 벡터 유사도 분류 (`utils/domain_classifier.py`)
3. 신뢰도가 `DOMAIN_CLASSIFICATION_THRESHOLD` 미만이면 거부 응답 반환

### 거부 응답 형식
```
죄송합니다. 해당 질문은 Bizi의 상담 범위에 포함되지 않습니다.

Bizi는 다음 분야의 전문 상담을 제공합니다:
- 창업/지원사업: 사업자등록, 법인설립, 정부 지원사업, 마케팅
- 세무/회계: 부가세, 법인세, 회계 처리
- 인사/노무: 근로계약, 급여, 퇴직금, 4대보험
- 법률: 상법, 민법, 소송, 특허, 저작권
```

---

## 요청/응답 스키마

### 채팅 요청

```python
class ChatRequest(BaseModel):
    message: str
    history: list[ChatMessage] = []         # max_length=50
    user_context: UserContext | None = None
    session_id: str | None = None

class ChatMessage(BaseModel):
    role: str       # "user" | "assistant"
    content: str

class UserContext(BaseModel):
    user_id: str | None = None
    user_type: str = "prospective"  # prospective, startup_ceo, sme_owner
    company: CompanyContext | None = None

class CompanyContext(BaseModel):   # 모두 Optional
    company_name: str | None = None
    business_number: str | None = None
    industry_code: str | None = None
    industry_name: str | None = None
    employee_count: int | None = None
    years_in_business: int | None = None
    region: str | None = None
    annual_revenue: int | None = None
```

### 채팅 응답

```python
class ChatResponse(BaseModel):
    content: str
    domain: str
    domains: list[str] = []                     # 복합 질문 시 관련 도메인
    sources: list[SourceDocument] = []          # 출처 객체 리스트
    actions: list[ActionSuggestion] = []
    evaluation: EvaluationResult | None = None
    session_id: str | None = None
    retry_count: int = 0
    ragas_metrics: dict | None = None
    timing_metrics: TimingMetrics | None = None
    evaluation_data: EvaluationDataForDB | None = None  # Backend DB 저장용

class SourceDocument(BaseModel):
    title: str | None = None
    content: str
    source: str | None = None
    url: str = "https://law.go.kr/"
    metadata: dict = {}

class ActionSuggestion(BaseModel):
    type: str       # document_generation, funding_search, etc.
    label: str
    description: str | None = None
    params: dict = {}

class EvaluationResult(BaseModel):
    scores: dict[str, int] = {}   # accuracy, completeness, relevance, citation
    total_score: int              # 100점 만점
    passed: bool
    feedback: str | None = None
```

---

## 환경 변수 (품질 기능 토글)

```
ENABLE_HYBRID_SEARCH=true        # Hybrid Search (BM25+Vector+RRF)
VECTOR_SEARCH_WEIGHT=0.7         # 벡터 검색 가중치 (0.0=BM25만, 1.0=벡터만)
ENABLE_RERANKING=true            # Cross-encoder Re-ranking
MULTI_QUERY_COUNT=3              # Multi-Query 생성 개수 (항상 사용)
ENABLE_LLM_EVALUATION=true       # LLM 답변 평가
ENABLE_DOMAIN_REJECTION=true     # 도메인 외 질문 거부
ENABLE_RAGAS_EVALUATION=false    # RAGAS 정량 평가
```

### 도메인 분류
```
ENABLE_LLM_DOMAIN_CLASSIFICATION=true  # LLM API 기반 도메인 분류 (1차)
ENABLE_VECTOR_DOMAIN_CLASSIFICATION=true  # 벡터 유사도 분류 (fallback)
DOMAIN_CLASSIFICATION_THRESHOLD=0.6    # 벡터 유사도 임계값
```

### 검색 평가 (규칙 기반)
```
MIN_RETRIEVAL_DOC_COUNT=2              # 최소 문서 수
MIN_KEYWORD_MATCH_RATIO=0.3            # 최소 키워드 매칭 비율
MIN_AVG_SIMILARITY_SCORE=0.5           # 최소 평균 유사도
MIN_DOC_EMBEDDING_SIMILARITY=0.2       # 문서별 임베딩 유사도 필터 임계값
```

### 문서 제한 / Reranking
```
ENABLE_FIXED_DOC_LIMIT=true            # 도메인별 고정 문서 개수 제한 (False면 Dynamic K)
ENABLE_CROSS_DOMAIN_RERANK=true        # 복합 도메인 병합 후 Cross-Domain Reranking
```

### Multi-Query / 재시도
```
MULTI_QUERY_COUNT=3                    # 검색 단계 Multi-Query 생성 개수 (항상 사용)
ENABLE_POST_EVAL_RETRY=true            # 평가 FAIL 시 재시도
POST_EVAL_ALT_QUERY_COUNT=2            # 재시도 시 대체 쿼리 수 (1~5)
```
재시도 동작: 평가 FAIL → 대체 쿼리 2개 생성 → 원본 + 2개 = **3개 후보** 중 LLM 최고점 반환.
재시도는 **1회만** 수행 (`max_retry_count=1`, evaluate → retry → END, 루프 없음).

### 추가 기능 토글
```
ENABLE_ADAPTIVE_SEARCH=true            # 적응형 검색 모드 선택
ENABLE_RESPONSE_CACHE=true             # 응답 캐싱
ENABLE_RATE_LIMIT=true                 # Rate Limiting
ENABLE_METADATA_FILTERING=true         # 메타데이터 필터링 (지역/대상)
ENABLE_GRADUATED_RETRY=true            # 단계적 재시도 (L1~L4)
ENABLE_ACTION_AWARE_GENERATION=true    # 액션 선제안
```

### 법률 보충 검색
```
ENABLE_LEGAL_SUPPLEMENT=true           # 법률 보충 검색 활성화
LEGAL_SUPPLEMENT_K=3                   # 법률 보충 검색 문서 수
```
주 도메인 검색 후 쿼리/문서에서 법률 키워드를 감지하면 `law_common_db`에서 추가 검색합니다.
`law_common`이 주 도메인인 직접 법률 질문은 보충 없이 단독 처리됩니다.
판단 로직: `utils/legal_supplement.py` (LLM 미사용, 키워드 매칭)

### API 인증
```
RAG_API_KEY=                          # 설정 시 /api/* 경로에 X-API-Key 헤더 검증 (미설정 시 인증 없이 통과)
```

### RunPod GPU Inference (선택)
```
EMBEDDING_PROVIDER=local              # "local" (CPU/GPU 로컬 모델) | "runpod" (RunPod Serverless GPU)
RUNPOD_API_KEY=                       # RunPod API 키 (rpa_xxx 형식)
RUNPOD_ENDPOINT_ID=                   # RunPod Serverless Endpoint ID
```
- `runpod` 모드: `RunPodEmbeddings` (vectorstores/embeddings.py) + `RunPodReranker` (utils/reranker.py) 사용
- `local` 모드: 기존 HuggingFace 로컬 모델 (BAAI/bge-m3, bge-reranker-base) 사용
- 동일 RunPod 엔드포인트에서 embed/rerank 모두 처리 (task 필드로 구분)

필수 환경 변수(`OPENAI_API_KEY`, `CHROMA_HOST` 등)는 [README.md](./README.md) 참조.

---

## 성능 목표

- Router 분류 정확도: 95%
- 공고 요약 정확도: 90%
- 법령 답변 정확도: 90%
- 응답 시간: 3초 이내
- 평가 FAIL 시 재시도 1회 (대체 쿼리 2개 생성, 3개 후보 중 최고점 반환)

---

## 코드 품질

`.claude/rules/coding-style.md`, `.claude/rules/security.md`, `.claude/rules/patterns.md` 참조

RAG 고유 규칙:
- 프롬프트는 반드시 `utils/prompts.py`에 정의 (하드코딩 금지)
- 설정값은 `utils/config/settings.py`로 관리 (chunk_size, temperature 등)
- 도메인 키워드, 에이전트 코드는 상수로 정의
