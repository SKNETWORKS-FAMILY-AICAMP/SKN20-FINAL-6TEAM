# 복합 도메인 질문 처리 개선 계획

## 요구사항 요약

- 사용자 요청: Bizi RAG 시스템에서 복합 도메인 질문(예: "직원 해고 시 퇴직금 세금 처리와 법적 절차는?") 처리 시 발생하는 문제점 분석 및 개선안 제출
- 핵심 목표: 2개 이상 도메인에 걸치는 복합 질문의 분류 정확도, 검색 품질, 응답 통합성 향상

## 현황 분석 결과 -- 복합 도메인 처리 파이프라인 전체 흐름

```
사용자 질문
    |
    v
[1. classify] VectorDomainClassifier.classify()
    |-- 키워드 매칭 (_keyword_classify)
    |-- 벡터 유사도 (_vector_classify)
    |-- 복합 도메인 탐지: best_score - score < 0.1 이면 추가 도메인 포함
    |
    v
[2. decompose] QuestionDecomposer.adecompose()
    |-- 단일 도메인이면 스킵
    |-- LLM 호출로 질문을 도메인별 SubQuery로 분해
    |
    v
[3. retrieve] RetrievalAgent.aretrieve()
    |-- SearchStrategySelector.analyze() → 쿼리 특성 분석
    |-- DocumentBudgetCalculator.calculate() → 도메인별 K값 할당
    |-- 도메인별 병렬 검색 (asyncio.gather)
    |-- GraduatedRetryHandler → 검색 평가 실패 시 단계적 재시도
    |-- 법률 보충 검색 (needs_legal_supplement)
    |-- DocumentMerger.merge_and_prioritize() → 복합 도메인 문서 병합
    |-- Cross-Domain Reranking (선택적)
    |
    v
[4. generate] ResponseGeneratorAgent.agenerate()
    |-- 단일 도메인: 도메인 프롬프트 사용
    |-- 복수 도메인: MULTI_DOMAIN_SYNTHESIS_PROMPT로 통합 생성
    |
    v
[5. evaluate] EvaluatorAgent.aevaluate()
    |-- LLM 평가 (100점 만점, 70점 이상 PASS)
    |-- FAIL 시 _aretry_with_alternatives_node (멀티쿼리 대체)
```

## 문제점 목록

### P0 (Critical) -- 결과에 직접적 영향

#### P0-1: 벡터 유사도 복합 도메인 탐지 임계값이 고정적 (0.1)

**파일**: `rag/utils/domain_classifier.py` L274-278

```python
# 복수 도메인 탐지: 최고 점수와 0.1 이내 차이인 도메인 포함
detected_domains = [best_domain]
for domain, score in sorted_domains[1:]:
    if best_score - score < 0.1 and score >= threshold:
        detected_domains.append(domain)
```

**문제**:
- 0.1 이라는 고정 갭은 도메인 간 벡터 공간 특성을 무시한다. 예를 들어 "직원 해고 시 퇴직금 세금 처리와 법적 절차는?"이라는 질문에서 hr_labor(해고, 퇴직금)가 best_score이고 finance_tax(세금)는 0.12 차이, law_common(법적 절차)은 0.15 차이라면, finance_tax와 law_common 모두 누락된다.
- 실질적으로 3개 도메인이 관련된 질문인데 1개 도메인으로만 분류될 수 있다.
- 키워드 매칭이 3개 도메인을 모두 잡더라도, `keyword+vector` 경로에서 `boosted_confidence >= threshold`일 때 `final_domains = keyword_result.domains if not vector_result.is_relevant else vector_result.domains`로 결정되므로, 벡터가 통과했으면 벡터의 (부족한) 도메인 리스트가 사용된다.

**근본 원인**: 벡터 유사도만으로 복합 도메인을 탐지하는 구조적 한계. 키워드 매칭 결과를 도메인 리스트 보강에 적극 활용하지 않는다.

#### P0-2: 키워드+벡터 조합 시 도메인 리스트 병합 로직 결함 

**파일**: `rag/utils/domain_classifier.py` L395-416

```python
if vector_result.is_relevant or boosted_confidence >= threshold:
    if boosted_confidence >= threshold:
        # 키워드 도메인 기준으로 결과 생성
        final_domains = keyword_result.domains if not vector_result.is_relevant else vector_result.domains
```

