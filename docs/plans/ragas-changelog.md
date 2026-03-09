# RAGAS 코드 Simplify 로그

> **주의**: 이 문서의 판정과 근거는 당시 분석 기준이며 정답이 아닙니다.
> 더 나은 방향이 발견되면 기존 판정을 번복할 수 있으므로, 새로운 변경 시 반드시 사용자에게 근거를 설명하고 승인을 받아야 합니다.
>
> **알려진 미검증 사항:**
> - ~~`_CITATION_MARKER_RE` 오탐 위험~~ → 해결됨 (2026-03-10, negative lookahead 적용)
> - `ragas_embedding_provider=local` (bge-m3) vs `openai` (text-embedding-3-large)의 AR 점수 비교가 미실측 — `--compare` 플래그로 검증 가능한 상태이나 데이터 미확보

## 2026-03-10 — `_CITATION_MARKER_RE` 정밀화 + 임베딩 비교 검증 가이드

### 수정 항목

| # | 파일 | 내용 |
|---|------|------|
| 1 | `rag/evaluation/ragas_evaluator.py` | `_CITATION_MARKER_RE`에 negative lookahead 추가: `r"\s*\[\d+\]"` → `r"\s*\[\d+\](?![가-힣a-zA-Z0-9])"` — `[1]항`, `[3]억원` 같은 법률/금액 표현 보존, 인용 마커(`[1]`, `[1] 참고`, `[1],`)는 정상 제거 |

### 미실측 검증 가이드 (임베딩 provider 비교)

`ragas_embedding_provider=local` (bge-m3) vs `openai` (text-embedding-3-large) AR 점수 비교를 위한 실행 절차:

```bash
# 1) OpenAI 임베딩으로 평가
cd rag
RAGAS_EMBEDDING_PROVIDER=openai python -m evaluation -d eval_0301/ragas_dataset_0301.jsonl -o results/ar_openai.json

# 2) 로컬 bge-m3로 평가
RAGAS_EMBEDDING_PROVIDER=local python -m evaluation -d eval_0301/ragas_dataset_0301.jsonl -o results/ar_local.json

# 3) results_analyzer로 비교
python -m evaluation.results_analyzer --files results/ar_openai.json results/ar_local.json
```

결과에 따라 `ragas_embedding_provider` 기본값(`openai`) 변경 여부를 판단할 것.

## 2026-03-09 22:22 — 코드 리뷰 및 정리

3개 병렬 리뷰 에이전트(Reuse / Quality / Efficiency) 실행 후 발견사항 수정.

### 수정 항목

| # | 파일 | 내용 |
|---|------|------|
| 1 | `rag/utils/config/settings.py` | `ragas_embedding_provider`에 `@field_validator` 추가 — `"openai"` / `"local"` 외 값 입력 시 조용히 무시되던 문제. 기존 `embedding_provider`, `reranker_type`과 동일 패턴 적용 |
| 2 | `rag/evaluation/ragas_evaluator.py` | `evaluate_batch`에서 `_skip_strip` 해킹 파라미터 제거 — 호출자(`__main__.py`)가 직접 `strip_system_artifacts()`를 적용하도록 변경. API 단순화 및 `evaluate`/`evaluate_batch`/`quick_evaluate` 간 일관성 확보 |
| 3 | `rag/evaluation/__main__.py` | `all_raw_results`를 `compare=False`일 때 `None`으로 초기화 — 불필요한 리스트 할당/추가 제거. `delta_averages` 이중 초기화(dead code) 제거 |
| 4 | `rag/evaluation/ragas_evaluator.py` | `_get_langchain_embeddings` bare except에 `exc_info=True` 추가 — 임베딩 초기화 실패 시 에러 상세 로깅 |

### 스킵 항목 (false positive 또는 불필요)

| 항목 | 사유 |
|------|------|
| 참고자료 regex 중복 (`generator.py` vs `ragas_evaluator.py`) | 서로 다른 용도 (생성 vs 제거), 분리 유지가 적절 |
| `DOMAIN_COLLECTION_MAP` 중복 (`ground_truth_alignment.py`) | 독립 CLI 도구의 short alias 매핑, 기존 `COLLECTION_NAMES`와 구조 상이 |
| `noncommittal_verify.py` 프롬프트 중복 | RAGAS 내부 클래스에 import 의존하면 더 취약 |
| JSONL 로딩 중복 (`__main__.py` vs `ground_truth_alignment.py`) | 4줄 수준의 trivial 패턴, 공유 유틸리티 과잉 |
| N+1 벡터 검색 (`ground_truth_alignment.py`) | CLI 진단 도구, hot path 아님 |
| 순차 API 호출 (`noncommittal_verify.py`) | CLI 진단 도구, 36회 호출 ~10-20초 수준 |
| `line = line.strip()` 변수 섀도잉 | Python 일반 관용구, 실제 버그 아님 |

