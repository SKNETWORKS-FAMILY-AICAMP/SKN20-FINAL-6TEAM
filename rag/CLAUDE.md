# RAG Service - Agentic RAG 시스템

> AI 에이전트(Claude Code) 전용 코드 작성 가이드입니다.
> 기술 스택, 실행 방법, API 엔드포인트, CLI 사용법, RAGAS 설정 등 일반 정보는 [README.md](./README.md)를 참조하세요.
> 아키텍처 다이어그램은 [ARCHITECTURE.md](./ARCHITECTURE.md)를 참조하세요.
> 파이프라인 상세(RouterState, 5단계 흐름, 벡터DB별 에이전트, 청킹 전략, 프롬프트 설계)는 아래를 참조하세요:
> @.claude/docs/rag-pipeline.md

**중요**: RAG 서비스는 프론트엔드와 직접 통신합니다. Backend를 거치지 않습니다.

---

## 코드 작성 가이드

새 기능 추가 시 아래 파일의 패턴을 따르세요:
- **에이전트**: `agents/*.py` → `BaseAgent` 상속, 패턴: `.claude/rules/patterns.md`
- **체인**: `chains/rag_chain.py` → RAG 체인 정의
- **스키마**: `schemas/request.py`, `schemas/response.py`
- **유틸리티**: `utils/*.py` (config, prompts, cache, search 등)
- **프롬프트**: `utils/prompts.py` (모든 프롬프트 집중 관리)
- **설정**: `utils/config.py` (Pydantic BaseSettings)
- **벡터DB 설정**: `vectorstores/config.py` (컬렉션별 청킹/소스 매핑)

### 새 에이전트 추가
1. `agents/{domain}.py` 생성 — `BaseAgent` 상속
2. `agents/router.py`에 에이전트 등록
3. `utils/prompts.py`에 프롬프트 추가
4. `vectorstores/config.py`에 컬렉션 매핑 추가
5. 도메인 키워드 → `DOMAIN_KEYWORDS` dict에 추가

### 새 벡터DB 컬렉션 추가
1. `vectorstores/config.py`에 설정 추가
2. 데이터 파일을 `data/preprocessed/` 하위에 JSONL 형식으로 준비
3. `python -m vectorstores.build_vectordb --db {name}` 실행

---

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
        '인사', '노무', '4대보험'
    ],
    'law_common': [
        '법률', '법령', '조문', '판례', '규정',
        '상법', '민법', '소송', '분쟁', '손해배상',
        '특허', '상표', '저작권', '변호사', '계약'
    ],
}
```

---

## 도메인 외 질문 거부

### 동작 방식
1. 1차: 키워드 매칭 (DOMAIN_KEYWORDS 기반)
2. 2차: 벡터 유사도 기반 분류 (LLM 미사용, `domain_classifier.py`)
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

### 도메인 분류 (벡터 기반)
```
DOMAIN_CLASSIFICATION_THRESHOLD=0.6    # 벡터 유사도 임계값
ENABLE_VECTOR_DOMAIN_CLASSIFICATION=true
ENABLE_LLM_DOMAIN_CLASSIFICATION=false # LLM 분류 비교 (추가 비용 발생)
```

### 검색 평가 (규칙 기반)
```
MIN_RETRIEVAL_DOC_COUNT=2              # 최소 문서 수
MIN_KEYWORD_MATCH_RATIO=0.3            # 최소 키워드 매칭 비율
MIN_AVG_SIMILARITY_SCORE=0.5           # 최소 평균 유사도
MIN_DOC_EMBEDDING_SIMILARITY=0.2       # 문서별 임베딩 유사도 필터 임계값
```

### Multi-Query / 재시도
```
MULTI_QUERY_COUNT=3                    # 생성할 쿼리 수
ENABLE_POST_EVAL_RETRY=false           # 평가 후 재시도 (기본 비활성화)
```

### 법률 보충 검색
```
ENABLE_LEGAL_SUPPLEMENT=true           # 법률 보충 검색 활성화
LEGAL_SUPPLEMENT_K=3                   # 법률 보충 검색 문서 수
```
주 도메인 검색 후 쿼리/문서에서 법률 키워드를 감지하면 `law_common_db`에서 추가 검색합니다.
`law_common`이 주 도메인인 직접 법률 질문은 보충 없이 단독 처리됩니다.
판단 로직: `utils/legal_supplement.py` (LLM 미사용, 키워드 매칭)

필수 환경 변수(`OPENAI_API_KEY`, `CHROMA_HOST` 등)는 [README.md](./README.md) 참조.

---

## 성능 목표

- Router 분류 정확도: 95%
- 공고 요약 정확도: 90%
- 법령 답변 정확도: 90%
- 응답 시간: 3초 이내
- Multi-Query 재검색 시 최대 추가 3회 쿼리

---

## 코드 품질

`.claude/rules/coding-style.md`, `.claude/rules/security.md`, `.claude/rules/patterns.md` 참조

RAG 고유 규칙:
- 프롬프트는 반드시 `utils/prompts.py`에 정의 (하드코딩 금지)
- 설정값은 `utils/config.py`로 관리 (chunk_size, temperature 등)
- 도메인 키워드, 에이전트 코드는 상수로 정의
