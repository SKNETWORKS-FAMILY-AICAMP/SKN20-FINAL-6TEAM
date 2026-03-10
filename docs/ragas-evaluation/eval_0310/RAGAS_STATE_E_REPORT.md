# RAGAS 평가 보고서 — State E (eval_0310)

> **State**: E — 현재 main (ACTION_AWARE=false)
> **Commit**: `ba51612`
> **VectorDB**: `vectordb_0305.zip` (chunk_size=1500, 4 collections)
> **평가 데이터셋**: `ragas_dataset_0310.jsonl` (80문항)
> **평가일**: 2026-03-10
> **평가 설정**: RAGAS 0.4.3 / gpt-4.1-mini / text-embedding-3-small (AR)
> **특이사항**: `ENABLE_ACTION_AWARE_GENERATION=false`, `TOTAL_TIMEOUT=300`, `LLM_TIMEOUT=120`

---

## 1. 전체 요약

| 메트릭 | 점수 |
|--------|------|
| **Faithfulness** | **0.6772** |
| **Answer Relevancy** | **0.7927** |
| **Context Precision** | **0.7161** |
| **Context Recall** | **0.5258** |
| **Context F1** | **0.6064** |
| **거부 정확도** | **1.00** (10/10) |
| 유효 응답 | 70/80 |
| 타임아웃 | 0/80 |
| Reject 케이스 | 10/80 |
| 정확 거부 | 10/10 |

> Context F1 = 2 × 0.7161 × 0.5258 / (0.7161 + 0.5258) = **0.6064**

---

## 2. 도메인별 성능

| 도메인 | N | Faithfulness | AR | CP | CR |
|--------|---|-------------|-----|-----|-----|
| startup_funding | 22 | 0.7460 | 0.8143 | 0.6895 | 0.4674 |
| law_common | 13 | 0.5575 | 0.7852 | 0.7123 | 0.4449 |
| finance_tax | 14 | 0.5501 | 0.8032 | 0.6605 | 0.4452 |
| hr_labor | 21 | 0.7638 | 0.7679 | 0.7833 | 0.6907 |

---

## 3. 거부 정확도 분석

| 항목 | 결과 |
|------|------|
| Reject 질문 수 | 10 |
| 정확 거부 수 | 10 |
| 거부 정확도 | **100%** |

**분석**: State E에서 도메인 거부 기능이 완벽히 동작.
"죄송합니다. 해당 질문은 Bizi의 상담 범위에 포함되지 않습니다." 한국어 거부 응답으로 10/10 정확 거부.

---

## 4. State A 대비 비교

| 메트릭 | State A | State E | 변화 |
|--------|---------|---------|------|
| Faithfulness | 0.4196 | 0.6772 | **+0.2576** |
| Answer Relevancy | 0.7354 | 0.7927 | +0.0573 |
| Context Precision | 0.5697 | 0.7161 | **+0.1464** |
| Context Recall | 0.3745 | 0.5258 | **+0.1513** |
| Context F1 | 0.4519 | 0.6064 | **+0.1545** |
| 거부 정확도 | 10% | **100%** | **+90%** |

**핵심 개선**: 모든 메트릭에서 State A 대비 대폭 향상.
Faithfulness +0.2576(+61.4%), AR +0.0573(+7.8%), CP +0.1464(+25.7%), CR +0.1513(+40.4%).

---

## 5. eval_0301 State E 대비 비교

| 메트릭 | eval_0301 State E | eval_0310 State E | 변화 |
|--------|-------------------|-------------------|------|
| Faithfulness | 0.6145 | 0.6772 | **+0.0627** |
| Answer Relevancy | 0.6803 | 0.7927 | **+0.1124** |
| Context Precision | 0.7388 | 0.7161 | -0.0227 |
| Context Recall | 0.5490 | 0.5258 | -0.0232 |
| 거부 정확도 | 100% | 100% | 0% |

**분석**:
- Faithfulness, AR: eval_0310에서 개선 (데이터셋·프롬프트 개선 효과)
- CP, CR: 소폭 하락 (데이터셋 문항 구성 차이 — multi 30문항 포함)

---

## 6. 결과 파일

- Phase 1: `docs/ragas-evaluation/eval_0310/results/answers_state_e.json`
- Phase 2: `docs/ragas-evaluation/eval_0310/results/answers_state_e_evaluated.json`
