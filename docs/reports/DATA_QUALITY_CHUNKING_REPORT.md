# RAG 데이터 품질 + 청킹 전략 개선 작업 보고서

> 작업일: 2026-02-25

---

## 배경

RAG 평가(RAGAS) 결과 검색 품질이 기대 이하로, 코드 수정 전에 **데이터 자체의 품질 문제**를 먼저 해결하기로 방향을 전환했습니다.

분석 결과 4가지 핵심 이슈를 발견하여 수정했습니다.

---

## 변경 1: JSONL 데이터 정제

**스크립트**: `scripts/preprocessing/clean_jsonl.py` (신규, ~200줄)

### 1-1. domain 필드 정규화

크로스도메인 리랭킹에서 `DOMAIN_LABELS` 키와 불일치하는 domain 값을 정규화했습니다.

| 파일 | 변경 전 | 변경 후 | 건수 |
|------|--------|--------|------|
| `announcements.jsonl` | `funding` | `startup_funding` | 510 |
| `industry_startup_guide_filtered.jsonl` | `startup` | `startup_funding` | 1,589 |
| `startup_procedures_filtered.jsonl` | `startup` | `startup_funding` | 10 |
| `labor_interpretation.jsonl` | `labor` | `hr_labor` | 399 |

### 1-2. type 필드 정규화

| 파일 | 변경 전 | 변경 후 | 건수 |
|------|--------|--------|------|
| `labor_interpretation.jsonl` | `labor` | `interpretation` | 399 |

### 1-3. 불필요 메타데이터 제거

전처리/PDF 잔여물로 RAG 검색에 무의미한 필드를 제거했습니다.

| 파일 | 제거 키 | 건수 |
|------|--------|------|
| `laws_full.jsonl` | `filter_method`, `filter_reason` | 4,528 × 2 = 9,056 |
| `interpretations.jsonl` | `filter_method`, `filter_reason` | 4,421 × 2 = 8,842 |
| `tax_support.jsonl` | `page` | 134 |
| `hr_insurance_edu.jsonl` | `page_range` | 89 |
| `labor_interpretation.jsonl` | `qa_count` | 399 |

### 1-4. HTML 잔재 정리

court_cases의 `metadata.reference` 필드에 남아있던 HTML 태그를 정리했습니다.

| 파일 | 처리 | 건수 |
|------|------|------|
| `court_cases_tax.jsonl` | `<br/>` → `\n`, 태그 제거 | 1,458 / 1,949 |
| `court_cases_labor.jsonl` | `<br/>` → `\n`, 태그 제거 | 732 / 981 |

### 스크립트 사용법

```bash
py scripts/preprocessing/clean_jsonl.py --dry-run      # 변경 사항만 리포트
py scripts/preprocessing/clean_jsonl.py                 # 실행 (원본 .bak 백업)
py scripts/preprocessing/clean_jsonl.py --no-backup     # 백업 없이 실행
```

---

## 변경 2: DATA_SOURCES 경로 수정

**파일**: `rag/vectorstores/config.py` (line 41)

실제 디렉토리 이름과 불일치하는 경로를 수정했습니다.

```python
# Before
"finance_tax": DATA_PREPROCESSED_DIR / "finance_tax",
# After
"finance_tax": DATA_PREPROCESSED_DIR / "tax",
```

실제 디렉토리 구조:
```
data/preprocessed/
├── startup_support/   ← startup_funding 매핑 (정상)
├── tax/               ← finance_tax 매핑 (수정됨)
├── hr_labor/          ← hr_labor 매핑 (정상)
└── law_common/        ← law_common 매핑 (정상)
```

---

## 변경 3: 청킹 파라미터 조정

**파일**: `rag/vectorstores/config.py`

### 3-1. OPTIONAL_CHUNK_THRESHOLD 하향

```python
# Before
OPTIONAL_CHUNK_THRESHOLD = 3500
# After
OPTIONAL_CHUNK_THRESHOLD = 2500
```

