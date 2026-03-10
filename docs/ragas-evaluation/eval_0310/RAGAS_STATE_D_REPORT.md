# RAGAS 평가 보고서 — State D (eval_0310)

> **State**: D — vectordb_full 적용 (full VectorDB)
> **Commit**: `24889e0`
> **VectorDB**: `vectordb_full.zip` (chunk_size=1500, 4 collections)
> **평가 데이터셋**: `ragas_dataset_0310.jsonl` (80문항)
> **평가일**: 2026-03-10
> **평가 설정**: RAGAS 0.4.3 / gpt-4.1-mini / text-embedding-3-small (AR)
> **특이사항**: `ENABLE_ACTION_AWARE_GENERATION=false`, `TOTAL_TIMEOUT=300`, `LLM_TIMEOUT=120`

---

## 1. 전체 요약

| 메트릭 | 점수 |
|--------|------|
| **Faithfulness** | **0.6192** |
| **Answer Relevancy** | **0.7302** |
| **Context Precision** | **0.6660** |
| **Context Recall** | **0.5884** |
| **Context F1** | **0.6248** |
| **거부 정확도** | **0.80** (8/10) |
| 유효 응답 | 68/80 |
| 타임아웃 | 2/80 |
| Reject 케이스 | 10/80 |
| 정확 거부 | 8/10 |

> Context F1 = 2 × 0.6660 × 0.5884 / (0.6660 + 0.5884) = **0.6248**
> 거부 정확도: 영어 거부 메시지("outside Bizi support scope") 8건 정확 거부, R02·R03 미거부

---

## 2. 도메인별 성능

| 도메인 | N | Faithfulness | AR | CP | CR |
|--------|---|-------------|-----|-----|-----|
| startup_funding | 20 | 0.6977 | 0.7449 | 0.5056 | 0.5467 |
| law_common | 13 | 0.3790 | 0.7203 | 0.7800 | 0.4256 |
| finance_tax | 13 | 0.6152 | 0.7229 | 0.7739 | 0.6949 |
| hr_labor | 22 | 0.6922 | 0.7269 | 0.6807 | 0.6595 |

> N은 타임아웃(2건) 제외. D0301-S01, D0301-S02 타임아웃

---

## 3. 거부 정확도 분석

| 항목 | 결과 |
|------|------|
| Reject 질문 수 | 10 |
| 정확 거부 수 | 8 |
| 거부 정확도 | **80%** |
| 미거부 사례 | D0301-R02(주식투자), D0301-R03(부동산투자) — "전문가 상담 권합니다" 응답 |

**분석**: 영어 거부 응답 "Sorry, this question is outside Bizi support scope."로 8건 정확 거부.
D0301-R02, R03은 finance_tax 도메인으로 잘못 라우팅되어 비도메인 질문에 답변 제공.

---

## 4. 타임아웃 분석

| 질문 ID | 도메인 | 원인 |
|---------|--------|------|
| D0301-S01 | startup | 300s 타임아웃 |
| D0301-S02 | startup | 300s 타임아웃 |

---

## 5. State C 대비 비교

| 메트릭 | State C | State D | 변화 |
|--------|---------|---------|------|
| Faithfulness | 0.6834 | 0.6192 | **-0.0642** |
| Answer Relevancy | 0.7766 | 0.7302 | **-0.0464** |
| Context Precision | 0.7269 | 0.6660 | **-0.0609** |
| Context Recall | 0.6009 | 0.5884 | -0.0125 |
| Context F1 | 0.6579 | 0.6248 | **-0.0331** |
| 거부 정확도 | 80% | 80% | 0% |

**핵심**: State D는 State C 대비 모든 RAGAS 메트릭이 하락. `vectordb_full.zip`으로의 교체가
오히려 검색 품질 저하를 유발한 것으로 분석됨.

---

## 6. 결과 파일

- Phase 1: `docs/ragas-evaluation/eval_0310/results/answers_state_d.json`
- Phase 2: `docs/ragas-evaluation/eval_0310/results/answers_state_d_evaluated.json`
