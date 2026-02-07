# RAG Pipeline 상세

> rag/CLAUDE.md에서 분할된 파이프라인 상세 정보입니다.
> 파이프라인 수정 작업 시 참조하세요.

## RAG Pipeline (LangGraph 기반)

### RouterState 상태 타입

- `query`, `user_context`, `domains`
- `classification_result`, `sub_queries`
- `retrieval_results`, `documents`
- `final_response`, `sources`, `actions`
- `evaluation`, `ragas_metrics`, `timing_metrics`

### 5단계 처리 흐름

| 단계 | 노드 | 설명 |
|------|------|------|
| 1 | **분류 (classify)** | VectorDomainClassifier로 도메인 식별 |
| 2 | **분해 (decompose)** | 단일 도메인: 통과 / 복합 도메인: LLM 질문 분해 |
| 3 | **검색 (retrieve)** | 도메인별 병렬 RAGChain + RuleBasedRetrievalEvaluator로 품질 평가 → 미달 시 Multi-Query 재검색 |
| 4 | **생성 (generate)** | 검색 문서 기반 LLM 답변 생성 + 복수 도메인 응답 통합 |
| 5 | **평가 (evaluate)** | LLM 평가 + RAGAS 평가 (로깅만, 재시도 없음) |

---

## 벡터DB별 에이전트

### 1. 창업 및 지원 에이전트

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

### 2. 재무 및 세무 에이전트

**담당 도메인**: 세무, 회계, 재무
**데이터 소스**: 국세청 자료, 세법
**벡터DB**: `finance_tax_db/`

**주요 기능**:
- 세금 종류별 안내
- 신고/납부 일정
- 세금 계산 가이드
- 회계 기초 안내
- 재무제표 분석

### 3. 인사 및 노무 에이전트

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

### 4. 평가 모듈

**역할**: 답변 품질 평가 (로깅 목적, 재시도 비활성화 기본값)

**평가 기준**:
- 정확성: 제공된 정보가 사실에 부합하는지
- 완성도: 질문에 대해 충분히 답변했는지
- 관련성: 질문 의도에 맞는 답변인지
- 출처 명시: 법령/규정 인용 시 출처가 있는지

**참고**: `ENABLE_POST_EVAL_RETRY=false`가 기본값이므로 RAGAS 평가는 로깅만 수행합니다.

### 5. Action Executor (문서 생성)

**출력 형식**: PDF, HWP

**생성 문서**:
- 근로계약서
- 취업규칙
- 연차관리대장
- 급여명세서
- 사업계획서 템플릿

---

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

---

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
