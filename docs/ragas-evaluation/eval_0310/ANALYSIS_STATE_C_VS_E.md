# State C vs State E 성능 차이 심층 분석 (eval_0310)

> **작성일**: 2026-03-10
> **분석 대상**: State C (`0542e0c`) vs State E (`ba51612`)
> **평가 데이터셋**: `ragas_dataset_0310.jsonl` (80문항)
> **분석 목적**: Context Recall 역전 현상(C > E)의 근본 원인 규명

---

## 0. 핵심 발견 요약

State C가 Context Recall(0.5906 vs 0.5258)과 Context F1(0.6412 vs 0.6064)에서 우세. 그러나 **State E는 `ENABLE_LLM_DOMAIN_CLASSIFICATION=false`(기본값)로 평가**되었으며, 이는 공정한 비교가 아닐 수 있음.

**→ State E를 `ENABLE_LLM_DOMAIN_CLASSIFICATION=true`로 재평가해야 진정한 비교 가능.**

---

## 1. 전체 메트릭 비교

| 메트릭 | State C | State E | 차이 (C−E) |
|--------|---------|---------|-----------|
| Faithfulness | 0.6667 | **0.6772** | −0.0105 |
| Answer Relevancy | 0.7681 | **0.7927** | −0.0246 |
| Context Precision | 0.7013 | **0.7161** | −0.0148 |
| **Context Recall** | **0.5906** | 0.5258 | **+0.0648** |
| **Context F1** | **0.6412** | 0.6064 | **+0.0348** |
| 거부 정확도 | 0.80 (8/10) | **1.00 (10/10)** | −0.20 |
| 타임아웃 | 2/80 | 0/80 | +2 |

**State C 우위**: Context Recall, Context F1
**State E 우위**: Faithfulness, Answer Relevancy, Context Precision, 거부 정확도, 타임아웃 없음

---

## 2. 평가 조건 차이 — 비교의 공정성 문제

| 조건 | State C | State E |
|------|---------|---------|
| `ENABLE_LLM_DOMAIN_CLASSIFICATION` | **true** (명시적 설정) | **false** (기본값, 미기재) |
| VectorDB | `vectordb.zip` | `vectordb_0305.zip` |
| 분류기 구조 | LLM → 벡터 유사도 → 키워드 (3-tier) | 키워드만 (2-tier) |

State C 보고서에는 `ENABLE_LLM_DOMAIN_CLASSIFICATION=true`가 명시됨.
State E 보고서의 특이사항에는 이 설정이 없음 → 기본값 `false`로 실행된 것으로 판단.

현재 main(`c69e4a8` 이후)에서는 LLM 분류가 기본 모드로 전환되었으므로, 이 평가는 State E의 실제 운영 환경과도 다름.

---

## 3. Context Recall 메트릭 개요

RAGAS LLM Context Recall 계산 방식:

```
Context Recall = (ground truth에서 검색 context로 귀속 가능한 claim 수)
                ─────────────────────────────────────────────────────────
                              ground truth 전체 claim 수
```

- ground truth를 개별 claim으로 분해
- 각 claim이 검색된 context에 귀속(attributable)될 수 있는지 LLM이 판정
- **낮은 값 = 검색 단계에서 정답에 필요한 정보 누락**

---

## 4. 근본 원인 분석

### 원인 1: LLM 도메인 분류의 Multi-Domain 라우팅 우위 (주요 원인)

질문 유형별로 분해하면 차이의 구조가 드러남:

| 질문 유형 | N | State C CR | State E CR | 차이 |
|-----------|---|-----------|-----------|------|
| **Multi-domain** | 30 | **0.7032** | 0.5385 | **+0.1647** |
| Single-domain | 38 | 0.5018 | 0.5171 | −0.0154 |

- Single-domain 질문에서는 C와 E가 사실상 동일(−0.015)
- **전체 격차(+0.065)의 거의 전부가 multi-domain 질문에서 발생**

**메커니즘:**
- Multi-domain 질문 예: "소상공인 미용실 재건축 명도 + 지원사업" → law_common + startup_funding 교차
- State C (LLM 분류): 질문의 의미를 이해하여 **복수 도메인 컬렉션에서 동시 검색**
- State E (키워드 전용): 표면적 키워드로만 판단 → **단일 도메인으로만 라우팅** → 다른 도메인 context 누락

**도메인×유형별 CR 차이 (큰 순):**

| 도메인/유형 | C CR | E CR | 차이 | 설명 |
|-------------|------|------|------|------|
| law_common/multi | 0.575 | 0.163 | **+0.413** | 법률+타도메인 교차에서 E가 법률 context 대거 누락 |
| startup_funding/multi | 0.775 | 0.503 | **+0.272** | 창업+세무/노무 교차 질문 |
| finance_tax/multi | 0.620 | 0.480 | **+0.140** | 세무+법률 교차 질문 |
| law_common/single | 0.465 | 0.579 | −0.115 | 단일 법률 질문에서는 E가 오히려 우위 |

### 원인 2: 벡터 도메인 분류 삭제의 부작용

State C→E 사이(`c2607b0`)에서 `VectorDomainClassifier` 완전 삭제:
- `enable_vector_domain_classification`, `domain_classification_threshold`, `multi_domain_gap_threshold` 설정 모두 제거
- Embeddings 의존성 및 도메인 벡터 사전계산 삭제

