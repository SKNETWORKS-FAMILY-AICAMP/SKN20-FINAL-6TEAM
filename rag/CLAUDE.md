# RAG Service - Agentic RAG 시스템

> **이 문서는 Claude Code를 위한 자기 완결적 개발 가이드입니다.**
> 다른 AI 에이전트는 [AGENTS.md](./AGENTS.md)를 참조하세요.

## 개요

Bizi의 핵심 AI 서비스입니다. LangChain과 LangGraph를 사용하여
Agentic RAG 시스템을 구현합니다. (5개 에이전트: 메인 라우터, 3개 전문 에이전트, 평가 에이전트)

아키텍처 상세는 [ARCHITECTURE.md](./ARCHITECTURE.md)를 참조하세요.

**중요**: RAG 서비스는 프론트엔드(React + Vite)와 직접 통신합니다. Backend를 거치지 않고 채팅 및 AI 응답을 처리합니다.

## 기술 스택

- Python 3.10+
- FastAPI
- LangChain 0.1+
- LangGraph
- OpenAI GPT-4o-mini
- ChromaDB (벡터 DB)
- httpx (HTTP 클라이언트)

## 프로젝트 구조

```
rag/
├── CLAUDE.md                 # 이 파일 (개발 가이드)
├── ARCHITECTURE.md           # 상세 아키텍처 (다이어그램)
├── main.py                   # FastAPI 진입점
├── cli.py                    # CLI 테스트 모드
├── requirements.txt
├── Dockerfile
│
├── agents/                   # Agentic RAG 에이전트
│   ├── __init__.py
│   ├── router.py             # 메인 라우터 (질문 분류 및 조율)
│   ├── base.py               # 기본 에이전트 클래스
│   ├── startup_funding.py    # 창업 및 지원 에이전트
│   ├── finance_tax.py        # 재무 및 세무 에이전트
│   ├── hr_labor.py           # 인사 및 노무 에이전트
│   ├── evaluator.py          # 평가 에이전트 (LLM 기반)
│   └── executor.py           # Action Executor (문서 생성)
│
├── chains/                   # LangChain 체인
│   ├── __init__.py
│   └── rag_chain.py          # RAG 체인
│
├── evaluation/               # RAGAS 정량 평가
│   ├── __init__.py
│   ├── __main__.py           # 배치 평가 실행 (python -m evaluation)
│   └── ragas_evaluator.py    # RAGAS 메트릭 평가기
│
├── vectorstores/             # 벡터 DB 관리
│   ├── __init__.py
│   ├── config.py             # VectorDB 설정 및 청킹 설정
│   ├── chroma.py             # ChromaDB 클라이언트
│   ├── embeddings.py         # 임베딩 설정 (BAAI/bge-m3)
│   ├── loader.py             # 데이터 로더 및 청킹
│   └── build_vectordb.py     # VectorDB 빌드 스크립트
│
├── vectordb/                 # VectorDB 저장 디렉토리 (git에서 제외)
│   ├── startup_funding_db/   # 창업/지원/마케팅 전용
│   ├── finance_tax_db/       # 재무/세무 전용
│   ├── hr_labor_db/          # 인사/노무 전용
│   └── law_common_db/        # 법령/법령해석 (공통)
│
├── schemas/                  # Pydantic 스키마
│   ├── __init__.py
│   ├── request.py
│   └── response.py
│
├── utils/                    # 유틸리티
│   ├── __init__.py
│   ├── config.py             # 설정 (Pydantic BaseSettings)
│   ├── prompts.py            # 프롬프트 템플릿
│   ├── cache.py              # 응답 캐싱
│   ├── feedback.py           # 피드백 분석 및 검색 전략 조정
│   ├── middleware.py         # 메트릭 수집, Rate Limiting 미들웨어
│   ├── query.py              # 쿼리 재작성 및 처리
│   └── search.py             # Hybrid Search, Re-ranking
│
├── tests/                    # 테스트
│   ├── conftest.py           # pytest 설정
│   ├── test_api.py           # API 엔드포인트 테스트
│   ├── test_rag_chain.py     # RAG 체인 테스트
│   ├── test_evaluator.py     # 평가 에이전트 테스트
│   ├── test_ragas_evaluator.py  # RAGAS 평가 테스트
│   ├── test_query.py         # 쿼리 처리 테스트
│   ├── test_search.py        # 검색 테스트
│   ├── test_cache.py         # 캐시 테스트
│   ├── test_feedback.py      # 피드백 테스트
│   └── test_middleware.py    # 미들웨어 테스트
│
└── logs/                     # 로그 (런타임 생성)
    ├── chat.log              # 채팅 로그 (10MB, 5 로테이션)
    └── ragas.log             # RAGAS 메트릭 로그 (JSON Lines)
```

