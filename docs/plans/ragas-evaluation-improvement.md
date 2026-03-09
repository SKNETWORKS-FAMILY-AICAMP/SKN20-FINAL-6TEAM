# RAGAS 평가방식 검증 보고서

> 현재 Bizi 프로젝트의 RAGAS 평가가 적합한지, 인위적 점수 하락 요인이 있는지, 유사도 기반 평가의 의미를 분석합니다.
> 검증 기준: RAGAS 공식 문서(docs.ragas.io), GitHub 소스코드, 현재 코드베이스 (2026-03-09)

---

## 1. 현재 평가방식이 프로젝트 응답 평가에 적합한가?

### 결론: 부분적으로 적합하나, 구조적 불일치로 절대 점수를 품질 지표로 신뢰하기 어렵다.

**적합한 부분:**
- **Faithfulness** — 시스템 프롬프트가 "참고 자료에 있는 내용만 사용"을 요구하므로, 답변이 컨텍스트에 근거하는지 측정하는 것은 타당
- **Context Precision** — 검색된 문서의 관련성/순위를 측정, 검색 품질 반영에 적합

**구조적 문제:**

### 문제 A: Ground Truth가 코퍼스와 독립적
- `ground_truth`가 VectorDB 내용과 무관하게 전문가 이상 답변으로 작성됨
- 특정 URL(www.ftc.go.kr), 정확한 금액(1억 400만원), 기관명(한국식품안전관리인증원) 등 VectorDB에 없는 정보 다수 참조
- **Context Recall이 구조적으로 상한이 제한됨** — D0301-S08(벤처기업 인증)은 State A~E 모두 CR=0.0, 코퍼스에 해당 정보 자체가 없음
- 이것이 Context Recall 평균 0.5490의 근본 원인

### 문제 B: 평가-생성 비대칭 (해결됨)
- 시스템이 주입한 아티팩트(`[번호]` 인용, 면책 문구, 인용 감사 경고)가 RAGAS 평가에 노이즈 유발
- **현재 대응**: `strip_system_artifacts()`(`ragas_evaluator.py:20-47`)가 배치 평가(`__main__.py:240`)와 실시간 단건 평가(`ragas_evaluator.py:380`, `ragas_evaluator.py:557`) 모두에서 아티팩트 제거 적용
- `__init__.py`에서 `strip_system_artifacts` export 추가됨

---

## 2. 한글 이슈/프롬프트 내용/하드코딩이 점수를 낮추는가?

### 결론: 일부 메커니즘이 인위적 점수 하락을 유발하며, 주요 항목은 이미 대응 완료됨.

### 메커니즘 1: `[번호]` 인용 마커 오염 (배치+실시간 평가에서 해결됨)
- **원인**: `prompts.py:140` — "모든 사실적 문장에 [번호] 출처를 표기하세요"
- **Faithfulness 영향**: NLI 분해 시 "출처 [1]에 따르면..." 같은 진술문 생성 → 컨텍스트에 인용 마커 없으므로 검증 불가로 판정
- **Answer Relevancy 영향**: 인용 마커 포함 답변에서 역질문 생성 시 원래 질문과 유사도 저하
- **현재 대응**: `strip_system_artifacts()`(`ragas_evaluator.py:20-47`)가 `[번호]` 마커, 인용 경고, 참고자료 꼬리말 제거 — 배치 및 실시간 평가 모두 적용

### 메커니즘 2: "제공된 자료에서 확인할 수 없습니다" 면책 문구 (대응 완료)
- **원인**: `prompts.py:112,126` — 정보 부재 시 명시하라는 지시
- **Faithfulness**: 메타 진술문(정보 부재에 대한 진술)이 컨텍스트에서 추론 불가
- **Answer Relevancy**: RAGAS의 noncommittal 감지가 질문별 이진 판정(0 or 1) — noncommittal=1이면 해당 역질문의 cosine score가 0으로 처리, 최종 점수는 N개 역질문의 평균
- **현재 대응**: `KoreanResponseRelevancePrompt`(`ragas_evaluator.py:80-115`)에 "구체적인 답변을 제공하면서 일부 항목에 대해 '제공된 자료에서 확인할 수 없습니다'라고 명시하는 것은 정직한 답변이므로 noncommittal이 아닙니다(0으로 설정)"라는 지시 포함
- **검증 도구**: `noncommittal_verify.py`로 LLM 준수율을 검증할 수 있음