## 2026-03-09 — 메트릭 집계 중복 제거 및 import 정리

대상 파일: `rag/evaluation/__main__.py`

### 수정 항목

| # | 내용 | 근거 |
|---|------|------|
| 1 | `strip_system_artifacts`, `RagasMetrics` late import(line 223, 245) → 파일 상단 import 섹션으로 이동 | 두 심볼 모두 `evaluation.ragas_evaluator`에서 가져오며, 같은 모듈의 `RagasEvaluator`는 이미 상단에서 import 중. `__init__.py`에서도 동일 모듈을 import하므로 순환 참조 위험 없음. 함수 내부 산재 import는 가독성을 낮추고 의존 관계 파악을 어렵게 함 |
| 2 | `_collect_metric_values(results, timeout_flags, metric_keys)` 헬퍼 함수 추출 | cleaned 메트릭 집계(기존 line 282-304)와 raw 메트릭 집계(기존 line 312-321)가 동일 로직(timeout 스킵 → `metrics.available` 확인 → `getattr`로 값 수집) 중복. 헬퍼로 추출하여 각각 1줄 호출로 대체, ~20줄 중복 제거 |

## 2026-03-09 — settings 복원 try/finally 통합

대상 파일: `rag/evaluation/__main__.py`

### 변경 근거

`run_batch_evaluation()`에서 settings 4개 플래그(`enable_ragas_evaluation`, `enable_llm_evaluation`, `enable_post_eval_retry`, `enable_graduated_retry`)를 함수 진입 시 저장하고, 종료 시 복원하는 코드가 2곳(조기반환 line 228-232 + 정상종료 line 387-391)에 중복되어 있었음. 이 구조는 두 가지 문제를 가짐:

1. **예외 안전성 부재** — `vector_store` 생성 이후 본문에서 예외 발생 시 settings가 복원되지 않고 변경된 상태로 남음
2. **유지보수 부담** — 새 반환 경로 추가 시 복원 코드를 빠뜨릴 위험

### 수정 항목

| # | 내용 | 근거 |
|---|------|------|
| 1 | `vector_store = ChromaVectorStore()` 이후 본문 전체를 `try/finally`로 감싸기 | 모든 반환 경로(정상, 조기반환, 예외)에서 settings 복원 + `vector_store.close()` 보장 |
| 2 | 기존 복원 코드 2곳 제거 (valid_indices 없을 때 조기반환, 함수 끝) | `finally` 블록이 일괄 처리하므로 중복 제거. 조기반환은 `return`만 남김 |
| 3 | RAGAS 미사용 조기반환(line 117-120) 수동 복원 유지 | `vector_store` 생성 전이므로 `try` 바깥 — `enable_ragas_evaluation` 1개만 복원하면 충분 |

## 2026-03-09 — metric_keys 상수 중앙화

### 변경 근거

`["faithfulness", "answer_relevancy", "context_precision", "context_recall"]` 메트릭 키 목록이 2곳에서 독립적으로 하드코딩되어 있었음:

- `__main__.py:275` — `["faithfulness", "answer_relevancy", "context_precision"]` + 조건부 `context_recall` append
- `results_analyzer.py:23` — `METRIC_KEYS = ["faithfulness", "answer_relevancy", "context_precision", "context_recall"]`

두 목록이 미묘하게 다른 구조(하나는 동적 append, 하나는 정적 리스트)로, 메트릭 추가/변경 시 한쪽만 수정하면 불일치 발생 가능.

### 수정 항목

| # | 파일 | 내용 |
|---|------|------|
| 1 | `rag/evaluation/__init__.py` | `RAGAS_METRIC_KEYS` 상수 정의 및 `__all__` export 추가 |
| 2 | `rag/evaluation/__main__.py` | `RAGAS_METRIC_KEYS` import, 하드코딩 리스트를 리스트 컴프리헨션으로 대체 (`context_recall`은 `has_ground_truth` 조건 유지) |
| 3 | `rag/evaluation/results_analyzer.py` | `RAGAS_METRIC_KEYS` import, 로컬 alias `METRIC_KEYS = RAGAS_METRIC_KEYS`로 기존 참조 6곳 유지 |

### 스킵 항목 (Simplify 리뷰 중 부적합 판정)