## 실행 방법

### 개발 환경

```bash
# 프로젝트 루트에서
cd rag
source ../.venv/bin/activate  # Windows: ..\.venv\Scripts\activate
pip install -r requirements.txt
uvicorn main:app --host 0.0.0.0 --port 8001 --reload
```

### Docker

```bash
docker build -t bizmate-rag .
docker run -p 8001:8001 bizmate-rag
```

### VectorDB 빌드

```bash
# 프로젝트 루트의 .venv 활성화
cd rag
source ../.venv/bin/activate  # Windows: ..\.venv\Scripts\activate

# 전체 VectorDB 빌드 (OPENAI_API_KEY 필요)
python -m vectorstores.build_vectordb --all

# 특정 DB만 빌드
python -m vectorstores.build_vectordb --db startup_funding
python -m vectorstores.build_vectordb --db finance_tax
python -m vectorstores.build_vectordb --db hr_labor
python -m vectorstores.build_vectordb --db law_common

# 강제 재빌드 (기존 데이터 삭제 후 재생성)
python -m vectorstores.build_vectordb --all --force

# 통계 확인
python -m vectorstores.build_vectordb --stats
```

## API 엔드포인트

### 채팅

| Method | Endpoint | 설명 |
|--------|----------|------|
| POST | `/api/chat` | 사용자 메시지 처리 및 응답 |
| POST | `/api/chat/stream` | 스트리밍 응답 |

### 문서 생성

| Method | Endpoint | 설명 |
|--------|----------|------|
| POST | `/api/documents/contract` | 근로계약서 생성 |
| POST | `/api/documents/rules` | 취업규칙 생성 |
| POST | `/api/documents/business-plan` | 사업계획서 생성 |

### 지원사업

| Method | Endpoint | 설명 |
|--------|----------|------|
| GET | `/api/funding/search` | 지원사업 검색 |
| POST | `/api/funding/recommend` | 맞춤 지원사업 추천 |
| POST | `/api/funding/sync` | 공고 데이터 동기화 |

## 도메인 분류 기준

```python
DOMAIN_KEYWORDS = {
    'startup_funding': [
        '창업', '사업자등록', '법인설립', '업종',
        '지원사업', '보조금', '정책자금', '공고',
        '마케팅', '광고', '홍보', '브랜딩'
    ],
    'finance_tax': [
        '세금', '부가세', '법인세', '회계',
        '세무', '재무', '결산', '세무조정'
    ],
    'hr_labor': [
        '근로', '채용', '해고', '급여', '퇴직금', '연차',
        '인사', '노무', '4대보험',
        '계약', '소송', '분쟁', '특허', '상표'
    ],
}
```

## 도메인 외 질문 거부

Bizi 상담 범위에 포함되지 않는 질문은 자동으로 거부됩니다.

### 동작 방식
1. 키워드 매칭으로 1차 분류
2. 키워드 매칭 실패 시 LLM 분류 + 신뢰도 판단
3. 신뢰도가 `DOMAIN_CONFIDENCE_THRESHOLD` 미만이면 거부 응답 반환

### 거부 응답
```
죄송합니다. 해당 질문은 Bizi의 상담 범위에 포함되지 않습니다.

Bizi는 다음 분야의 전문 상담을 제공합니다:
- 창업/지원사업: 사업자등록, 법인설립, 정부 지원사업, 마케팅
- 세무/회계: 부가세, 법인세, 회계 처리
- 인사/노무: 근로계약, 급여, 퇴직금, 4대보험
```

## 에이전트 상세

### 1. 메인 라우터

**역할**: 질문 분류, 에이전트 조율, 평가 결과에 따른 재요청

