# RetrievalAgent 구현 정리

> 파이프라인 3번 검색(retrieve) 파트를 전담하는 에이전트.
> 2026-02-09 구현 완료.

---

## 1. 배경 및 목적

### 기존 문제점

`router.py`의 `_retrieve_node()`가 모든 검색 로직을 직접 처리:

- 도메인별 순차 루프 → 검색 전략 없음
- K값 고정 (settings.retrieval_k) → 쿼리 특성 무시
- 복합 도메인 시 문서 폭증 → 예산 관리 없음
- 평가 실패 시 Multi-Query 1회만 재시도 → 단계적 대응 없음
- 법률 보충 검색이 router에 직접 구현 → 관심사 혼재

### 해결 방향

| 문제 | 해결 | 비용 |
|------|------|------|
| K값 고정 | 쿼리 특성 분석 → 동적 K (3~7) | $0 (규칙 기반) |
| 문서 폭증 | 도메인별 예산(budget) 할당 | $0 (규칙 기반) |
| 재시도 1회 | 4단계 graduated retry | Level 2만 LLM 사용 |
| 전략 없음 | 5가지 SearchMode 자동 선택 | $0 (규칙 기반) |

---

## 2. 파일 변경 목록

| 파일 | 작업 | 변경량 |
|------|------|--------|
| `rag/agents/retrieval_agent.py` | **신규 생성** | ~600줄 |
| `rag/utils/config.py` | 수정 | 설정 7개 + override 5개 추가 |
| `rag/agents/router.py` | 수정 | ~120줄 삭제, ~10줄 추가 |
| `rag/agents/__init__.py` | 수정 | export 1개 추가 |

### 변경하지 않은 파일 (호환성 유지)

- `RouterState` TypedDict — 필드 추가 없음
- `RetrievalResult`, `RetrievalEvaluationResult` — 그대로 재사용
- `_generate_node`, `_evaluate_node` — 변경 없음
- `astream` — 기존 스트리밍 경로 유지

---

## 3. 클래스 구조

```
retrieval_agent.py
├── SearchMode (Enum)              # 검색 모드 5종
├── RetryLevel (Enum)              # 재시도 단계 5종
├── QueryCharacteristics (dataclass) # 쿼리 분석 결과
├── DocumentBudget (dataclass)      # 도메인별 문서 할당량
├── RetryContext (dataclass)        # 재시도 상태 추적
├── SearchStrategySelector          # 쿼리 → 검색 전략 결정
├── DocumentBudgetCalculator        # 도메인별 K값 할당
├── GraduatedRetryHandler           # 4단계 재시도
├── DocumentMerger                  # 복합 도메인 문서 병합
└── RetrievalAgent                  # 메인 오케스트레이터
```

---

## 4. 핵심 컴포넌트 상세

### 4.1 SearchMode — 검색 모드

```python
class SearchMode(str, Enum):
    HYBRID = "hybrid"           # BM25 + Vector + RRF (기본)
    VECTOR_HEAVY = "vector"     # 의미 기반 검색 강화
    BM25_HEAVY = "bm25"         # 키워드 매칭 강화
    MMR_DIVERSE = "mmr"         # MMR로 다양성 극대화
    EXACT_PLUS_VECTOR = "exact" # 법조문 정확 매칭 우선
```

### 4.2 SearchStrategySelector — 쿼리 분석

LLM 호출 없이 규칙 기반으로 쿼리를 분석하여 최적 검색 전략을 추천합니다.

| 쿼리 특성 | SearchMode | K값 | 판단 기준 |
|-----------|-----------|-----|----------|
| 짧은 사실형 | BM25_HEAVY | 3 | ≤20자 + 키워드 밀도 ≥0.3 |
| 법조문 인용 | EXACT_PLUS_VECTOR | 5 | "제X조", "법 제X항" 패턴 |
| 긴 서술형 | VECTOR_HEAVY | 7 | ≥50자 또는 10단어 이상 |
| 모호/광범위 | MMR_DIVERSE | 7 | ≥15자 + 키워드 밀도 <0.1 |
| 일반 질문 | HYBRID | 5 | 위 조건 미해당 |