| 항목 | 사유 |
|------|------|
| Q1: `strip_system_artifacts` API 일관화 | `evaluate_batch`가 자동 strip하지 않는 것은 의도적 설계 — `--compare` 플래그가 stripped/raw 비교를 위해 호출자 제어 필요 (changelog 첫 번째 섹션 항목 2 참조) |
| R1: `load_test_dataset` 공통 유틸 | 이전 스킵 판정 유지 — trivial 4줄 패턴 |
| R2: `DOMAIN_COLLECTION_MAP` 통합 | 이전 스킵 판정 유지 — 독립 CLI 도구 short alias |
| Q2: noncommittal 프롬프트 중앙화 | 이전 스킵 판정 유지 — RAGAS 내부 클래스 의존 회피 |
| E1: compare 2x 비용 | `--compare`의 목적 자체가 2회 비교 실행 |
| E2, E3: CLI 도구 최적화 | 이전 스킵 판정 유지 — hot path 아님 |
| E4: 임베딩 싱글톤 thread-safety | async 단일 워커 환경에서 문제 없음 |

## 2026-03-09 — 2차 Simplify 리뷰 (고려 후 변경하지 않은 사항)

전체 변경사항에 대해 코드 재사용, 품질, 효율성 관점에서 추가 리뷰 수행.
4건의 개선 제안을 검토한 결과, changelog 및 improvement 보고서의 기존 설계 의도와 대조하여 **모두 변경 불필요**로 판정.

### 검토 항목

| # | 제안 | 검토 결과 | 판정 사유 |
|---|------|----------|----------|
| A | `evaluate_batch`에도 `strip_system_artifacts` 내부 자동 적용하여 `evaluate_single`/`evaluate_answer_quality`와 API 일관화 | **철회 (설계 의도 충돌)** | `--compare` 모드가 동일 `evaluate_batch()`를 cleaned/raw 2회 호출하여 점수 차이를 측정. 내부 자동 strip 시 raw 점수를 얻을 수 없어 비교 기능 파괴. 기존 스킵 판정(Q1) 재확인 |
| B | `_CITATION_MARKER_RE`(`r"\s*\[\d+\]"`)가 인용 마커 외 `[1]항` 등 합법적 패턴까지 제거할 위험 | **변경 불필요 (LOW)** | 실제 답변에서 `[숫자]`는 시스템 주입 인용 마커로만 사용됨. `\s*` prefix가 있어 문장 내 `[3개월]` 같은 패턴은 매칭되지 않음(숫자만 있는 대괄호). 실운영 오탐 사례 미확인 |
| C | `ragas_embedding_model` 기본값이 `text-embedding-3-small` → `text-embedding-3-large`로 변경되어 비용 약 5배 증가 | **변경 불필요 (의도된 변경)** | improvement 보고서 메커니즘 5에서 한국어 AR 정확도를 위해 `large` 선택 근거 제시. RAGAS 평가는 빈번 호출 경로가 아니므로 비용 영향 제한적. 추가로 `ragas_embedding_provider=local` (bge-m3) 옵션으로 비용 회피 가능 |
| D | `noncommittal_verify.py`의 `SYSTEM_PROMPT`가 `ragas_evaluator.py`의 `KoreanResponseRelevancePrompt.instruction`과 내용 중복 — 하나 변경 시 불일치 | **변경 불필요 (의도적 분리)** | 기존 스킵 판정(Q2) 재확인. `KoreanResponseRelevancePrompt`는 ragas 라이브러리 내부 클래스(`ResponseRelevancePrompt`) 상속이므로, 검증 도구에서 import 시 ragas 버전 변경에 취약해짐. 독립 CLI 진단 도구로서 자체 프롬프트 유지가 적절 |

## 2026-03-09 — 3차 Simplify 리뷰 (전체 diff 기반, 변경 없음)

전체 변경 파일 5개 + 신규 파일 2개에 대해 `/simplify` 관점에서 리뷰 수행.
changelog 및 기존 설계 의도와 대조하여 **4건 모두 변경 불필요**로 판정.

### 검토 항목