**주요 기능**:
- 사용자 질문 분석 및 도메인 분류
- 복합 질문 시 여러 에이전트 병렬 호출
- 에이전트 응답 통합
- 평가 에이전트의 피드백에 따라 재요청 처리

### 2. 창업 및 지원 에이전트

**담당 도메인**: 창업, 지원사업, 마케팅
**데이터 소스**: 창업진흥원, 중소벤처기업부, 기업마당 API, K-Startup API
**벡터DB**: `startup_funding_db/`

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
**벡터DB**: `finance_tax_db/`

**주요 기능**:
- 세금 종류별 안내
- 신고/납부 일정
- 세금 계산 가이드
- 회계 기초 안내
- 재무제표 분석

### 4. 인사 및 노무 에이전트

**담당 도메인**: 노무, 인사
**데이터 소스**: 근로기준법, 상법, 민법, 지식재산권법
**벡터DB**: `hr_labor_db/`

**주요 기능**:
- Hierarchical RAG (법령 계층 검색)
- 채용/해고 상담
- 근로시간/휴가 안내
- 임금/퇴직금 계산
- 계약법 가이드
- 지식재산권 안내

### 5. 평가 에이전트

**역할**: 답변 품질 평가 및 재요청 판단

**평가 기준**:
- 정확성: 제공된 정보가 사실에 부합하는지
- 완성도: 질문에 대해 충분히 답변했는지
- 관련성: 질문 의도에 맞는 답변인지
- 출처 명시: 법령/규정 인용 시 출처가 있는지

**재요청 기준**: 평가 점수가 threshold 미만일 경우 피드백과 함께 재요청

### 6. Action Executor (문서 생성)

**출력 형식**: PDF, HWP

**생성 문서**:
- 근로계약서
- 취업규칙
- 연차관리대장
- 급여명세서
- 사업계획서 템플릿

## 벡터DB 구성

```
vectordb/
├── startup_funding_db/   # 창업/지원/마케팅 전용 (~2,100 documents)
├── finance_tax_db/       # 재무/세무 전용 (~15,200 documents)
├── hr_labor_db/          # 인사/노무 전용 (~8,200 documents)
└── law_common_db/        # 법령/법령해석 공통 (~187,800 documents)
```

### 데이터 소스 및 청킹 전략

| DB | 파일 | 청킹 | 설정 |
|----|------|------|------|
| startup_funding | announcements.jsonl | 안함 | - |
| startup_funding | industry_startup_guide_filtered.jsonl | 안함 | - |
| startup_funding | startup_procedures_filtered.jsonl | 조건부 | size=1000, overlap=200 |
| finance_tax | court_cases_tax.jsonl | 필수 | size=800, overlap=100 |
| finance_tax | extracted_documents_final.jsonl | 필수 | size=800, overlap=100 |
| hr_labor | court_cases_labor.jsonl | 필수 | size=800, overlap=100 |
| hr_labor | labor_interpretation.jsonl | 조건부 | size=800, overlap=100 |
| hr_labor | hr_major_insurance.jsonl | 조건부 | size=800, overlap=100 |
| law_common | laws_full.jsonl | 조건부 | size=800, overlap=100 |
| law_common | interpretations.jsonl | 조건부 | size=800, overlap=100 |

### 공통 벡터DB 사용

`law_common_db/`는 법령 원문과 법령 해석례를 저장하며, 모든 전문 에이전트가 공유합니다.
법령 관련 질문 시 전용 DB 검색 후 공통 DB도 함께 검색하여 답변 정확도를 높입니다.

### 임베딩 모델

- **모델**: `BAAI/bge-m3` (HuggingFace, 로컬 실행, GPU 자동 감지)
- **벡터 차원**: 1024
- **벡터 공간**: cosine similarity

## 요청/응답 스키마

### 채팅 요청

```python
class ChatRequest(BaseModel):
    message: str
    history: list[dict] = []
    user_context: dict = {}

class UserContext(BaseModel):
    user_type: str  # prospective, startup_ceo, sme_owner
    company: CompanyContext | None = None

class CompanyContext(BaseModel):
    industry_code: str
    employee_count: int
    years_in_business: int | None
```

### 채팅 응답