**분석 항목**: 글자 수, 단어 수, 법조문 인용 여부, 숫자 포함, 도메인 키워드 밀도

### 4.3 DocumentBudgetCalculator — 예산 할당

복합 도메인 질문 시 도메인별 문서 수를 예산 기반으로 관리합니다.

```
단일 도메인:  K = recommended_k (3~7)
복합 2도메인: primary = ceil(max_total × 0.6), secondary = floor(max_total × 0.4)
복합 3도메인: primary = ceil(max_total × 0.5), secondary = 균등 분배
법률 보충:    별도 예산 (legal_supplement_k=3, 총 예산에 미포함)
```

**예시** (max_total=12, 2도메인):
- finance_tax (primary): 8건
- hr_labor (secondary): 4건

### 4.4 GraduatedRetryHandler — 단계적 재시도

검색 평가 실패 시 비용이 낮은 전략부터 순서대로 시도합니다.

| Level | 전략 | 비용 | 설명 |
|-------|------|------|------|
| 1 | RELAX_PARAMS | $0 | K +3 증가, 키워드 임계값 0.3→0.15, 유사도 0.5→0.35 |
| 2 | MULTI_QUERY | ~$0.01 | LLM 쿼리 확장 (3개 변형 + RRF) |
| 3 | CROSS_DOMAIN | $0 | 인접 도메인 검색 (아래 매핑 참조) |
| 4 | PARTIAL_ANSWER | $0 | 현재 문서로 진행 (포기) |

기본 설정(`max_retry_level=2`)에서는 Level 2(MULTI_QUERY)까지만 시도합니다.

**인접 도메인 매핑**:
```python
ADJACENT_DOMAINS = {
    "startup_funding": ["finance_tax"],
    "finance_tax": ["startup_funding", "law_common"],
    "hr_labor": ["law_common"],
    "law_common": ["hr_labor", "finance_tax"],
}
```

### 4.5 DocumentMerger — 문서 병합

복합 도메인 검색 결과를 하나의 문서 리스트로 병합합니다.

**처리 순서**:
1. **중복 제거**: 문서 앞 500자 MD5 해시 기반
2. **점수 정렬**: 도메인 내 similarity score 내림차순
3. **예산 적용**: 도메인별 `allocated_k`로 절단
4. **우선순위 병합**: primary 도메인 문서 우선 배치
5. **총 예산 적용**: `max_total` 초과 시 후순위 문서 제거

### 4.6 RetrievalAgent — 오케스트레이터

모든 컴포넌트를 조합하여 검색 파이프라인을 실행합니다.

```
Input: RouterState (sub_queries, query, domains)
  │
  ├─ 1. 쿼리 분석: strategy_selector.analyze()
  │     → QueryCharacteristics (모드, 추천 K)
  │
  ├─ 2. 예산 할당: budget_calculator.calculate()
  │     → dict[domain, DocumentBudget]
  │
  ├─ 3. 도메인별 검색 (동기: 순차 / 비동기: asyncio.gather 병렬):
  │     for each sub_query:
  │       ├─ search_mode에 따라 rag_chain.retrieve() 파라미터 설정
  │       ├─ 검색 실행
  │       ├─ 평가: RuleBasedRetrievalEvaluator.evaluate()
  │       └─ 실패 시: retry_handler.retry() (단계적)
  │
  ├─ 4. 법률 보충 검색 (조건부):
  │     if needs_legal_supplement(): → law_common_supplement
  │
  ├─ 5. 문서 병합 (복합 도메인만):
  │     merger.merge_and_prioritize()
  │
  └─ Output: RouterState 업데이트
       - retrieval_results
       - documents
       - timing_metrics
```

---

## 5. 설정 (config.py)

### 추가된 설정 필드

| 필드 | 타입 | 기본값 | 설명 |
|------|------|--------|------|
| `enable_adaptive_search` | bool | True | 쿼리 특성 기반 검색 전략 자동 선택 |
| `enable_dynamic_k` | bool | True | 쿼리 특성에 따라 K값 자동 조절 |
| `dynamic_k_min` | int | 3 | 동적 K 최소값 |
| `dynamic_k_max` | int | 8 | 동적 K 최대값 |
| `primary_domain_budget_ratio` | float | 0.6 | 복합 도메인 시 주 도메인 예산 비율 |
| `enable_graduated_retry` | bool | True | 단계적 재시도 활성화 |
| `max_retry_level` | int | 2 | 최대 재시도 단계 (0~4) |