| # | 제안 | 판정 | 사유 |
|---|------|------|------|
| 1 | `evaluate_batch()`에도 `strip_system_artifacts` 내부 자동 적용하여 `evaluate`/`evaluate_quick`과 API 일관화 | **철회 (설계 의도 충돌)** | `--compare` 모드가 동일 `evaluate_batch()`를 cleaned/raw 2회 호출하여 점수 차이를 측정. 내부 자동 strip 시 raw 점수를 얻을 수 없어 비교 기능 파괴. 기존 Q1 스킵 판정 + 2차 리뷰 항목 A에서 이미 2회 기각 |
| 2 | `run_batch_evaluation` 함수 분리 (~280줄) | **변경 불필요 (과잉)** | `try/finally` 통합 후 단일 흐름. 분리 시 인자 전달 복잡도 증가, 프로젝트 규칙("minimal changes") 위반 |
| 3 | `compare` 모드 `all_raw_results` None/[] 분기 정리 | **이미 적용됨** | 1차 리뷰 항목 3에서 수정 완료 — `compare=False`일 때 `None` 초기화, 불필요한 리스트 할당 제거 |
| 4 | `noncommittal_verify.py`의 `for f in failure_details` — 빌트인 `f` 섀도잉 | **스킵 (관행 허용)** | 기존 스킵 판정(`line = line.strip()` 섀도잉 — Python 일반 관용구, 실제 버그 아님)과 동일 기준 적용 |

## 2026-03-10 — 4차 리뷰: `_CITATION_MARKER_RE` 정밀화 + 임베딩 비교 검증 가이드

4차 `/simplify` 리뷰에서 changelog 전체의 근거 충분성과 방향 적합성을 재검증.
기존 판정 대부분 타당하나, 2차 리뷰 항목 B(`_CITATION_MARKER_RE` 안전성)의 근거가 불충분하다고 판단하여 **기존 "변경 불필요(LOW)" 판정을 번복**, regex를 정밀화함.
또한 improvement 보고서 메커니즘 5(임베딩 provider 비교)의 실측 데이터 부재를 미검증 사항으로 명시.

### 수정 항목

| # | 파일 | 내용 | 변경 근거 |
|---|------|------|-----------|
| 1 | `rag/evaluation/ragas_evaluator.py` | `_CITATION_MARKER_RE`에 negative lookahead 추가: `r"\s*\[\d+\]"` → `r"\s*\[\d+\](?![가-힣a-zA-Z0-9])"` | 2차 리뷰 항목 B를 번복. 기존 근거 "실운영 오탐 사례 미확인"은 사실이나, regex 자체가 `[1]항`, `[3]억원` 같은 법률/금액 표현을 구조적으로 오탐할 수 있음. LLM 출력 형식에 의존하는 "우연한 안전성"이므로, 비용 없이(1줄 변경) 방어적으로 정밀화. 인용 마커(`[1]`, `[1] 참고`, `[1],`)는 정상 제거됨 |

### 2차 리뷰 항목 B 번복 근거 상세

**기존 판정 (2차 리뷰)**: 변경 불필요(LOW) — "실운영 오탐 사례 미확인"

**번복 이유**:

1. **구조적 오탐 가능성**: `r"\s*\[\d+\]"`는 `[숫자]` 뒤에 한글/영문이 바로 오는 경우(`[1]항`, `[3]억원`, `[2]호`)도 매칭함. 이는 프롬프트(`prompts.py:140`)가 `[번호]` 인용을 지시하는 것과 무관한, regex 패턴 자체의 과잉 매칭
2. **우연한 안전성에 의존**: 기존 "오탐 없음"은 LLM이 법조문을 "제1항" 형태로 출력하기 때문이지, regex가 안전하기 때문이 아님. LLM 모델 변경이나 프롬프트 수정 시 `[1]항` 형태가 출력될 가능성 배제 불가
3. **수정 비용 제로**: negative lookahead `(?![가-힣a-zA-Z0-9])` 추가로 기존 동작(인용 마커 제거)은 100% 보존하면서 오탐만 방지. 성능 영향 없음

### 미실측 검증 가이드 (임베딩 provider 비교)

improvement 보고서 메커니즘 5에서 `ragas_embedding_provider=local` (bge-m3) 옵션을 구현했으나,
`openai` (text-embedding-3-large) 대비 AR 점수 비교 데이터가 없어 기본값(`openai`) 선택의 근거가 불충분.
아래 절차로 실측 후 기본값 변경 여부를 판단할 것.

```bash
# 1) OpenAI 임베딩으로 평가
cd rag
RAGAS_EMBEDDING_PROVIDER=openai python -m evaluation -d eval_0301/ragas_dataset_0301.jsonl -o results/ar_openai.json

# 2) 로컬 bge-m3로 평가
RAGAS_EMBEDDING_PROVIDER=local python -m evaluation -d eval_0301/ragas_dataset_0301.jsonl -o results/ar_local.json

# 3) results_analyzer로 비교
python -m evaluation.results_analyzer --files results/ar_openai.json results/ar_local.json
```

## 2026-03-10 — 5차 리뷰: RAGAS 버전 핀 + 프롬프트 fallback 경고 상향