```python
class ChatResponse(BaseModel):
    content: str
    domain: str
    sources: list[str] = []
    actions: list[ActionSuggestion] = []
    evaluation: EvaluationResult | None = None

class ActionSuggestion(BaseModel):
    type: str  # document_generation, funding_search, etc.
    label: str
    params: dict

class EvaluationResult(BaseModel):
    score: float
    passed: bool
    feedback: str | None = None
```

## 환경 변수

### 필수
```
OPENAI_API_KEY=
CHROMA_HOST=localhost
CHROMA_PORT=8002
```

### 품질 기능 토글
```
ENABLE_HYBRID_SEARCH=true        # Hybrid Search (BM25+Vector+RRF)
ENABLE_RERANKING=true            # Cross-encoder Re-ranking
ENABLE_QUERY_REWRITE=true        # LLM 쿼리 재작성
ENABLE_LLM_EVALUATION=true       # LLM 답변 평가
ENABLE_DOMAIN_REJECTION=true     # 도메인 외 질문 거부
DOMAIN_CONFIDENCE_THRESHOLD=0.5  # 거부 임계값
ENABLE_RAGAS_EVALUATION=false    # RAGAS 정량 평가
```

## 프롬프트 설계

### 메인 라우터 프롬프트

```
당신은 Bizi의 메인 라우터입니다.
사용자 질문을 분석하여 적절한 도메인으로 라우팅하세요.

도메인 목록:
- startup_funding: 창업, 사업자등록, 법인설립, 지원사업, 보조금, 마케팅
- finance_tax: 세금, 회계, 세무, 재무
- hr_labor: 근로, 채용, 급여, 노무, 계약, 소송, 지식재산권

복합 질문인 경우 여러 도메인을 선택하세요.
```

### 도메인 에이전트 프롬프트 (예: 인사 및 노무 에이전트)

```
당신은 Bizi의 인사 및 노무 전문 상담사입니다.
근로기준법과 관련 법령을 기반으로 정확한 정보를 제공하세요.

사용자 유형: {user_type}
기업 정보: {company_context}

주의사항:
1. 법률 조문을 인용할 때는 출처를 명시하세요
2. 복잡한 사안은 전문가 상담을 권유하세요
3. 사용자 유형에 맞는 눈높이로 설명하세요
```

### 평가 에이전트 프롬프트

```
당신은 Bizi의 답변 품질 평가자입니다.
다음 기준으로 답변을 평가하세요:

1. 정확성 (0-25): 정보가 사실에 부합하는가?
2. 완성도 (0-25): 질문에 충분히 답변했는가?
3. 관련성 (0-25): 질문 의도에 맞는 답변인가?
4. 출처 명시 (0-25): 법령/규정 인용 시 출처가 있는가?

총점 70점 이상이면 PASS, 미만이면 FAIL.
FAIL인 경우 구체적인 개선 피드백을 제공하세요.
```

## CLI 테스트 모드

FastAPI 서버 없이 터미널에서 RAG 시스템을 직접 테스트할 수 있습니다.

### 사용법

```bash
# 대화형 모드 (INFO 로그 기본 출력)
python -m cli

# 단일 쿼리 모드
python -m cli --query "사업자등록 절차 알려주세요"

# RAGAS 평가 포함
python -m cli --query "퇴직금 계산 방법" --ragas

# 로그 숨김 (WARNING만 출력)
python -m cli --quiet

# 디버그 출력 (DEBUG 로그 포함)
python -m cli --debug

# 사용자 유형 지정
python -m cli --user-type startup_ceo

# 검색 기능 토글
python -m cli --no-hybrid                    # Hybrid Search (BM25+RRF) 비활성화
python -m cli --no-rerank                    # Re-ranking 비활성화
python -m cli --no-rewrite                   # 쿼리 재작성 비활성화
python -m cli --no-hybrid --no-rerank        # 여러 기능 동시 비활성화
```

### CLI 옵션

| 옵션 | 설명 |
|------|------|
| `--query`, `-q` | 단일 쿼리 모드 |
| `--ragas` | RAGAS 정량 평가 활성화 |
| `--quiet` | 로그 숨김 (WARNING만 출력, 컨텍스트 내용 미표시) |
| `--debug` | DEBUG 로그 출력 (모든 로그) |
| `--user-type` | 사용자 유형 (prospective, startup_ceo, sme_owner) |
| `--no-hybrid` | Hybrid Search (BM25+RRF) 비활성화 |
| `--no-rerank` | Re-ranking 비활성화 |
| `--no-rewrite` | 쿼리 재작성 비활성화 |