**문제**:
- `vector_result.is_relevant = True`(벡터 통과)인 경우, `final_domains = vector_result.domains`가 되어 키워드가 추가로 감지한 도메인이 무시된다.
- 예: 키워드가 [hr_labor, finance_tax, law_common] 3개를 감지했지만, 벡터가 [hr_labor]만 통과하면 최종 결과는 [hr_labor]만 된다.
- 키워드 결과와 벡터 결과의 **합집합**이 아닌 **택일** 방식으로, 복합 도메인 질문에서 핵심 도메인이 누락된다.

#### P0-3: Cross-Domain Reranking이 문서 수를 주 도메인 K로 축소

**파일**: `rag/agents/retrieval_agent.py` L1074-1086

```python
primary_budget = next(
    (b for b in budgets.values() if b.is_primary), None
)
final_k = primary_budget.allocated_k if primary_budget else self.settings.retrieval_k
reranker = self.rag_chain.reranker
if reranker and len(merged) > final_k:
    merged = reranker.rerank(query, merged, top_k=final_k)
```

**문제**:
- `enable_fixed_doc_limit=True`(기본값)일 때, 모든 도메인에 동일한 K(=3)가 할당된다 (`_calculate_bounded`).
- 2개 도메인이면 총 6건의 문서가 검색되지만, cross-domain rerank 후 `final_k=3`으로 절반이 잘린다.
- 이때 주 도메인 문서만 살아남고 부 도메인 문서가 전부 제거될 수 있어, 복합 질문에서 한 도메인의 컨텍스트가 완전히 유실된다.

### P1 (Important) -- 품질에 유의미한 영향

#### P1-1: 질문 분해(decompose) 시 도메인 간 연결 맥락 유실

**파일**: `rag/utils/question_decomposer.py`, `rag/utils/prompts.py` L464-519

**문제**:
- `QUESTION_DECOMPOSER_PROMPT`는 각 하위 질문이 "독립적으로 이해 가능"하도록 분해하라고 지시한다.
- "직원 해고 시 퇴직금 세금 처리와 법적 절차"에서 분해하면:
  - hr_labor: "직원 해고 시 퇴직금 처리 방법"
  - finance_tax: "퇴직금 세금 처리 방법"
  - law_common: "직원 해고 시 법적 절차"
- 각 하위 질문은 독립적이지만, "퇴직금에 대한 세금"이라는 **도메인 간 연결점**이 명시되지 않아 검색이 일반적인 세금 문서를 가져올 수 있다.

#### P1-2: 법률 보충 검색이 복합 도메인에서 이중 검색 유발

**파일**: `rag/agents/retrieval_agent.py` L1003-1011, `rag/utils/legal_supplement.py` L44-92

**문제**:
- 복합 도메인으로 [hr_labor, law_common]이 분류된 경우:
  - law_common 에이전트가 이미 검색 수행 (도메인별 병렬 검색 단계)
  - 그런데 `needs_legal_supplement()`는 `"law_common" in classified_domains`일 때만 보충을 스킵한다.
  - 하지만 `classified_domains`가 `["hr_labor", "law_common"]`이면 `"law_common" in classified_domains`는 True → 보충 스킵된다 (정상).

  그러나 **실제 문제**는 반대 경우:
  - 분류가 [hr_labor, finance_tax]로만 됐을 때(P0-1/P0-2 문제로 law_common 누락), 질문에 "법적 절차"라는 법률 키워드가 있어 법률 보충 검색이 트리거된다.
  - 이때 법률 보충은 원본 query 전체("직원 해고 시 퇴직금 세금 처리와 법적 절차는?")로 검색하는데, 이는 법률에 특화된 하위 질문이 아니라 복합 질문 전체이므로 검색 정밀도가 떨어진다.

#### P1-3: 복합 도메인 통합 프롬프트에 하위 질문 정보 미전달

**파일**: `rag/agents/generator.py` L624-686, `rag/utils/prompts.py` L562-607

**문제**:
- `_agenerate_multi()`는 `MULTI_DOMAIN_SYNTHESIS_PROMPT`를 사용하는데, 이 프롬프트에 전달되는 변수는:
  - `{query}`: 원본 복합 질문
  - `{context}`: 전체 문서 병합
  - `{domains_description}`: 도메인 한글 라벨
  - `{actions_context}`: 액션 리스트
