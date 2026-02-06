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
│  - 1차: 키워드 매칭                                          │
│  - 2차: 벡터 유사도 기반 도메인 분류 (VectorDomainClassifier) │
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
│                  3. 검색 (retrieve)                          │
│  - 도메인별 병렬 검색 (RAGChain)                              │
│  - 규칙 기반 검색 평가 (문서 수, 키워드, 유사도)              │
│    → RuleBasedRetrievalEvaluator                             │
│  - 평가 실패 시 Multi-Query 재검색 (MultiQueryRetriever)      │
└────────────────────────┬────────────────────────────────────┘
                         │
                         ↓
┌─────────────────────────────────────────────────────────────┐
│                  4. 생성 (generate)                          │
│  - 검색된 문서 기반 답변 생성                                │
│  - 복수 도메인 시 응답 통합                                  │
│  - 액션 제안 생성                                            │
└────────────────────────┬────────────────────────────────────┘
                         │
                         ↓
┌─────────────────────────────────────────────────────────────┐
│                  5. 평가 (evaluate)                          │
│  - LLM 평가 (선택적, ENABLE_LLM_EVALUATION)                  │
│  - RAGAS 평가 (로깅만, 재시도 없음)                          │
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
└───────────────┬─────────────────────────────┬───────────────────┘
                │ axios (REST API)            │ axios (직접 통신)
                │ (인증, 사용자, 기업)         │ (채팅, AI 응답)
                ↓                             ↓