전체 변경사항에 대해 `/simplify` + RAGAS 최신 문서 웹서치 + 실제 설치 버전(0.4.3) 호환성 테스트를 수행.
기존 changelog의 판정 4건을 교차 검증하여 대부분 타당함을 재확인하고, changelog에서 다루지 않았던 **RAGAS 버전 관리** 관점에서 2건의 신규 수정을 적용.

### 교차 검증 결과 (기존 판정 재확인)

| 기존 판정 | 재검증 결과 |
|-----------|------------|
| Q1/A/1: `evaluate_batch` 자동 strip 불필요 | **타당** — `--compare` 설계 의도 충돌. 3회 기각 이력 재확인 |
| B→4차 번복: `_CITATION_MARKER_RE` 정밀화 | **타당** — negative lookahead 적용 완료 |
| C: `text-embedding-3-large` 비용 허용 | **타당** — 웹서치 결과 한국어 다국어 벤치마크에서 large가 80.5% vs small 75.8% 정확도 |
| D/Q2: `noncommittal_verify.py` 프롬프트 독립 유지 | **타당** — RAGAS private API 의존 회피 |

### 호환성 테스트 (ragas 0.4.3, 실제 설치 버전)

프로젝트가 사용하는 모든 RAGAS API 패턴을 ragas 0.4.3에서 직접 테스트:

| 패턴 | 상태 | 비고 |
|------|------|------|
| `from ragas.metrics import faithfulness` 등 4개 | **동작** | `DeprecationWarning: v1.0에서 제거, ragas.metrics.collections 사용 권장` |
| `from ragas.metrics._answer_relevance import ResponseRelevancePrompt` 등 | **동작** | 경고 없음 (private API) |
| `from ragas.metrics._faithfulness import NLIStatementPrompt` 등 | **동작** | 경고 없음 (private API) |
| `answer_relevancy.question_generation = CustomPrompt()` | **동작** | 속성 할당 정상 |
| `faithfulness.nli_statements_prompt = CustomPrompt()` | **동작** | 속성 할당 정상 |
| `ragas.evaluate(dataset=HF_Dataset, metrics=..., llm=..., embeddings=...)` | **동작** | deprecated 아님, `Union[Dataset, EvaluationDataset]` 허용 |
| `from ragas.llms import llm_factory` | **동작** | — |

**Breaking point**: ragas **v1.0**(미출시)에서 `ragas.metrics` import 경로 제거 예정. `ragas.metrics._faithfulness` 등 private API는 명시적 deprecation 없이 변경 가능.

### 수정 항목

| # | 파일 | 내용 | 변경 근거 |
|---|------|------|-----------|
| 1 | `requirements.txt` | `ragas>=0.1.0` → `ragas>=0.4.0,<1.0.0` | 기존 `>=0.1.0`은 사실상 무제한으로, ragas v1.0 설치 시 `from ragas.metrics import faithfulness` 경로 제거 + private API(`_answer_relevance`, `_faithfulness`) 변경으로 한국어 프롬프트 커스터마이징이 **조용히 비활성화**됨. 하한 `>=0.4.0`: 현재 설치 버전(0.4.3)이 정상 동작 확인됨, `llm_factory` 등 0.4 API 사용 중이므로 다운그레이드 방지. 상한 `<1.0.0`: v1.0이 실제 breaking point |
| 2 | `rag/evaluation/ragas_evaluator.py` | 한국어 프롬프트 fallback 로그: `logger.info` → `logger.warning` | 한국어 프롬프트(`KoreanResponseRelevancePrompt`, `KoreanNLIStatementPrompt`, `KoreanStatementGeneratorPrompt`)는 Faithfulness/AR 점수에 핵심적 영향(improvement 보고서 메커니즘 1-4). import 실패 시 영어 기본 프롬프트로 fallback하면 점수 급락하나, 기존 `logger.info`는 기본 로그 레벨(WARNING)에서 출력되지 않아 원인 파악 불가. `_get_langchain_embeddings`에 `exc_info=True` 추가한 것(1차 리뷰 항목 4)과 동일한 "실패 가시성 확보" 맥락 |

### 스킵 항목

| 항목 | 사유 |
|------|------|
| `ragas.metrics` → `ragas.metrics.collections` import 경로 마이그레이션 | v1.0 미출시, 현재 deprecation 단계. 버전 상한(`<1.0.0`)으로 보호되므로 즉시 마이그레이션 불필요 |
| `_CITATION_MARKER_RE` `\s*` 공백 소실 | 4차 리뷰에서 negative lookahead 적용으로 이미 해결. 추가 변경 불필요 |