**근거**: interpretations 평균 3,809자 기준, 3500 임계값에서는 52%만 청킹 대상이었으나, 2500으로 낮추면 ~78%가 청킹 대상이 됩니다.

### 3-2. FILE_CHUNKING_CONFIG 파라미터

| 파일 | chunk_size | chunk_overlap | 변경 내용 |
|------|-----------|--------------|----------|
| `laws_full.jsonl` | 2000 → **1500** | 200 → **250** | 정밀도↑, 컨텍스트 보존↑ |
| `interpretations.jsonl` | 2000 → **1500** | 200 → **250** | 동일 |
| `court_cases_tax.jsonl` | 1500 (유지) | 150 → **200** | overlap↑ |
| `court_cases_labor.jsonl` | 1500 (유지) | 150 → **200** | overlap↑ |
| `labor_interpretation.jsonl` | 1500 (유지) | 150 → **200** | overlap↑ |
| `hr_insurance_edu.jsonl` | 1500 (유지) | 150 → **200** | overlap↑ |
| `tax_support.jsonl` | 1500 (유지) | 150 → **200** | overlap↑ |

**chunk_size 1500 근거**: bge-m3 8,192 토큰 한도, 1500자 ≈ 1,050 토큰 (~13%). 검색 정밀도와 문맥 보존 최적 구간.

**overlap 200-250 근거**: 법률/세무 문서에 15~17% overlap 권장 (기존 10%에서 향상).

---

## 변경 파일 요약

| # | 파일 | 작업 | 비고 |
|---|------|------|------|
| 1 | `scripts/preprocessing/clean_jsonl.py` | **신규** | 데이터 정제 스크립트 |
| 2 | `rag/vectorstores/config.py` | **수정** | DATA_SOURCES + 청킹 파라미터 |
| 3 | `data/preprocessed/**/*.jsonl` | **정제** | 10개 파일 (원본 .bak 백업됨) |

RAG 파이프라인 코드(agents, chains, routes) 변경 **없음**.

---

## 검증 결과

### domain 값 (정제 후)

```
court_cases_labor.jsonl:                {'hr_labor'}
hr_insurance_edu.jsonl:                 {'hr_labor'}
labor_interpretation.jsonl:             {'hr_labor'}
interpretations.jsonl:                  {'finance_tax', 'startup_funding', 'hr_labor', 'general'}
laws_full.jsonl:                        {'finance_tax', 'startup_funding', 'hr_labor', 'general'}
announcements.jsonl:                    {'startup_funding'}
industry_startup_guide_filtered.jsonl:  {'startup_funding'}
startup_procedures_filtered.jsonl:      {'startup_funding'}
court_cases_tax.jsonl:                  {'finance_tax'}
tax_support.jsonl:                      {'finance_tax'}
```

모든 domain 값이 `DOMAIN_LABELS` 키(`startup_funding`, `finance_tax`, `hr_labor`, `general`)와 일치합니다.

### 메타데이터 정리 확인

- `laws_full.jsonl`: `filter_method`, `filter_reason` 제거 확인
- `tax_support.jsonl`: `page` 제거 확인
- `hr_insurance_edu.jsonl`: `page_range` 제거 확인
- `labor_interpretation.jsonl`: `qa_count` 제거, domain=`hr_labor`, type=`interpretation` 확인

### HTML 정리 확인

- `court_cases_tax.jsonl`: HTML 잔재 0건
- `court_cases_labor.jsonl`: HTML 잔재 0건

---

## 후속 작업

- [ ] **VectorDB 재빌드** — 데이터가 정제되었으므로 벡터 인덱스를 다시 빌드해야 변경 사항이 검색에 반영됩니다
- [ ] **RAGAS 재평가** — 재빌드 후 검색 품질 변화 측정
- [ ] `.bak` 백업 파일 정리 (검증 완료 후)