- **`sub_queries`가 프롬프트에 전달되지 않는다.**
- LLM은 각 도메인에 대해 어떤 하위 질문이 분해되었는지 모른 채, 원본 복합 질문과 뒤섞인 문서만 보고 답변을 생성한다.
- 이로 인해 도메인별 답변 구조가 모호해지고, 특정 도메인의 답변이 누락되거나 불균형해질 수 있다.

#### P1-4: DocumentBudget의 bounded 방식에서 복합 도메인 총 문서량 미제어

**파일**: `rag/agents/retrieval_agent.py` L265-302

```python
def _calculate_bounded(self, domains, recommended_k, retrieval_k):
    k = min(recommended_k, retrieval_k)
    if len(domains) == 1:
        return {domains[0]: DocumentBudget(..., allocated_k=k, ...)}
    # 복합 도메인: 각 도메인에 k 균등 할당
    for i, domain in enumerate(domains):
        budgets[domain] = DocumentBudget(..., allocated_k=k, ...)
```

**문제**:
- 3개 도메인이면 총 문서 = 3 * 3 = 9건 + 법률 보충 3건 = 12건
- 4개 도메인이면 총 문서 = 4 * 3 = 12건 + 법률 보충 3건 = 15건
- `max_retrieval_docs=10`(기본값)이 있지만 이것은 `_calculate_bounded`에서 참조되지 않는다.
- LLM 컨텍스트 윈도우에 과도한 문서가 들어가 노이즈가 증가한다.

#### P1-5: 스트리밍 경로에서 복합 도메인 평가(evaluate) 단계 누락

**파일**: `rag/agents/router.py` L876-926

**문제**:
- `astream()` 메서드의 복수 도메인 경로에서는:
  1. decompose
  2. retrieve
  3. generate (스트리밍)
  만 수행하고, **evaluate 노드가 호출되지 않는다.**
- 비스트리밍 `aprocess()`는 LangGraph 그래프를 통해 evaluate → retry_with_alternatives 까지 수행하지만, 스트리밍은 이를 건너뛴다.
- 스트리밍이 프로덕션 주력 경로라면, 복합 도메인 답변의 품질 보장이 안 된다.

### P2 (Nice-to-have) -- 최적화/개선 가능

#### P2-1: 벡터 복합 도메인 갭 임계값이 설정 불가

**파일**: `rag/utils/domain_classifier.py` L276

- `0.1`이라는 매직 넘버가 하드코딩되어 있다. `config.py`의 Settings에서 설정 가능해야 한다.

#### P2-2: DocumentMerger의 중복 제거가 MD5 앞 500자 기반

**파일**: `rag/agents/retrieval_agent.py` L668-672

```python
def _content_hash(doc: Document) -> str:
    content = doc.page_content[:500]
    return hashlib.md5(content.encode("utf-8")).hexdigest()
```

- 500자가 동일하고 이후 내용이 다른 문서는 중복으로 처리된다.
- 복합 도메인에서 같은 법령의 다른 조항이 앞부분이 비슷할 경우 유효한 문서가 제거될 수 있다.

#### P2-3: 복합 도메인 분해 결과 캐시가 도메인 순서에 민감

**파일**: `rag/utils/question_decomposer.py` L66-87

- `_build_cache_key`에서 `",".join(sorted(domains))`를 사용하므로 순서 문제는 없지만, 같은 질문이라도 이전 assistant 응답이 다르면 캐시 미스 발생.

#### P2-4: 복합 도메인 질문의 evaluation_data에 첫 도메인 검색 결과만 포함

**파일**: `rag/agents/router.py` L676-690

```python
for domain, result in retrieval_results.items():
    if result and result.evaluation:
        ...
        break  # 첫 번째 도메인만 사용
```

- 복합 도메인의 경우 모든 도메인의 검색 평가를 집계해야 정확한 품질 측정이 가능하다.

## 영향 범위

| 서비스 | 변경 파일 | 변경 내용 |
|--------|----------|----------|
| rag | `rag/utils/domain_classifier.py` | 복합 도메인 탐지 로직 개선 (키워드+벡터 합집합) |
| rag | `rag/utils/config.py` | 복합 도메인 갭 임계값 설정 추가 |
| rag | `rag/agents/retrieval_agent.py` | cross-domain rerank final_k 계산 수정, bounded budget 총량 제어 |
| rag | `rag/agents/generator.py` | 복합 도메인 프롬프트에 sub_queries 전달 |
| rag | `rag/utils/prompts.py` | MULTI_DOMAIN_SYNTHESIS_PROMPT에 sub_queries 섹션 추가 |
| rag | `rag/utils/question_decomposer.py` | 도메인 간 연결점 보존 개선 (프롬프트 수정) |
| rag | `rag/agents/router.py` | 스트리밍 복합 도메인 평가 추가, evaluation_data 집계 |
| rag | `rag/utils/legal_supplement.py` | 복합 도메인 시 하위 질문 기반 보충 검색 |

