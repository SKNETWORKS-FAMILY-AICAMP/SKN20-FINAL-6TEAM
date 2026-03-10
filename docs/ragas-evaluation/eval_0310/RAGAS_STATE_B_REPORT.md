# RAGAS 평가 보고서 — State B (eval_0310)

> **State**: B — VectorDB 개선 (chunk_size=800→1500)
> **Commit**: `160d05b`
> **VectorDB**: `vectordb.zip` (chunk_size=1500, 4 collections, 총 ~726MB)
> **평가 데이터셋**: `ragas_dataset_0310.jsonl` (80문항)
> **평가일**: 2026-03-10
> **평가 설정**: RAGAS 0.4.3 / gpt-4.1-mini / text-embedding-3-small (AR)
> **특이사항**: `ENABLE_ACTION_AWARE_GENERATION=false`, `TOTAL_TIMEOUT=300`, `LLM_TIMEOUT=120`

---

## 1. 전체 요약

| 메트릭 | 점수 |
|--------|------|
| **Faithfulness** | **0.6401** |
| **Answer Relevancy** | **0.7537** |
| **Context Precision** | **0.6822** |
| **Context Recall** | **0.5524** |
| **Context F1** | **0.6106** |
| **거부 정확도** | **1.00** (10/10) |
| 유효 응답 | 70/80 |
| 타임아웃 | 0/80 |
| Reject 케이스 | 10/80 |
| 정확 거부 | 10/10 |

> Context F1 = 2 × 0.6822 × 0.5524 / (0.6822 + 0.5524) = **0.6106**

---

## 2. 도메인별 성능

| 도메인 | N | Faithfulness | AR | CP | CR |
|--------|---|-------------|-----|-----|-----|
| startup_funding | 25 | 0.7641 | 0.7381 | 0.5988 | 0.5523 |
| law_common | 14 | 0.5150 | 0.6845 | 0.7856 | 0.4702 |
| finance_tax | 13 | 0.5141 | 0.8168 | 0.6521 | 0.6128 |
| hr_labor | 18 | 0.6561 | 0.7834 | 0.7394 | 0.5728 |

> State B부터 law_common 도메인 에이전트가 별도 분류되어 집계됨

---

## 3. 거부 정확도 분석

| 항목 | 결과 |
|------|------|
| Reject 질문 수 | 10 |
| 정확 거부 수 | 10 |
| 거부 정확도 | **100%** |

**분석**: State B에서 도메인 거부 기능이 완벽히 동작. chunk_size=1500으로 벡터DB 품질 향상 및
거부 임계값/로직 개선 효과로 비도메인 질문을 모두 정확히 거부.

---

## 4. State A 대비 비교

| 메트릭 | State A | State B | 변화 |
|--------|---------|---------|------|
| Faithfulness | 0.4196 | 0.6401 | **+0.2205** |
| Answer Relevancy | 0.7354 | 0.7537 | +0.0183 |
| Context Precision | 0.5697 | 0.6822 | **+0.1125** |
| Context Recall | 0.3745 | 0.5524 | **+0.1779** |
| Context F1 | 0.4519 | 0.6106 | **+0.1587** |
| 거부 정확도 | 10% | **100%** | **+90%** |

**핵심 개선**: VectorDB 청크 크기 증가(800→1500)가 Faithfulness, CR 모두 대폭 향상.
거부 정확도 0%→100% 개선은 State B의 도메인 분류 로직 정교화 효과.

---

## 5. 결과 파일

- Phase 1: `docs/ragas-evaluation/eval_0310/results/answers_state_b.json`
- Phase 2: `docs/ragas-evaluation/eval_0310/results/answers_state_b_evaluated.json`