┌───────────────────────────┐    ┌─────────────────────────────────┐
│   Backend (FastAPI)       │    │      RAG Service (FastAPI)      │
│   localhost:8000          │    │      localhost:8001             │
│                           │    │                                 │
│ - Google OAuth2 인증      │    │ - LangGraph 5단계 파이프라인    │
│ - 사용자/기업 관리         │    │ - 3개 도메인별 벡터DB           │
│ - 상담 이력 저장           │    │ - 평가 모듈 (LLM + RAGAS)       │
│ - 일정 관리               │    │ - Action Executor               │
└───────────────┬───────────┘    └───────────┬─────────────────────┘
                │                             │
                ↓                             ↓
        ┌───────────────┐           ┌─────────────────────┐
        │    MySQL      │           │     ChromaDB        │
        │  final_test   │           │   (Vector DB)       │
        └───────────────┘           └─────────────────────┘
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
├── hr_labor_db/                 # 인사/노무/법률 전용
│   ├── 근로기준법
│   ├── 근로기준법 시행령
│   ├── 근로기준법 시행규칙
│   ├── 상법
│   ├── 민법
│   └── 지식재산권법
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
    - graph: 동기 StateGraph
    - async_graph: 비동기 StateGraph

    노드 메서드:
    - _classify_node(): 도메인 분류
    - _decompose_node(): 질문 분해
    - _retrieve_node(): 문서 검색
    - _generate_node(): 답변 생성
    - _evaluate_node(): 품질 평가
    """
```

### 2. 창업 및 지원 에이전트

**담당 도메인**: 창업, 지원사업, 마케팅
**데이터 소스**: 창업진흥원, 중소벤처기업부, 기업마당 API, K-Startup API

**주요 기능**:
- 사업자 등록 절차 안내
- 법인 설립 가이드
- 업종별 인허가 정보
- 지원사업 검색/필터
- 기업 조건 매칭
- 마케팅 전략 조언

### 3. 재무 및 세무 에이전트

**담당 도메인**: 세무, 회계, 재무
**데이터 소스**: 국세청 자료, 세법

**주요 기능**:
- 세금 종류별 안내
- 신고/납부 일정
- 세금 계산 가이드
- 회계 기초 안내
- 재무제표 분석

### 4. 인사 및 노무 에이전트

**담당 도메인**: 노무, 인사, 법률
**데이터 소스**: 근로기준법, 상법, 민법, 지식재산권법

**주요 기능**:
- Hierarchical RAG (법령 계층 검색)
- 채용/해고 상담
- 근로시간/휴가 안내
- 임금/퇴직금 계산
- 계약법 가이드
- 지식재산권 안내

### 5. 평가 모듈

**역할**: 답변 품질 평가 (로깅 목적)

**평가 기준**:
- 정확성: 제공된 정보가 사실에 부합하는지
- 완성도: 질문에 대해 충분히 답변했는지
- 관련성: 질문 의도에 맞는 답변인지
- 출처 명시: 법령/규정 인용 시 출처가 있는지

```python
class Evaluator:
    """
    답변 품질을 평가 (재시도는 기본 비활성화)
    ENABLE_POST_EVAL_RETRY=false가 기본값
    """

    def evaluate(self, query: str, response: str) -> EvaluationResult:
        """
        답변 품질 평가
        Returns: EvaluationResult(score, passed, feedback)
        """
        pass
```

### 핵심 유틸리티 모듈

| 모듈 | 클래스 | 역할 |
|------|--------|------|
| `domain_classifier.py` | `VectorDomainClassifier` | 벡터 유사도 기반 도메인 분류 |
| `question_decomposer.py` | `QuestionDecomposer` | LLM 기반 복합 질문 분해 |
| `retrieval_evaluator.py` | `RuleBasedRetrievalEvaluator` | 규칙 기반 검색 품질 평가 |
| `multi_query.py` | `MultiQueryRetriever` | Multi-Query 재검색 |
| `token_tracker.py` | `TokenUsageCallbackHandler` | 토큰 사용량 추적 |

### 6. Action Executor

**역할**: 문서 생성 (PDF, HWP)

**생성 가능 문서**:
- 근로계약서
- 취업규칙
- 연차관리대장
- 급여명세서
- 사업계획서 템플릿

## 3중 평가 체계

RAG 시스템은 세 가지 평가 방식을 지원합니다:

| 구분 | 검색 평가 (retrieval_evaluator.py) | LLM 평가 (evaluator.py) | RAGAS 평가 (evaluation/) |
|------|-----------------------------------|-------------------------|--------------------------|
| 방식 | 규칙 기반 (문서 수, 키워드, 유사도) | LLM이 5개 기준으로 채점 | RAGAS 라이브러리 메트릭 |
| 용도 | 검색 품질 판단 → Multi-Query 재검색 트리거 | 답변 품질 채점 | 정량적 품질 추적 및 분석 |
| 실행 | 검색 단계에서 자동 실행 | `ENABLE_LLM_EVALUATION=true` | `ENABLE_RAGAS_EVALUATION=true` |
| 재시도 | Multi-Query 재검색 | 기본 비활성화 (`ENABLE_POST_EVAL_RETRY=false`) | 없음 (로깅만) |
| 로그 | 콘솔 | logs/chat.log | logs/ragas.log (JSON Lines) |

## 데이터 흐름 예시

### 단일 도메인 질문
```
Q: "부가세 신고 기한이 언제인가요?"

1. classify → 도메인 분류: [finance_tax]
2. decompose → 단일 도메인이므로 분해 없이 통과
3. retrieve → finance_tax_db 검색 → 문서 충분
4. generate → 답변 생성
5. evaluate → RAGAS 로깅
6. ChatResponse 반환
```

### 복합 도메인 질문
```
Q: "창업하려는데 사업자등록 방법과 초기 세무 처리 알려주세요"

1. classify → 도메인 분류: [startup_funding, finance_tax]
2. decompose → 2개 SubQuery 생성
   - startup_funding: "사업자등록 방법"
   - finance_tax: "초기 세무 처리"
3. retrieve → 병렬 검색
   - startup_funding_db → 문서 4건
   - finance_tax_db → 문서 3건
4. generate → 통합 응답 생성
5. evaluate → RAGAS 로깅
6. ChatResponse 반환
```

### Multi-Query 재검색 케이스
```
Q: "창업 절차와 초기 세무 처리"

1. classify → [startup_funding, finance_tax]
2. decompose → 2개 SubQuery 생성
3. retrieve (1차):
   - startup_funding: 문서 1건 (MIN_RETRIEVAL_DOC_COUNT 미달)
   - finance_tax: 문서 3건 (통과)
4. retrieve (Multi-Query 재검색):
   - startup_funding: 3개 변형 쿼리로 문서 4건 확보
5. generate → 통합 응답 생성
6. evaluate → RAGAS 로깅
7. ChatResponse 반환
```
