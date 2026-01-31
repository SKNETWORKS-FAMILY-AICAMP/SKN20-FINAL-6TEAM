# RAG Service - Agentic RAG 시스템

> **이 문서는 RAG 에이전트 및 다른 AI 시스템을 위한 가이드입니다.**
> Claude Code 개발 가이드는 [CLAUDE.md](./CLAUDE.md)를 참조하세요.

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
├── AGENTS.md                 # 이 파일 (개발 가이드)
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
│   ├── __main__.py           # 배치 평가 실행
│   └── ragas_evaluator.py    # RAGAS 메트릭 평가기
│
├── vectorstores/             # 벡터 DB 관리
│   ├── __init__.py
│   ├── config.py             # VectorDB 설정 및 청킹 설정
│   ├── chroma.py             # ChromaDB 클라이언트
│   ├── embeddings.py         # 임베딩 설정
│   ├── loader.py             # 데이터 로더 및 청킹
│   └── build_vectordb.py     # VectorDB 빌드 스크립트
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
│   ├── feedback.py           # 피드백 분석
│   ├── middleware.py         # 메트릭 수집, Rate Limiting
│   ├── query.py              # 쿼리 재작성
│   └── search.py             # Hybrid Search, Re-ranking
│
└── tests/                    # 테스트
    ├── conftest.py
    ├── test_api.py
    ├── test_rag_chain.py
    ├── test_evaluator.py
    ├── test_ragas_evaluator.py
    └── ...
```

## 실행 방법

### 개발 환경

```bash
cd rag
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate
pip install -r requirements.txt
uvicorn main:app --host 0.0.0.0 --port 8001 --reload
```

### Docker

```bash
docker build -t bizmate-rag .
docker run -p 8001:8001 bizmate-rag
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
ChromaDB
├── startup_funding_db/   # 창업/지원/마케팅 전용
├── finance_tax_db/       # 재무/세무 전용
├── hr_labor_db/          # 인사/노무/법률 전용
└── law_common_db/        # 법령/법령해석 (공통 - 모든 에이전트 공유)
```

### 공통 벡터DB 사용

`law_common_db/`는 법령 원문과 법령 해석례를 저장하며, 모든 전문 에이전트가 공유합니다.
법령 관련 질문 시 전용 DB 검색 후 공통 DB도 함께 검색하여 답변 정확도를 높입니다.

## 데이터 파이프라인

### 지원사업 데이터 수집

```python
# 기업마당 API 연동
async def fetch_bizinfo_announcements():
    """기업마당 Open API에서 지원사업 공고 수집"""
    pass

# K-Startup API 연동
async def fetch_kstartup_announcements():
    """K-Startup Open API에서 스타트업 지원사업 수집"""
    pass

# 벡터DB 저장
async def store_to_vectordb(announcements: list):
    """수집된 공고를 임베딩하여 벡터DB에 저장"""
    pass
```

### 법령 데이터 로드

```python
# Hierarchical RAG 구조
HIERARCHY = {
    '근로기준법': {
        'level': 1,
        'children': ['근로기준법 시행령', '근로기준법 시행규칙']
    }
}
```

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

```
OPENAI_API_KEY=
CHROMA_HOST=localhost
CHROMA_PORT=8002
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

## 테스트

```bash
pytest tests/
pytest tests/ -v --cov=.
```

## 성능 목표

- Router 분류 정확도: 95%
- 공고 요약 정확도: 90%
- 법령 답변 정확도: 90%
- 응답 시간: 3초 이내
- 평가 후 재요청 최대 횟수: 2회

---

## 코드 품질 가이드라인 (필수 준수)

### 절대 금지 사항

- **하드코딩 금지**: API 키, ChromaDB 연결 정보 등을 코드에 직접 작성 금지 → `utils/config.py` 환경 변수 사용
- **매직 넘버/매직 스트링 금지**: chunk_size, temperature 등 설정값을 코드에 직접 사용 금지
- **중복 코드 금지**: 동일한 RAG 로직은 chains/ 또는 유틸 함수로 추출
- **프롬프트 하드코딩 금지**: 프롬프트는 반드시 `utils/prompts.py`에 정의
- **API 키 노출 금지**: OpenAI, 외부 API 키를 코드/로그에 노출 금지

### 필수 준수 사항

- **환경 변수 사용**: 모든 설정값은 `.env` 파일 + `utils/config.py`로 관리
- **상수 정의**: 도메인 키워드, 에이전트 코드 등은 상수로 정의
- **타입 힌트 사용**: 함수 파라미터와 반환값에 타입 힌트 필수
- **Pydantic 스키마**: API 요청/응답은 반드시 `schemas/` Pydantic 모델로 검증
- **에러 처리**: LangChain 체인 실행 시 예외 처리 필수
- **의미 있는 네이밍**: 에이전트, 체인, 함수명은 역할을 명확히 표현

**Be pragmatic. Be reliable. Self-anneal.**