## 리스크 및 의존성

- **리스크 1 (높음)**: P0-1/P0-2 수정 시 도메인 분류 결과가 변경되므로, 기존 단일 도메인 질문의 분류 정확도에 영향을 줄 수 있음. 반드시 기존 테스트 케이스로 회귀 검증 필요.
- **리스크 2 (중간)**: P0-3의 final_k 변경은 LLM에 전달되는 컨텍스트 양이 증가하여 비용/지연이 증가할 수 있음. max_retrieval_docs로 상한 보장 필요.
- **리스크 3 (낮음)**: P1-3의 프롬프트 변경은 답변 형식에 영향을 줄 수 있음. A/B 테스트 권장.
- **의존성**: P0-1/P0-2는 반드시 함께 수정해야 함 (분류 로직의 같은 흐름). P1-2는 P0-1/P0-2 수정 후 법률 도메인이 정상 분류되면 빈도가 감소.

## 구현 단계

| 순서 | 태스크 | 위임 에이전트 | 의존성 | 예상 변경량 |
|------|--------|-------------|--------|-----------|
| 1 | P0-1/P0-2: 도메인 분류 복합 도메인 탐지 개선 | rag-specialist | 없음 | ~60줄 |
| 2 | P2-1: 복합 도메인 갭 임계값 설정화 | rag-specialist | 1 | ~10줄 |
| 3 | P0-3: cross-domain rerank final_k 계산 수정 | rag-specialist | 없음 | ~20줄 |
| 4 | P1-4: bounded budget 총 문서량 제어 | rag-specialist | 3 | ~15줄 |
| 5 | P1-1: 질문 분해 프롬프트 도메인 연결점 보존 | rag-specialist | 없음 | ~20줄 |
| 6 | P1-3: 통합 프롬프트에 sub_queries 전달 | rag-specialist | 5 | ~30줄 |
| 7 | P1-2: 법률 보충 검색 하위 질문 기반 개선 | rag-specialist | 1 | ~25줄 |
| 8 | P1-5: 스트리밍 복합 도메인 평가 추가 | rag-specialist | 없음 | ~40줄 |
| 9 | P2-4: evaluation_data 복합 도메인 집계 | rag-specialist | 없음 | ~20줄 |
| 10 | 테스트 작성 및 회귀 검증 | tdd-guide | 1-9 | ~200줄 |

## 테스트 전략

### 단위 테스트
- `VectorDomainClassifier.classify()`: 복합 도메인 질문 10개에 대해 기대 도메인 리스트 검증
- `DocumentBudgetCalculator._calculate_bounded()`: 2~4개 도메인 시나리오별 총 문서량 검증
- `DocumentMerger.merge_and_prioritize()`: cross-domain rerank 후 도메인 다양성 보존 검증
- `needs_legal_supplement()`: 복합 도메인 [hr_labor, law_common] 시 보충 스킵 검증

### 통합 테스트
- 복합 도메인 질문 5개에 대해 전체 파이프라인 실행, 응답에 모든 도메인 관련 내용 포함 검증
- 스트리밍 vs 비스트리밍 경로의 응답 품질 비교

### 회귀 테스트
- 기존 단일 도메인 질문 20개에 대해 분류 정확도 유지 확인
- 기존 테스트 스위트 전체 통과 확인

## 예상 변경 파일 목록