### 초기화 출력

CLI 시작 시 다음 정보가 표시됩니다:
- 임베딩 디바이스 (GPU (CUDA) / GPU (Apple MPS) / CPU)
- Hybrid Search, Re-ranking, Query Rewrite 활성화 상태

### 로그 레벨

| 레벨 | 옵션 | 출력 내용 |
|------|------|----------|
| INFO | (기본) | 각 단계별 검색/생성 시간, 문서 수, 도메인 분류, 평가 기준별 점수, 검색 문서 제목 등 |
| WARNING | `--quiet` | 경고 및 에러만 |
| DEBUG | `--debug` | 모든 내부 처리 과정 상세 출력 |

### 출력 정보

- 질문/답변
- 참고 문서 (출처, 제목)
- LLM 평가 결과 (5개 기준 점수)
- RAGAS 메트릭 (`--ragas` 옵션 사용 시)
- 응답 시간

## RAGAS 정량 평가

기존 LLM 기반 평가(evaluator.py)에 추가로 RAGAS 라이브러리를 사용한 정량 평가를 지원합니다.

### 메트릭

| 메트릭 | 설명 | Ground Truth 필요 |
|--------|------|-------------------|
| Faithfulness | 답변이 검색된 컨텍스트와 사실적으로 일관되는지 | 아니오 |
| Answer Relevancy | 답변이 질문에 관련 있는지 | 아니오 |
| Context Precision | 검색된 컨텍스트가 정밀한지 (관련 문서 상위 랭킹) | 아니오 |
| Context Recall | 검색된 컨텍스트가 정답을 충분히 커버하는지 | 예 |

### 설정

`.env` 파일에 추가:
```
ENABLE_RAGAS_EVALUATION=true
```

- 기본값: `false` (추가 LLM 호출로 비용/지연 발생)
- 라이브 쿼리: Faithfulness, Answer Relevancy, Context Precision (3개)
- 배치 평가 (ground_truth 포함): + Context Recall (4개)

### 배치 평가

```bash
# 테스트 데이터셋으로 배치 평가
python -m evaluation --dataset tests/test_dataset.jsonl --output results.json
```

### 로그

RAGAS 메트릭은 `logs/ragas.log`에 JSON Lines 형식으로 기록됩니다:
```json
{"timestamp": "2026-01-30 14:30:00", "question": "퇴직금 계산 방법", "answer_preview": "퇴직금은...", "domains": ["hr_labor"], "response_time": 3.25, "ragas_metrics": {"faithfulness": 0.85, "answer_relevancy": 0.92, "context_precision": 0.78}}
```

## 테스트

```bash
pytest tests/
pytest tests/ -v --cov=.
```

## 로깅 정보

RAG 파이프라인 실행 시 다음 로그가 INFO 레벨로 출력됩니다:

| 단계 | 로그 형식 | 예시 |
|------|----------|------|
| 캐시 | `[캐시] ✓ 히트` / `[캐시] ✗ 미스` | `[캐시] ✗ 미스 - '창업 절차...'` |
| 쿼리 재작성 | `[ainvoke] 쿼리 재작성: 원본 → 재작성` | `'창업' → '창업 절차 사업자등록...'` |
| 검색 완료 | `[검색 완료] 총 N건 검색됨` | 각 문서의 제목, score, 출처 포함 |
| 리랭킹 | `[리랭킹] 시작: N건 → top_K` | `13건 → top_3` |
| 평가 | `[평가] 총점=N/100` | 기준별 점수 상세 |

## 성능 목표

- Router 분류 정확도: 95%
- 공고 요약 정확도: 90%
- 법령 답변 정확도: 90%
- 응답 시간: 3초 이내
- 평가 후 재요청 최대 횟수: 2회

## 코드 품질
`.claude/rules/coding-style.md`, `.claude/rules/security.md`, `.claude/rules/patterns.md` 참조

RAG 고유 규칙:
- 프롬프트는 반드시 `utils/prompts.py`에 정의 (하드코딩 금지)
- 설정값은 `utils/config.py`로 관리 (chunk_size, temperature 등)
- 도메인 키워드, 에이전트 코드는 상수로 정의