### 메커니즘 3: 인용 감사 경고 문구 (배치+실시간 평가에서 해결됨)
- **원인**: `generator.py:212` — `"주의: 이 답변은 참고 자료 인용이 누락되었을 수 있습니다."`
- 문서가 제공되었는데 `[번호]` 인용이 없으면 답변 끝에 추가됨
- 이 경고에서 생성된 역질문은 원래 질문과 무관 → AR=0.0 케이스의 주요 원인
- **현재 대응**: `strip_system_artifacts()`가 이 경고 문구를 제거

### 메커니즘 4: 한국어 NLI에서 gpt-4o-mini의 한계
- `KoreanNLIStatementPrompt`에 3개 예시 제공 (퇴직금 의역, R&D 세액공제 동의어, 부가세 매입세액 과일반화 — `ragas_evaluator.py:135-207`)
- 예시가 다양하나, 법률 분야의 미묘한 의역/수치 판정에서 gpt-4o-mini의 한국어 법률 추론 능력 한계 존재
- 특히 "계속근로기간 1년에 대하여 30일분 이상의 평균임금" 같은 표현의 의역 판정이 불안정

### 메커니즘 5: text-embedding-3-large의 한국어 한계
- Answer Relevancy가 `text-embedding-3-large`(`settings.py:432`)로 코사인 유사도 계산
- `text-embedding-3-large`(3072차원)는 `text-embedding-3-small`(1536차원) 대비 한국어 성능이 개선되었으나, 한국어 전용 모델(BAAI/bge-m3 등) 대비 여전히 한계 존재
- `ragas_embedding_provider=local` 설정(`settings.py:434-446`, `ragas_evaluator.py:234-259`)으로 bge-m3를 AR 임베딩에 사용 가능
- 한국어 법률/비즈니스 용어("원천징수", "가맹사업법")가 영어 대비 임베딩 공간에서 상대적으로 희소
- 동일 의미의 두 한국어 질문이 영어 대비 체계적으로 낮은 유사도 (정확한 수치 차이는 실증 검증 필요)

### 인위적 하락 추정치

| 메트릭 | 보고 점수 (State E) | 추정 실제 범위 | 주요 하락 원인 |
|--------|---------------------|---------------|---------------|
| Faithfulness | 0.6145 | 0.65~0.75 | 면책 문구 메타진술, 한국어 NLI 한계 |
| Answer Relevancy | 0.6803 | 0.72~0.82 | noncommittal 잔여 오판, 임베딩 한계 |
| Context Precision | 0.7388 | 0.74~0.78 | 최소 하락 (답변 비의존적) |
| Context Recall | 0.5490 | **구조적 상한** | ground_truth-코퍼스 불일치 |

> Note: `--compare` 플래그(`__main__.py:405-409`)를 사용하면 아티팩트 제거 전/후 점수를 동시에 측정하여 정확한 하락 폭을 정량화할 수 있음.
> 위 추정치는 아티팩트 제거 적용 전(State E) 기준. `--compare` 재평가 데이터 필요.

---

## 3. 생성 응답과 검색 문서의 키워드/유사도 비교의 의미

### RAGAS Answer Relevancy의 실제 동작 방식

RAGAS AR은 **키워드 비교가 아니라 역질문 생성 + 임베딩 유사도** 방식:
1. 생성된 답변에서 LLM이 N개(strictness=3, `ragas_evaluator.py:212`) 역질문 생성
2. 원래 질문과 각 역질문을 `text-embedding-3-large`(`settings.py:432`)로 임베딩
3. 코사인 유사도 계산
4. **noncommittal 판정**: 각 역질문별로 이진 판정(0 or 1) — noncommittal=1이면 해당 질문의 cosine score를 0으로 처리, 최종 점수는 N개의 평균 (RAGAS 소스: `_answer_relevance.py`)

### 한국어 법률/비즈니스 텍스트에서의 잔여 문제점

**A. 한국어 임베딩 성능**: `text-embedding-3-large`(3072차원)는 MIRACL 벤치마크 기준 다국어 성능 개선이 있으나, 한국어 전용 모델(bge-m3, ko-sbert) 대비 한국어 의미 유사도 정밀도가 낮을 수 있음

**B. 법률 동의어 발산**: "간이과세자" vs "소규모 사업자 세금 유형" — 같은 개념이지만 임베딩 거리 큼