- `rag/utils/domain_classifier.py` -- 복합 도메인 탐지, 키워드+벡터 합집합
- `rag/utils/config.py` -- multi_domain_gap_threshold 설정 추가
- `rag/agents/retrieval_agent.py` -- cross-domain rerank final_k, bounded budget 상한
- `rag/agents/generator.py` -- _agenerate_multi에 sub_queries 전달
- `rag/utils/prompts.py` -- MULTI_DOMAIN_SYNTHESIS_PROMPT에 하위 질문 섹션, QUESTION_DECOMPOSER_PROMPT에 연결점 지침
- `rag/utils/question_decomposer.py` -- 프롬프트 변수에 연결점 힌트
- `rag/agents/router.py` -- 스트리밍 평가, evaluation_data 집계
- `rag/utils/legal_supplement.py` -- 하위 질문 기반 보충 검색 지원
- `rag/tests/unit/test_domain_classifier.py` -- 복합 도메인 테스트 추가
- `rag/tests/unit/test_retrieval_agent.py` -- budget, merger, rerank 테스트
- `rag/tests/unit/test_generator.py` -- 복합 프롬프트 테스트
- `rag/tests/integration/test_multi_domain.py` -- 통합 테스트

---

## 부록: 각 문제별 구체적 코드 수준 개선안

### P0-1/P0-2 개선안: 키워드+벡터 도메인 합집합

```python
# domain_classifier.py classify() 메서드 수정

def classify(self, query: str) -> DomainClassificationResult:
    keyword_result = self._keyword_classify(query)

    if self.settings.enable_vector_domain_classification:
        vector_result = self._vector_classify(query)
    else:
        vector_result = None

    if vector_result:
        threshold = self.settings.domain_classification_threshold

        if keyword_result and vector_result.is_relevant:
            # 핵심 변경: 키워드 도메인과 벡터 도메인의 합집합
            merged_domains = list(dict.fromkeys(
                vector_result.domains +
                [d for d in keyword_result.domains if d not in vector_result.domains]
            ))
            boosted_confidence = min(1.0, vector_result.confidence + 0.1)

            return DomainClassificationResult(
                domains=merged_domains,
                confidence=boosted_confidence,
                is_relevant=True,
                method="keyword+vector",
                matched_keywords=keyword_result.matched_keywords,
            )

        if keyword_result and not vector_result.is_relevant:
            boosted_confidence = min(1.0, vector_result.confidence + 0.1)
            if boosted_confidence >= threshold:
                return DomainClassificationResult(
                    domains=keyword_result.domains,
                    confidence=boosted_confidence,
                    is_relevant=True,
                    method="keyword+vector",
                    matched_keywords=keyword_result.matched_keywords,
                )

        if vector_result.is_relevant:
            return vector_result

        return vector_result

    if keyword_result:
        return keyword_result

    return DomainClassificationResult(
        domains=[], confidence=0.0, is_relevant=False, method="fallback_rejected",
    )
```

### P0-3 개선안: cross-domain rerank final_k 계산

```python
# retrieval_agent.py _merge_with_optional_rerank() 수정

# 변경 전:
# final_k = primary_budget.allocated_k

# 변경 후:
# 모든 도메인의 예산 합계를 final_k로 사용하되, max_retrieval_docs로 상한
final_k = min(
    sum(b.allocated_k for b in budgets.values() if b.domain in main_results),
    self.settings.max_retrieval_docs,
)
```

### P1-3 개선안: 통합 프롬프트에 sub_queries 전달

```python
# generator.py _agenerate_multi() 수정

# sub_queries를 프롬프트에 전달
sub_queries_text = "\n".join(
    f"- [{DOMAIN_LABELS.get(sq.domain, sq.domain)}] {sq.query}"
    for sq in sub_queries
)

# prompts.py MULTI_DOMAIN_SYNTHESIS_PROMPT에 추가
# ## 분해된 하위 질문
# {sub_queries_text}
#
# 위 하위 질문 각각에 대해 검색된 문서에서 답변 근거를 찾아 통합 답변을 작성하세요.
```

### P1-4 개선안: bounded budget 총량 제어

```python
# retrieval_agent.py _calculate_bounded() 수정

def _calculate_bounded(self, domains, recommended_k, retrieval_k):
    k = min(recommended_k, retrieval_k)

    if len(domains) == 1:
        return {domains[0]: DocumentBudget(..., allocated_k=k, ...)}

    # 총 문서량이 max_retrieval_docs를 초과하지 않도록 조정
    settings = get_settings()
    total = k * len(domains)
    if total > settings.max_retrieval_docs:
        k = max(2, settings.max_retrieval_docs // len(domains))

    budgets = {}
    for i, domain in enumerate(domains):
        budgets[domain] = DocumentBudget(
            domain=domain, allocated_k=k, is_primary=(i == 0), priority=i + 1,
        )
    return budgets
```