모든 필드가 `_ALLOWED_OVERRIDES`에 포함되어 `Settings.override()`로 런타임 변경 가능합니다.

### 기존 방식으로 되돌리기

```python
settings.override(
    enable_adaptive_search=False,   # 고정 검색 모드
    enable_dynamic_k=False,         # 고정 K값
    enable_graduated_retry=False,   # 재시도 비활성화
)
```

---

## 6. router.py 변경 사항

### Before (~120줄)

```python
def _retrieve_node(self, state):
    # 직접 루프, 직접 평가, 직접 legal supplement...

async def _aretrieve_node(self, state):
    # 직접 병렬 검색, 직접 legal supplement...

def _perform_legal_supplement(self, ...):
    # ~50줄

async def _aperform_legal_supplement(self, ...):
    # ~50줄
```

### After (~5줄)

```python
def _retrieve_node(self, state: RouterState) -> RouterState:
    """검색 노드: RetrievalAgent에 위임합니다."""
    return self.retrieval_agent.retrieve(state)

async def _aretrieve_node(self, state: RouterState) -> RouterState:
    """비동기 검색 노드: RetrievalAgent에 위임합니다."""
    return await self.retrieval_agent.aretrieve(state)
```

`_perform_legal_supplement` / `_aperform_legal_supplement`는 **삭제** → `RetrievalAgent` 내부로 이동.

### __init__에 추가

```python
self.retrieval_agent = RetrievalAgent(
    agents=self.agents,
    rag_chain=shared_rag_chain,
    vector_store=self.vector_store,
)
```

---

## 7. 위/아래 호환성

### 위 (classify → decompose → **retrieve**)

- **입력 그대로**: `sub_queries`, `query`, `domains`, `history`, `user_context`
- 추가 입력 없음 — `QueryCharacteristics`는 내부에서 `query`로부터 자동 생성

### 아래 (**retrieve** → generate → evaluate)

- **출력 그대로**: `retrieval_results`, `documents`, `timing_metrics`
- `retrieval_results[domain].documents` — generate에서 도메인별 context 포맷에 사용
- `state["documents"]` — evaluate에서 전체 context로 사용
- `timing_metrics["agents"]` — 도메인별 타이밍 (기존 필드 유지)

### 스트리밍 (astream)

- 변경 없음 — 기존 단일 도메인 직접 검색 경로 유지
- `needs_legal_supplement` import는 router.py에 유지됨

---

## 8. 검증 방법

### 구문 검증 (완료)

```bash
cd rag
py -c "import ast; ast.parse(open('agents/retrieval_agent.py', encoding='utf-8').read()); print('OK')"
py -c "import ast; ast.parse(open('utils/config.py', encoding='utf-8').read()); print('OK')"
py -c "import ast; ast.parse(open('agents/router.py', encoding='utf-8').read()); print('OK')"
py -c "import ast; ast.parse(open('agents/__init__.py', encoding='utf-8').read()); print('OK')"
```

### 단위 테스트

```bash
cd rag && py -m pytest tests/unit/test_retrieval_agent.py -v
```

### 통합 테스트

```bash
cd rag && py -m evaluation.search_quality_eval --stage 2
```

### 수동 검증 (RAG 서비스 실행 후)

| 쿼리 | 기대 전략 | 기대 K |
|------|----------|--------|
| "부가세 신고 기한" | BM25_HEAVY | 3 |
| "근로기준법 제60조 연차 규정" | EXACT_PLUS_VECTOR | 5 |
| "창업하면서 세무 처리랑 근로계약서 작성법" | VECTOR_HEAVY | 7 |
| "사업 시작하려면 뭘 해야 하나요" | MMR_DIVERSE | 7 |

### A/B 비교

```python
# 기존 방식
settings.override(enable_adaptive_search=False, enable_graduated_retry=False)

# 새 방식 (기본값)
settings.override(enable_adaptive_search=True, enable_graduated_retry=True)
```