**C. 답변→질문 정보 손실**: 고도로 구체적인 법률 답변("근로기준법 제34조에 따라...")에서 생성되는 역질문이 지나치게 넓거나("퇴직금이란?") 지나치게 좁아("근로기준법 제34조의 퇴직금 산정 기준은?") 원래 질문과 거리 발생

**D. noncommittal 잔여 오판**: `KoreanResponseRelevancePrompt`에서 면책 문구를 noncommittal=0으로 판정하도록 지시했으나, gpt-4o-mini가 항상 준수하는지 미검증. 5개 요청 중 2개만 답변 가능하고 3개를 정직하게 "확인 불가"라고 한 응답이 여전히 저품질로 평가될 가능성 있음

### contextual_metrics가 더 적합한 보완 지표
`contextual_metrics.py`의 결정론적 키워드 체크(directive_coverage, context_adherence, conflict_free)가 한국어 편향 없이 더 신뢰할 수 있는 보완 지표

---

## 이미 완료된 개선사항

| # | 항목 | 파일 | 상태 |
|---|------|------|------|
| 1 | 배치 평가에 답변/컨텍스트 저장 | `__main__.py:364-377` | **완료** — `answer`, `contexts` 모두 JSON 출력에 포함 |
| 2 | 시스템 아티팩트 제거 함수 | `ragas_evaluator.py:20-47` | **완료** — `__main__.py`에서 `ragas_evaluator.py`로 이동 |
| 3 | AR 임베딩 `text-embedding-3-large` 기본값 | `settings.py:432` | **완료** |
| 4 | noncommittal 면책 문구 예외 프롬프트 | `ragas_evaluator.py:80-115` | **완료** |
| 5 | NLI 예시 3개 확장 | `ragas_evaluator.py:135-207` | **완료** — 퇴직금/R&D/부가세 3개 예시 |
| 6 | 아티팩트 제거 전/후 비교 모드 | `__main__.py:251-258, 405-409` | **완료** — `--compare` 플래그 |
| 7 | 실시간 평가에도 아티팩트 제거 | `ragas_evaluator.py:380, 557` | **완료** — `evaluate_single`, `evaluate_answer_quality` |
| 8 | AR 임베딩 local/openai 선택 | `settings.py:434-446`, `ragas_evaluator.py:234-259` | **완료** — `ragas_embedding_provider` 설정 |
| 9 | noncommittal 준수율 검증 도구 | `evaluation/noncommittal_verify.py` | **완료** — 신규 파일 |
| 10 | ground_truth 코퍼스 정렬 진단 도구 | `evaluation/ground_truth_alignment.py` | **완료** — 신규 파일 |

## 남은 개선 권고사항

### HIGH (점수 정확도 직결)

| # | 항목 | 설명 |
|---|------|------|
| 1 | **ground_truth를 코퍼스와 정렬** | 진단 도구(`ground_truth_alignment.py`)는 완료. **실제 데이터셋 정렬 작업은 미완** — CR 0.5490의 근본 원인 |

### LOW (장기)

| # | 항목 | 설명 |
|---|------|------|
| 2 | Faithfulness LLM을 gpt-4o로 교체 | 한국어 법률 NLI 정확도 향상 |
| 3 | 도메인 전문가 human evaluation | RAGAS vs 전문가 평가 캘리브레이션 |

---

## 핵심 파일

- `rag/evaluation/ragas_evaluator.py` — RAGAS 메트릭 설정, 한국어 프롬프트(80-207행), 임베딩 모델(234-259행), 아티팩트 제거(20-47행)
- `rag/evaluation/__main__.py` — 배치 평가 러너, 아티팩트 제거 적용(240행), 비교 모드(251-258행), 결과 저장(364-377행)
- `rag/evaluation/__init__.py` — `strip_system_artifacts` export 포함
- `rag/evaluation/ground_truth_alignment.py` — ground_truth-VectorDB 정렬 진단 CLI 도구
- `rag/evaluation/noncommittal_verify.py` — noncommittal 판정 준수율 검증 CLI 도구
- `rag/utils/prompts.py` — 인용 지시(140행), 면책 문구(112,126행)
- `rag/agents/generator.py` — `_audit_citations()` 경고 문구(212행)
- `rag/utils/config/settings.py` — RAGAS 설정(431-446행: LLM/임베딩/provider)
- `docs/ragas-evaluation/eval_0301/ragas_dataset_0301.jsonl` — ground_truth 데이터셋
