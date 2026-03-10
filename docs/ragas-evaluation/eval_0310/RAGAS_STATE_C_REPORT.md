# RAGAS 평가 보고서 — State C (eval_0310)

> **State**: C — LLM 기반 도메인 분류 활성화
> **Commit**: `0542e0c`
> **VectorDB**: `vectordb.zip` (chunk_size=1500, State B와 동일)
> **평가 데이터셋**: `ragas_dataset_0310.jsonl` (80문항)
> **평가일**: 2026-03-10
> **평가 설정**: RAGAS 0.4.3 / gpt-4.1-mini / text-embedding-3-small (AR)
> **특이사항**: `ENABLE_LLM_DOMAIN_CLASSIFICATION=true`, `ENABLE_ACTION_AWARE_GENERATION=false`, `TOTAL_TIMEOUT=300`, `LLM_TIMEOUT=120`
> **Phase 1 패치**: `augmented_query` 미정의 버그 수정 (평가 목적 패치)

---

## 1. 전체 요약

| 메트릭 | 점수 |
|--------|------|
| **Faithfulness** | **0.6667** |
| **Answer Relevancy** | **0.7681** |
| **Context Precision** | **0.7013** |
| **Context Recall** | **0.5906** |
| **Context F1** | **0.6412** |
| **거부 정확도** | **0.80** (8/10) |
| 유효 응답 | 68/80 |
| 타임아웃 | 2/80 |
| Reject 케이스 | 10/80 |
| 정확 거부 | 8/10 |

> Context F1 = 2 × 0.7013 × 0.5906 / (0.7013 + 0.5906) = **0.6412**

---

## 2. 도메인별 성능

| 도메인 | N | Faithfulness | AR | CP | CR |
|--------|---|-------------|-----|-----|-----|
| startup_funding | 21 | 0.7656 | 0.7574 | 0.5708 | 0.5976 |
| law_common | 12 | 0.5179 | 0.7451 | 0.8259 | 0.5014 |
| finance_tax | 14 | 0.6510 | 0.8271 | 0.7488 | 0.5833 |
| hr_labor | 21 | 0.6632 | 0.7525 | 0.7290 | 0.6395 |

> N은 타임아웃(2건) 제외. startup의 D0301-S02, D0301-S03 타임아웃

---

## 3. 거부 정확도 분석

| 항목 | 결과 |
|------|------|
| Reject 질문 수 | 10 |
| 정확 거부 수 | 8 |
| 거부 정확도 | **80%** |
| 미거부 사례 | D0301-R02(주식투자), D0301-R03(부동산투자) — finance_tax로 라우팅 |

**분석**: State C에서 LLM 기반 도메인 분류 활성화로 대부분의 비도메인 질문을 거부 (8/10).
영어 거부 메시지("Sorry, this question is outside Bizi support scope")로 8건 정확 거부.
D0301-R02(주식투자)와 D0301-R03(부동산투자)는 finance_tax 도메인으로 잘못 라우팅됨.

---

## 4. 타임아웃 분석

| 질문 ID | 도메인 | 원인 |
|---------|--------|------|
| D0301-S02 | startup | 통신판매업 신고 관련 — 복잡한 멀티스텝 질문 |
| D0301-S03 | startup | 동일 유형 — 300s 타임아웃 |

> eval_0301 State C와 동일한 질문에서 타임아웃 발생 — 구조적 한계

---

## 5. State B 대비 비교

| 메트릭 | State B | State C | 변화 |
|--------|---------|---------|------|
| Faithfulness | 0.6401 | 0.6667 | +0.0266 |
| Answer Relevancy | 0.7537 | 0.7681 | +0.0144 |
| Context Precision | 0.6822 | 0.7013 | +0.0191 |
| Context Recall | 0.5524 | 0.5906 | +0.0382 |
| Context F1 | 0.6106 | 0.6412 | +0.0306 |
| 거부 정확도 | 100% | 80% | **-20%** |

**핵심**: LLM 기반 도메인 분류로 RAGAS 메트릭 전반 개선. 단, 일부 비도메인 질문이 finance_tax로 오분류되어 거부 정확도 하락.

---

## 6. 결과 파일

- Phase 1: `docs/ragas-evaluation/eval_0310/results/answers_state_c.json`
- Phase 2: `docs/ragas-evaluation/eval_0310/results/answers_state_c_evaluated.json`
