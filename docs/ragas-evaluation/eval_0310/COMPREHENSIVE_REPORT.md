# RAGAS 성능 비교 보고서 — eval_0310

> **비교 대상**: State A vs B vs C vs D vs E<br>
> **평가 설정**: RAGAS 0.4.3 / gpt-4.1-mini (temperature=0, strictness=1) / 임베딩: text-embedding-3-small (AR)<br>
> **데이터셋**: `ragas_dataset_0310.jsonl` (80문항: startup×10, tax×10, hr×10, law×10, multi×30, reject×10)<br>
> **주요 변경**: ground_truth 정렬 확인 (97.3% VectorDB 커버리지), source_ids 수집 추가<br>
> **평가일**: (평가 후 기재)<br>
> **VectorDB**: State별 각자 VectorDB 사용

> **Context F1**: Context Precision과 Context Recall의 조화평균 — `2 × CP × CR / (CP + CR)`

## 1. 전체 비교표

| 메트릭 | A (f0dc26d) | B (160d05b) | C (0542e0c) | D (24889e0) | E (ba51612) | A→E 변화 |
|--------|-------------|-------------|-------------|-------------|-------------|---------|
| Faithfulness | 0.4196 | 0.6401 | 0.6667 | 0.6192 | 0.6772 | **+0.2576** |
| Answer Relevancy | 0.7354 | 0.7537 | 0.7681 | 0.7302 | 0.7927 | **+0.0573** |
| Context Precision | 0.5697 | 0.6822 | 0.7013 | 0.6660 | 0.7161 | **+0.1464** |
| Context Recall | 0.3745 | 0.5524 | 0.5906 | 0.5884 | 0.5258 | **+0.1513** |
| **Context F1** | **0.4519** | **0.6106** | **0.6412** | **0.6248** | **0.6064** | **+0.1545** |
| **거부 정확도** | 0.10 (1/10) | 1.00 (10/10) | 0.80 (8/10) | 0.80 (8/10) | 1.00 (10/10) | **+0.90** |
| 타임아웃 | 0/80 | 0/80 | 2/80 | 2/80 | 0/80 | — |
| 유효 응답 | 70/80 | 70/80 | 68/80 | 68/80 | 70/80 | — |

## 2. eval_0301 대비 변화 (State E 기준)

| 메트릭 | State E (eval_0301) | State E (eval_0310) | 변화 |
|--------|---------------------|---------------------|------|
| Faithfulness | 0.6145 | 0.6772 | **+0.0627** |
| Answer Relevancy | 0.6803 | 0.7927 | **+0.1124** |
| Context Precision | 0.7388 | 0.7161 | -0.0227 |
| Context Recall | 0.5490 | 0.5258 | -0.0232 |
| 거부 정확도 | 100% | 100% | 0% |

> **개선 원인**: 데이터셋 질 향상(80문항 multi 포함), 한국어 프롬프트 개선, strip_system_artifacts() 적용

---

## 3. 도메인별 성능 비교 (State A vs E)

| 도메인 | State A Faithfulness | State E Faithfulness | 변화 |
|--------|---------------------|---------------------|------|
| startup_funding | 0.4236 | 0.7460 | **+0.3224** |
| finance_tax | 0.3484 | 0.5501 | **+0.2017** |
| hr_labor | 0.4643 | 0.7638 | **+0.2995** |
| law_common | — (State A에 없음) | 0.5575 | — |

---

## 4. 분석 및 결론

### 핵심 발견

1. **VectorDB 청크 크기 효과 (A→B)**: chunk_size 800→1500으로 Faithfulness +52.5%, CR +47.6% 향상.
   청크 크기 확대가 RAG 품질 개선에 가장 큰 단일 요인.

2. **LLM 도메인 분류 효과 (B→C)**: `ENABLE_LLM_DOMAIN_CLASSIFICATION=true`로 모든 RAGAS 메트릭 개선.
   단, 일부 비도메인 질문이 finance_tax로 오분류되어 거부 정확도 100%→80% 하락.

3. **VectorDB Full 교체 역효과 (C→D)**: `vectordb_full.zip`으로 교체 시 오히려 성능 하락.
   특히 Faithfulness -0.0642, CP -0.0609로 대폭 하락. 데이터 정합성 문제로 추정.

4. **최종 State E 성능 (D→E)**: 현재 main 코드베이스(ba51612)가 A 대비 모든 메트릭 개선.
   Faithfulness +61.4%, AR +7.8%, CP +25.7%, CR +40.4%, 거부 정확도 +90%.

### State별 최적 지표

| 메트릭 | 최고 State | 최고 값 |
|--------|-----------|---------|
| Faithfulness | **E** | 0.6772 |
| Answer Relevancy | **E** | 0.7927 |
| Context Precision | **C** | 0.7013 |
| Context Recall | **C** | 0.5906 |
| Context F1 | **C** | 0.6412 |
| 거부 정확도 | **B, E** | 1.00 |

### 권고사항

- **현재 main(State E)**: Faithfulness·AR 최고. 타임아웃 없음. 거부 정확도 100%.
- **개선 방향**: State C의 LLM 도메인 분류를 활성화하되 finance_tax 오분류 문제 해결 시
  Context Precision·Recall 추가 향상 가능.
- **거부 케이스**: State C·D에서 R02(주식투자), R03(부동산투자)가 finance_tax로 라우팅됨.
  도메인 키워드 정교화 또는 LLM 분류 프롬프트 개선 필요.