결과: LLM 분류 비활성화 시 **키워드 매칭만으로 도메인 결정**. 키워드에 명시되지 않는 도메인 연관성 포착 불가.

### 원인 3: VectorDB 리빌드 영향 (부차적)

- State C: `vectordb.zip` (원본)
- State E: `vectordb_0305.zip` (2025-03-05 리빌드)
- State D에서 이미 VectorDB 교체의 역효과 확인: C→D에서 Faithfulness −0.064, CP −0.061
- `vectordb_0305.zip`의 컬렉션별 문서 수·커버리지 차이가 Context Recall에 부분 기여 가능

---

## 5. 개별 질문 수준 증거

### State C가 크게 우세한 질문 (CR 차이 ≥ +0.50)

| ID | 질문 요약 | 유형 | C CR | E CR | 차이 |
|----|-----------|------|------|------|------|
| D0301-M13 | 소상공인 미용실 재건축 명도 + 지원사업 | law/multi | 0.80 | 0.00 | **+0.80** |
| D0301-T02 | 프리랜서 종합소득세 신고 + 절세 | tax/single | 0.80 | 0.20 | **+0.60** |
| D0301-L06 | 카페 상표 등록 절차/비용/기간 | law/single | 1.00 | 0.40 | **+0.60** |
| D0301-M14 | 개인사업자 법인전환 세무/법적 절차 | startup/multi | 1.00 | 0.40 | **+0.60** |
| D0301-M07 | IT 스타트업 세액감면/공제 조건 | startup/multi | 1.00 | 0.50 | **+0.50** |
| D0301-M08 | 사무실 건물 매입 취득세/등기/계약 | tax/multi | 0.50 | 0.00 | **+0.50** |

**D0301-M13 분석**: State E CR=0.00 — 관련 context 전혀 검색 못함. State C는 0.80.
추정 원인: LLM 분류기는 "명도소송"(law_common) + "지원사업"(startup_funding) 동시 라우팅.
키워드 분류기는 표면적 키워드 하나의 도메인으로만 전송 → context 전체 누락.

### State E가 우세한 질문 (소수, 주로 single-domain)

| ID | 도메인/유형 | C CR | E CR | 차이 |
|----|-------------|------|------|------|
| D0301-L04 | law/single | 0.40 | 1.00 | −0.60 |
| D0301-L08 | law/single | 0.00 | 0.60 | −0.60 |

단일 도메인 법률 질문에서 E가 우세한 경우 존재.
`vectordb_0305.zip`의 law_common 컬렉션이 특정 질문에 더 나은 커버리지를 가지거나,
State E의 라우터 개선(follow-up 도메인 폴백, 쿼리 재작성 등)이 효과를 발휘한 것으로 추정.

---

## 6. Trade-off 구조

```
State C (LLM 분류 ON)
├── 장점: Multi-domain 질문의 정확한 라우팅 → Context Recall ↑ (+0.0648)
├── 단점: "주식투자", "부동산투자" OOB 질문을 finance_tax로 오분류 → 거부 정확도 80%
└── 단점: 타임아웃 2건 (LLM 분류 추가 호출로 인한 지연)

State E (키워드 전용, LLM OFF)
├── 장점: 100% 거부 정확도, 0 타임아웃
├── 장점: Faithfulness(+0.0105), AR(+0.0246), CP(+0.0148) 모두 소폭 우위
└── 단점: Multi-domain 질문에서 context 누락 → Context Recall −0.0648
```

---

## 7. 결론

### 핵심 결론
State C의 Context Recall 우위는 **LLM 도메인 분류기의 multi-domain 라우팅 능력** 때문.
30개 multi-domain 질문에서 평균 +0.165의 CR 차이가 전체 격차(+0.065)의 거의 전부를 설명.

**단, 이는 State E 평가 시 `ENABLE_LLM_DOMAIN_CLASSIFICATION=false`(기본값)로 실행된 결과.**
State E 코드 자체는 LLM 분류를 완전히 지원하며, 현재 main에서 LLM 분류가 기본 모드로 전환됨.
따라서 이 비교는 불완전하며, **State E를 LLM 분류 활성화 상태로 재평가해야 정확한 비교 가능**.

### 권고 사항

1. **즉시**: State E(`ba51612`)를 `ENABLE_LLM_DOMAIN_CLASSIFICATION=true`로 재평가
   - 재평가 계획: `tasks/ragas-reeval-state-e-llm-on.md` 참조
   - 예상: State E의 Context Recall이 State C 수준 이상으로 개선될 가능성 높음

2. **재평가 후**: OOB 거부 로직 강화
   - LLM 분류 프롬프트에 "주식투자/부동산투자/암호화폐 등은 반드시 reject" 명시
   - 목표: LLM 분류 ON + 거부 정확도 100% 동시 달성

3. **추가**: VectorDB 정합성 검증
   - `vectordb_0305.zip` vs `vectordb.zip` 컬렉션별 문서 수·커버리지 비교

---

## 참고 자료

- [RAGAS Context Recall 공식 문서](https://docs.ragas.io/en/v0.1.21/concepts/metrics/context_recall.html)
- [RAGAS 논문 (arXiv:2309.15217)](https://arxiv.org/abs/2309.15217)
- State C 보고서: `RAGAS_STATE_C_REPORT.md`
- State E 보고서: `RAGAS_STATE_E_REPORT.md`
- 종합 비교: `COMPREHENSIVE_REPORT.md`
