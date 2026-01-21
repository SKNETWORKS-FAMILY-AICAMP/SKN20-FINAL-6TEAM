# RAG Service - 멀티에이전트 시스템

> **이 문서는 Claude Code를 위한 자기 완결적 개발 가이드입니다.**
> 다른 AI 에이전트는 [AGENTS.md](./AGENTS.md)를 참조하세요.

## 개요
BizMate의 핵심 AI 서비스입니다. LangChain과 LangGraph를 사용하여 6개 도메인 전문 에이전트와 Master Router를 구현합니다.

**중요**: RAG 서비스는 프론트엔드(React + Vite)와 직접 통신합니다. Backend를 거치지 않고 채팅 및 AI 응답을 처리합니다.

## 기술 스택
- Python 3.10+
- FastAPI
- LangChain 0.1+
- LangGraph
- OpenAI GPT-4
- ChromaDB (벡터 DB)
- httpx (HTTP 클라이언트)

## 프로젝트 구조
```
rag/
├── CLAUDE.md
├── main.py                    # FastAPI 진입점
├── requirements.txt
├── Dockerfile
│
├── agents/                    # 멀티에이전트
│   ├── __init__.py
│   ├── router.py             # Master Router
│   ├── base.py               # 기본 에이전트 클래스
│   ├── startup.py            # 창업 에이전트
│   ├── tax.py                # 세무/회계 에이전트
│   ├── funding.py            # 지원사업 에이전트
│   ├── hr.py                 # 노무 에이전트
│   ├── legal.py              # 법률 에이전트
│   ├── marketing.py          # 마케팅 에이전트
│   └── executor.py           # Action Executor (문서 생성)
│
├── chains/                    # LangChain 체인
│   ├── __init__.py
│   └── rag_chain.py          # RAG 체인
│
├── vectorstores/              # 벡터 DB 관리
│   ├── __init__.py
│   ├── chroma.py             # ChromaDB 클라이언트
│   └── embeddings.py         # 임베딩 설정
│
├── loaders/                   # 데이터 로더 (벡터DB 적재용)
│   ├── __init__.py
│   ├── funding_loader.py     # 지원사업 데이터 로더
│   └── law_loader.py         # 법령 데이터 로더
│
├── schemas/                   # Pydantic 스키마
│   ├── __init__.py
│   ├── request.py
│   └── response.py
│
└── utils/                     # 유틸리티
    ├── __init__.py
    ├── prompts.py            # 프롬프트 템플릿
    └── config.py             # 설정
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

## 통신 아키텍처

### 프론트엔드 직접 통신
```
┌─────────────────────┐
│  Frontend (Vite)    │
│   localhost:5173    │
└─────────┬───────────┘
          │ axios 직접 통신 (POST /api/chat, /api/chat/stream)
          ↓
┌─────────────────────┐
│  RAG Service        │
│  localhost:8001     │
│                     │
│  - Master Router    │
│  - 6개 전문 에이전트 │
│  - Action Executor  │
└─────────┬───────────┘
          │
          ↓
┌─────────────────────┐
│  ChromaDB           │
│  (Vector DB)        │
└─────────────────────┘
```

**참고**: 사용자 인증, 기업 정보, 상담 이력 저장은 Backend(FastAPI)가 담당합니다.

## 멀티에이전트 아키텍처

### Master Router
```
사용자 입력
    ↓
[Master Router]
    ↓ (도메인 분류)
┌───────────────────────────────────────────┐
│  startup  │  tax  │  funding  │  hr  │ ...│
└───────────────────────────────────────────┘
    ↓ (복합 질문 시 병렬 처리)
[Response Aggregator]
    ↓
[Action Executor] (필요시)
    ↓
최종 응답
```

### 도메인 분류 기준
```python
DOMAIN_KEYWORDS = {
    'startup': ['창업', '사업자등록', '법인설립', '업종'],
    'tax': ['세금', '부가세', '법인세', '회계', '세무'],
    'funding': ['지원사업', '보조금', '정책자금', '공고'],
    'hr': ['근로', '채용', '해고', '급여', '퇴직금', '연차'],
    'legal': ['계약', '소송', '분쟁', '특허', '상표'],
    'marketing': ['마케팅', '광고', '홍보', '브랜딩'],
}
```

## 에이전트 상세

### 1. Startup Agent (창업)
**데이터 소스**: 창업진흥원, 중소벤처기업부 자료
**주요 기능**:
- 사업자 등록 절차 안내
- 법인 설립 가이드
- 업종별 인허가 정보
- 업종 코드 검색

### 2. Tax Agent (세무/회계)
**데이터 소스**: 국세청 자료, 세법
**주요 기능**:
- 세금 종류별 안내
- 신고/납부 일정
- 세금 계산 가이드
- 회계 기초 안내

### 3. Funding Agent (지원사업)
**데이터 소스**: 기업마당 API, K-Startup API
**주요 기능**:
- 지원사업 검색/필터
- 기업 조건 매칭
- 마감일 기반 정렬
- Top N 추천

### 4. HR Agent (노무)
**데이터 소스**: 근로기준법, 시행령, 시행규칙
**주요 기능**:
- Hierarchical RAG (법령 계층 검색)
- 채용/해고 상담
- 근로시간/휴가 안내
- 임금/퇴직금 계산

### 5. Legal Agent (법률)
**데이터 소스**: 상법, 민법, 지식재산권법
**주요 기능**:
- 상법 기초 안내
- 계약법 가이드
- 지식재산권 안내
- 분쟁 대응 가이드

### 6. Marketing Agent (마케팅)
**데이터 소스**: 마케팅 가이드, 사례 분석
**주요 기능**:
- 마케팅 전략 조언
- 디지털 마케팅 가이드
- 브랜딩 조언

### Action Executor (문서 생성)
**출력 형식**: PDF, HWP
**생성 문서**:
- 근로계약서
- 취업규칙
- 연차관리대장
- 급여명세서
- 사업계획서 템플릿

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

class ActionSuggestion(BaseModel):
    type: str  # document_generation, funding_search, etc.
    label: str
    params: dict
```

## 환경 변수
```
OPENAI_API_KEY=
BIZINFO_API_KEY=
KSTARTUP_API_KEY=
CHROMA_HOST=localhost
CHROMA_PORT=8002
```

## 프롬프트 설계

### Master Router 프롬프트
```
당신은 BizMate의 Master Router입니다.
사용자 질문을 분석하여 적절한 도메인으로 라우팅하세요.

도메인 목록:
- startup: 창업, 사업자등록, 법인설립
- tax: 세금, 회계, 세무
- funding: 지원사업, 보조금, 정책자금
- hr: 근로, 채용, 급여, 노무
- legal: 계약, 소송, 지식재산권
- marketing: 마케팅, 광고, 홍보

복합 질문인 경우 여러 도메인을 선택하세요.
```

### 도메인 에이전트 프롬프트 (예: HR Agent)
```
당신은 BizMate의 노무 전문 상담사입니다.
근로기준법과 관련 법령을 기반으로 정확한 정보를 제공하세요.

사용자 유형: {user_type}
기업 정보: {company_context}

주의사항:
1. 법률 조문을 인용할 때는 출처를 명시하세요
2. 복잡한 사안은 전문가 상담을 권유하세요
3. 사용자 유형에 맞는 눈높이로 설명하세요
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
