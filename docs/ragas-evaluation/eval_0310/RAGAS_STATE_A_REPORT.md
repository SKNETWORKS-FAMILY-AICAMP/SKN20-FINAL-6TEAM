# RAGAS 평가 보고서 — State A (eval_0310)

> **State**: A — 초기 상태
> **Commit**: `f0dc26d`
> **VectorDB**: `vectordb_0130.zip` (chunk_size=800, startup=2,109 / tax=15,196 / hr=8,638 / law=206,854 — 총 213,738건)
> **평가 데이터셋**: `ragas_dataset_0310.jsonl` (80문항)
> **평가일**: 2026-03-10
> **평가 설정**: RAGAS 0.4.3 / gpt-4.1-mini / text-embedding-3-small (AR)
> **특이사항**: 초기 RAG 상태. Hybrid Search, Re-ranking, Query Rewriting 기본 활성화.
>   도메인 분류 버그 수정 적용 (키워드 부스트 임계값 적용 순서 수정).
>   `ENABLE_ACTION_AWARE_GENERATION=false`는 미적용 (State A 원래 설정 사용).

---

## 1. 전체 요약

| 메트릭 | 점수 |
|--------|------|
| **Faithfulness** | **0.4196** |
| **Answer Relevancy** | **0.7354** |
| **Context Precision** | **0.5697** |
| **Context Recall** | **0.3745** |
| **Context F1** | **0.4519** |
| **거부 정확도** | **0.10** (1/10) |
| 유효 응답 | 70/80 |
| 타임아웃 | 0/80 |
| Reject 케이스 | 10/80 |
| 정확 거부 | 1/10 |

> Context F1 = 2 × 0.5697 × 0.3745 / (0.5697 + 0.3745) = **0.4519**

---

## 2. 도메인별 성능

| 도메인 | N | Faithfulness | AR | CP | CR |
|--------|---|-------------|-----|-----|-----|
| startup_funding | 40 | 0.4236 | 0.7550 | 0.4599 | 0.3844 |
| finance_tax | 13 | 0.3484 | 0.7112 | 0.6201 | 0.2782 |
| hr_labor | 17 | 0.4643 | 0.7080 | 0.7893 | 0.4249 |

> 법률(law) 도메인은 routing 결과에 따라 startup/hr로 분류됨 (State A는 별도 law 에이전트 없음)

---

## 3. 거부 정확도 분석

| 항목 | 결과 |
|------|------|
| Reject 질문 수 | 10 |
| 정확 거부 수 | 1 |
| 거부 정확도 | 10% |
| 미거부 사례 | 9건 (주식투자, 부동산, 여행, 레시피, 코딩, 마라톤, 반려견 등) |
| 정확 거부 사례 | Q55 (대학 수시 자기소개서) |

**분석**: State A의 도메인 거부 로직은 `ENABLE_DOMAIN_REJECTION=true` 기본값으로 활성화되어 있으나,
벡터 기반 도메인 분류의 임계값 설정과 키워드 매칭 한계로 대부분의 비도메인 질문을 업무 관련으로 분류함.
도메인 분류 버그 수정 후에도 거부 정확도가 10%에 그친 것은 State A 벡터DB의 낮은 도메인 특이성에 기인.

---

## 4. eval_0301 대비 비교

| 메트릭 | eval_0301 (State A) | eval_0310 (State A) | 변화 |
|--------|---------------------|---------------------|------|
| Faithfulness | 0.3562 | 0.4196 | **+0.0634** |
| Answer Relevancy | 0.6082 | 0.7354 | **+0.1272** |
| Context Precision | 0.4560 | 0.5697 | **+0.1137** |
| Context Recall | 0.2866 | 0.3745 | **+0.0879** |
| 거부 정확도 | 0.0% | 10.0% | +10.0% |

**개선 원인 분석**:
- **데이터셋 개선**: ground_truth 마크다운 헤더 제거, VectorDB 100% 정합성 확인
- **프롬프트 개선**: 한국어 NLI 프롬프트 (의역/동의어 허용), noncommittal 면책 예외 처리
- **평가 스크립트**: `strip_system_artifacts()` 적용 (인용 마커/경고 문구 제거)

---

## 5. 주요 특징 및 한계

**강점**:
- Answer Relevancy가 비교적 높음 (0.7354) — 질문과 관련된 답변 생성
- hr_labor 도메인 CP가 높음 (0.7893) — 관련 문서 정확 검색

**한계**:
- Faithfulness 낮음 (0.4196) — 컨텍스트 기반 답변 충실도 부족 (작은 chunk_size=800)
- Context Recall 낮음 (0.3745) — ground_truth 내용을 충분히 커버하지 못함
- 거부 정확도 10% — 비도메인 질문 거부 실패
- finance_tax Faithfulness 가장 낮음 (0.3484) — 세무 데이터 문서 분할 방식 한계

---

## 6. 결과 파일

- Phase 1: `docs/ragas-evaluation/eval_0310/results/answers_state_a.json`
- Phase 2: `docs/ragas-evaluation/eval_0310/results/answers_state_a_evaluated.json`
