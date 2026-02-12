# Bizi RAG 청킹 전략 개선 계획

> **상태**: 코드 구현 완료 (커밋 `ad2053f`)
> **작성일**: 2026-02-12
> **수정 대상**: `vectorstores/config.py`, `vectorstores/loader.py`, `utils/config.py`, `scripts/preprocessing/preprocess_laws.py`

---

## 1. 배경 및 목표

Bizi RAG 시스템은 4개 도메인(창업·지원사업, 재무·세무, 인사·노무, 법률)의 전처리된 JSONL 데이터를 ChromaDB에 적재하여 검색합니다. 기존 청킹 전략에 여러 구조적 문제가 있어, 검색 품질을 근본적으로 개선하기 위한 전면 재설계를 수행했습니다.

### 핵심 목표

1. 법령 조문 경계 보존 (P0)
2. LLM 컨텍스트 잘림 해소 (P0)
3. 판례 하드커트 제거 및 구조적 분리 (P1)
4. 마크다운 테이블 무결성 보존 (P1)
5. Q&A(질의-회시) 쌍 보존 (P1)
6. bge-m3 임베딩 모델 용량에 맞는 chunk_size 재조정 (P2)
7. Parent Document Retrieval용 메타데이터 기반 마련 (P2)

---

## 2. 문제 분석

### 2-1. 법령 조문 경계 파괴 (P0)

| 항목 | 내용 |
|------|------|
| **현상** | `process_laws()`에서 법령 1건의 모든 조문을 하나의 `content`로 합친 후, `RecursiveCharacterTextSplitter(800자, 100자 overlap)`로 일률 분할. 조문 경계와 무관하게 800자마다 절단됨 |
| **영향** | `law_common_db` 전체. "근로기준법 제56조 내용 알려줘" 같은 질문에 정확한 조문 검색 불가 |
| **해결** | 전처리 단계에서 조문 단위로 분할 → 법령 1건을 N개 JSONL 레코드로 출력 |

### 2-2. format_context_length=500 (P0)

| 항목 | 내용 |
|------|------|
| **현상** | `rag/chains/rag_chain.py`에서 `doc.page_content[:settings.format_context_length]`로 LLM에 전달할 텍스트를 자름. chunk_size=800이어도 실제로 LLM에는 500자만 전달 |
| **영향** | 모든 도메인. chunk_size를 올려도 효과 없음 |
| **해결** | `format_context_length` 500 → 2000, `source_content_length` 300 → 500 |

### 2-3. 판례 5,000자 하드커트 (P1)

| 항목 | 내용 |
|------|------|
| **현상** | `process_court_cases()`에서 판례 전문이 5,000자 초과 시 `full_text[:5000]`으로 절단한 후 800자 분할. 판결 이유의 핵심 논증이 후반부에 있으면 유실 |
| **영향** | `law_common_db`의 판례 검색 품질 |
| **해결** | summary(판시사항+판결요지)와 detail(판례 전문) 2개 레코드로 구조적 분리 |

### 2-4. 마크다운 테이블 파괴 (P1)

| 항목 | 내용 |
|------|------|
| **현상** | 세무 가이드(`tax_support.jsonl`)에 포함된 마크다운 테이블(`\|` 구분 행)이 RecursiveCharacterTextSplitter에 의해 행 중간에서 분할 |
| **영향** | `finance_tax_db`의 세무 가이드 검색 품질 |
| **해결** | 테이블 인식 splitter(`table_aware`) 추가 |

### 2-5. Q&A 쌍 분리 (P1)

| 항목 | 내용 |
|------|------|
| **현상** | 노무 해석례(`labor_interpretation.jsonl`)의 질의-회시 쌍이 chunk_size 초과 시 중간에서 분리. 질의와 회시가 다른 청크에 배치 |
| **영향** | `hr_labor_db`의 해석례 검색 품질 |
| **해결** | Q&A 보존 splitter(`qa_aware`) 추가 |

### 2-6. chunk_size=800이 bge-m3 대비 과도하게 보수적 (P2)

| 항목 | 내용 |
|------|------|
| **현상** | bge-m3 최대 8,192토큰 대비 800자(≈400~560토큰)는 모델 용량의 ~6%만 활용 |
| **근거** | 한글 1자 ≈ 0.5~0.7 토큰. 1,500자 ≈ 750~1,050 토큰(~13%). 검색 정밀도와 문맥 보존의 균형점 |
| **해결** | 전체 chunk_size를 1,500~2,000으로 상향 |

---

## 3. 아키텍처 개요

### 데이터 흐름

```
원본 데이터 (PDF, 크롤링)
    │
    ▼
전처리 스크립트 (scripts/preprocessing/)
    │  - process_laws(): 조문 단위 분할
    │  - process_interpretations(): Q&A core/reason 분리
    │  - process_court_cases(): summary/detail 분리
    ▼
전처리 완료 데이터 (data/preprocessed/*.jsonl)
    │
    ▼
벡터DB 로더 (rag/vectorstores/loader.py)
    │  - DataLoader._should_chunk(): 청킹 여부 결정
    │  - DataLoader._split_text(): splitter_type 라우팅
    │    ├─ "default": RecursiveCharacterTextSplitter
    │    ├─ "table_aware": _split_with_table_awareness()
    │    └─ "qa_aware": _split_preserving_qa()
    ▼
ChromaDB 벡터 인덱스 (rag/vectordb/)
    │  - startup_funding_db
    │  - finance_tax_db
    │  - hr_labor_db
    │  - law_common_db
    ▼
RAG 검색 & 생성 (rag/agents/, rag/chains/)
    │  - format_context_length=2000 으로 LLM에 전달
    ▼
사용자 응답
```

### 컬렉션-파일-폴더 매핑

```
data/preprocessed/
├── startup_support/                 → startup_funding_db
│   ├── announcements.jsonl              (청킹 안함)
│   ├── industry_startup_guide_filtered.jsonl  (청킹 안함)
│   └── startup_procedures_filtered.jsonl      (조건부, 1500/200)
│
├── finance_tax/                     → finance_tax_db
│   └── tax_support.jsonl                (조건부, 1500/150, table_aware)
│
├── hr_labor/                        → hr_labor_db
│   ├── labor_interpretation.jsonl       (조건부, 1500/150, qa_aware)
│   └── hr_insurance_edu.jsonl           (조건부, 1500/150)
│
└── law_common/                      → law_common_db
    ├── laws_full.jsonl                  (조건부, 2000/200)
    ├── interpretations.jsonl            (조건부, 2000/200)
    ├── court_cases_tax.jsonl            (필수, 1500/150)
    └── court_cases_labor.jsonl          (필수, 1500/150)
```

---

## 4. 구현 상세

### Phase 1: 전처리 개선 (`scripts/preprocessing/preprocess_laws.py`)

#### 4-1-A. 법령 조문 단위 분할 — `process_laws()`

**변경 전**: 법령 1건 → JSONL 1행 (모든 조문을 하나의 content로 합침)
**변경 후**: 법령 1건 → JSONL N행 (조문 단위 독립 레코드)

**상수**:
```python
MIN_ARTICLE_CHUNK = 200   # 이 미만이면 인접 조문과 병합 (부칙, 삭제 조문 등)
MAX_ARTICLE_CHUNK = 3000  # 이 초과면 항(clause) 단위로 분할 (제2조 정의 등)
```

**분할 알고리즘**:
```
각 조문을 순회:
  if len(조문) > MAX_ARTICLE_CHUNK (3000):
      → 버퍼 출력 → 항(clause) 단위로 분할하여 개별 레코드 생성
  elif 버퍼 누적 + 조문 > MAX_ARTICLE_CHUNK:
      → 버퍼 출력 → 새 버퍼 시작
  elif len(조문) < MIN_ARTICLE_CHUNK (200):
      → 인접 조문과 병합 (버퍼에 축적)
  else:
      → 버퍼 출력 → 독립 레코드로 출력
```

**출력 JSONL 구조** (일반 조문):
```json
{
  "id": "LAW_010719_A56",
  "type": "law_article",
  "domain": "hr_labor",
  "title": "근로기준법 제56조 (연장·야간 및 휴일 근로)",
  "content": "[근로기준법]\n소관부처: 고용노동부\n시행일: 2024-02-09\n\n제56조(연장·야간 및 휴일 근로)\n① ...",
  "metadata": {
    "law_id": "010719",
    "law_name": "근로기준법",
    "article_number": "56",
    "article_range": "56",
    "parent_id": "LAW_010719"
  }
}
```

**핵심 함수**:

| 함수 | 역할 |
|------|------|
| `_format_article_text(article)` | 조문 1개를 포맷팅된 텍스트로 변환 |
| `_split_large_article_by_clauses(...)` | 대형 조문을 항 단위로 분할 |
| `_build_article_doc(...)` | 조문 단위 JSONL 레코드 생성 |
| `_determine_filter_info(ministry, domain)` | 필터 메서드/이유 결정 |

---

#### 4-1-B. 해석례 Q&A 보존 — `process_interpretations()`

**변경 전**: 질의요지 + 회답 + 이유를 하나의 content로 합침
**변경 후**: core(질의+회답) + reason(이유) 분리

```
Core 청크 (항상 생성):
  id: INTERP_{item_id}
  content: "[제목]\n\n질의요지:\n{질의}\n\n회답:\n{회답}"
  metadata.chunk_type: "core"
  ※ 절대 분리 금지

Reason 청크 (이유가 300자 이상일 때만):
  id: INTERP_{item_id}_reason
  content: "[제목]\n질의: {질의 앞 150자}...\n\n이유:\n{이유}"
  metadata.chunk_type: "reason"
  metadata.parent_id: INTERP_{item_id}
```

**근거**: 해석례에서 "질의요지"와 "회답"은 불가분의 관계. 분리되면 검색 시 "이 회답이 어떤 질의에 대한 것인지" 맥락이 유실됨. 이유(reason)는 보충 설명으로 별도 검색 단위로도 유의미.

---

#### 4-1-C. 판례 summary/detail 분리 — `process_court_cases()`

**변경 전**: `full_text[:5000]` 하드커트 후 800자 분할
**변경 후**: 판례 1건 → 2개 JSONL 레코드

```
Summary 청크 (항상 생성):
  id: CASE_{item_id}_summary
  content: 사건 헤더 + 판시사항 + 판결요지
  metadata.chunk_type: "summary"
  metadata.parent_id: CASE_{item_id}

Detail 청크 (full_text가 있을 때만):
  id: CASE_{item_id}_detail
  content: 사건 헤더 + 판례내용 전문 (하드커트 없음)
  metadata.chunk_type: "detail"
  metadata.parent_id: CASE_{item_id}
```

**근거**: 판결요지는 짧고 검색 적합성이 높음. 판례 전문은 상세 근거가 필요할 때 활용. 하드커트 제거로 판결 이유 후반부 유실 방지.

---

### Phase 2: 벡터DB 청킹 설정 (`rag/vectorstores/config.py`)

#### 4-2-A. 청킹 전략 요약표

| 파일 | 컬렉션 | 청킹 유형 | chunk_size | overlap | splitter_type | 비고 |
|------|--------|----------|-----------|---------|---------------|------|
| `announcements.jsonl` | startup_funding | 청킹 안함 | - | - | - | 공고 원문 보존 |
| `industry_startup_guide_filtered.jsonl` | startup_funding | 청킹 안함 | - | - | - | 가이드 원문 보존 |
| `startup_procedures_filtered.jsonl` | startup_funding | 조건부 | 1,500 | 200 | default | >3500자만 분할 |
| `tax_support.jsonl` | finance_tax | 조건부 | 1,500 | 150 | **table_aware** | 테이블 보존 |
| `labor_interpretation.jsonl` | hr_labor | 조건부 | 1,500 | 150 | **qa_aware** | Q&A 쌍 보존 |
| `hr_insurance_edu.jsonl` | hr_labor | 조건부 | 1,500 | 150 | default | >3500자만 분할 |
| `laws_full.jsonl` | law_common | 조건부 | 2,000 | 200 | default | 조문 안전망 |
| `interpretations.jsonl` | law_common | 조건부 | 2,000 | 200 | default | Q&A 안전망 |
| `court_cases_tax.jsonl` | law_common | **필수** | 1,500 | 150 | default | 판례 항상 분할 |
| `court_cases_labor.jsonl` | law_common | **필수** | 1,500 | 150 | default | 판례 항상 분할 |

#### 4-2-B. 청킹 결정 로직 (`_should_chunk()`)

```
1. FILE_CHUNKING_CONFIG에서 파일별 설정 조회
2. config가 None → 청킹 안함 (announcements, industry_startup_guide)
3. NO_CHUNK_FILES에 포함 → 청킹 안함
4. OPTIONAL_CHUNK_FILES에 포함 → len(content) > 3500 일 때만 청킹
5. CHUNK_FILES에 포함 → 항상 청킹 (court_cases_*)
```

`OPTIONAL_CHUNK_THRESHOLD` = **3500** (전처리에서 MAX_ARTICLE_CHUNK=3000으로 제어하므로 안전망 상향)

---

### Phase 3: 특수 Splitter (`rag/vectorstores/loader.py`)

#### 4-3-A. table_aware — 마크다운 테이블 보존 splitter

**적용 대상**: `tax_support.jsonl`

**알고리즘** (`_split_with_table_awareness()`):

```
1단계: 블록 분리
  - 행 단위로 순회
  - "|"로 시작하고 "|"로 끝나는 연속 행 → "table" 블록
  - 그 외 → "text" 블록

2단계: 블록 병합
  - table 블록: 절대 분할하지 않음 (chunk_size 초과해도 보존)
  - text 블록: RecursiveCharacterTextSplitter로 분할
  - table + 주변 text가 chunk_size 이내면 하나의 청크로 병합
  - 초과 시 축적된 텍스트를 먼저 출력 후 새 청크 시작
```

**예시**:
```
일반 텍스트 (300자)           ─┐
| 헤더1 | 헤더2 | 헤더3 |      │ → 하나의 청크 (800자 < 1500)
| 데이터 | 데이터 | 데이터 |    │
| 데이터 | 데이터 | 데이터 |    │
일반 텍스트 (200자)           ─┘
```

---

#### 4-3-B. qa_aware — Q&A 보존 splitter

**적용 대상**: `labor_interpretation.jsonl`

**알고리즘** (`_split_preserving_qa()`):

```
1단계: 패턴 감지
  - 정규식: (?=질의\s*:)|(?=회시\s*:) 로 텍스트를 블록 분리
  - Q&A 패턴이 없으면 기본 splitter로 fallback

2단계: 쌍 구성
  - "질의"로 시작하는 블록 + "회시"로 시작하는 블록 = 하나의 Q&A 쌍
  - Q&A 이전 텍스트는 header로 보존

3단계: 청크 생성
  - Q&A 쌍이 chunk_size 이내 → 그대로 하나의 청크
  - Q&A 쌍이 chunk_size 초과:
    └─ 회시 부분만 RecursiveCharacterTextSplitter로 분할
    └─ 각 분할 청크에 "header + 질의" 를 prefix로 유지 (맥락 보존)
```

**예시**:
```
[제목]                                 ← header

질의 : 연차유급휴가 미사용수당의      ← question (보존)
산정 기준이 어떻게 되나요?

회시 : 1. 근로기준법 제60조에         ← answer (필요 시 분할)
따르면... (이하 장문)

→ 청크1: [제목]\n\n질의 : ...\n\n회시 : 1. 근로기준법 제60조에...
→ 청크2: [제목]\n\n질의 : ...\n\n(회시 후반부)
```

---

### Phase 4: LLM 컨텍스트 길이 상향 (`rag/utils/config.py`)

| 설정 | 변경 전 | 변경 후 | 사용 위치 |
|------|---------|---------|----------|
| `format_context_length` | 500 | **2000** | `rag/chains/rag_chain.py` — LLM에 전달할 문서 내용 최대 길이 |
| `source_content_length` | 300 | **500** | `rag/chains/rag_chain.py` — SourceDocument 변환 시 내용 최대 길이 |

**근거**: 조문 단위 청크의 평균 길이는 500~2,000자. format_context_length=500이면 chunk_size를 올려도 LLM에 500자만 전달되어 개선 효과가 사라짐. 2,000으로 상향하여 조문 전체를 온전히 전달.

---

### Phase 5: Parent Document Retrieval 메타데이터 (P2)

현재 구현에서는 **메타데이터만 준비** (실제 retrieval 로직은 향후 과제):

| 데이터 유형 | parent_id 형식 | 용도 |
|------------|---------------|------|
| 법령 조문 | `LAW_{law_id}` | 같은 법령의 다른 조문 추적 |
| 해석례 reason | `INTERP_{item_id}` | core ↔ reason 연결 |
| 판례 detail | `CASE_{item_id}` | summary ↔ detail 연결 |

**향후 활용 시나리오**:
- "근로기준법 제56조" 검색 → 해당 조문 + 같은 법령의 인접 조문 컨텍스트 제공
- 판례 summary 검색 → 연결된 detail 청크를 추가 컨텍스트로 활용

---

## 5. chunk_size 근거

### 임베딩 모델 용량 분석

```
bge-m3 최대 토큰: 8,192
한글 1자 ≈ 0.5~0.7 토큰 (BPE 기준)

chunk_size  | 예상 토큰수     | 모델 활용률
----------- | -------------- | ----------
800자       | 400~560토큰    | ~6%   (기존)
1,500자     | 750~1,050토큰  | ~13%  (개선)
2,000자     | 1,000~1,400토큰| ~17%  (법률)
```

### 도메인별 chunk_size 선정 근거

| 도메인 | chunk_size | 근거 |
|--------|-----------|------|
| 법률 (laws, interpretations) | 2,000 | 조문 단위 평균 500~2,000자. 전처리에서 MAX_ARTICLE_CHUNK=3000으로 제어하므로 안전망 역할 |
| 판례 (court_cases) | 1,500 | summary는 짧지만 detail은 장문. 필수 청킹으로 분할 보장 |
| 세무 (tax_support) | 1,500 | 테이블 포함 중문. table_aware가 테이블 보존 담당 |
| 노무 (labor_interpretation) | 1,500 | Q&A 쌍 보존. qa_aware가 쌍 보존 담당 |
| 그 외 | 1,500 | 기본값. 검색 정밀도와 문맥 보존의 균형 |

---

## 6. 수정 파일 요약

| 파일 | 변경 내용 |
|------|----------|
| `scripts/preprocessing/preprocess_laws.py` | 법령 조문 단위 분할, 해석례 Q&A core/reason 분리, 판례 summary/detail 분리, 하드커트 제거 |
| `rag/vectorstores/config.py` | DATA_SOURCES 실제 폴더 구조에 맞춤, FILE_TO_COLLECTION_MAPPING 실제 파일명에 맞춤, chunk_size 1500~2000 상향, splitter_type 필드 추가, OPTIONAL_CHUNK_THRESHOLD 3500 |
| `rag/vectorstores/loader.py` | `_split_text()` 라우터, `_split_with_table_awareness()`, `_split_preserving_qa()` 추가 |
| `rag/utils/config.py` | format_context_length 500→2000, source_content_length 300→500 |

---

## 7. 검증 결과

### 데이터 로드 검증 (기존 전처리 데이터 기준)

| 컬렉션 | 문서 수 | 상태 |
|--------|--------|------|
| startup_funding_db | 2,109 | OK |
| finance_tax_db | 134 | OK |
| hr_labor_db | 493 | OK |
| law_common_db | 68,143 | OK |

### 테스트 결과

```
376 passed, 11 failed (기존 미관련 실패), 5 skipped
```

기존 실패 11건은 이번 변경과 무관한 테스트 (domain_config_comparison, domain_config_db, reranker, retrieval_agent).

---

## 8. 후속 작업

| 작업 | 상태 | 설명 |
|------|------|------|
| 전처리 재실행 | 미실행 | 원본 데이터(law-raw/)로 `preprocess_laws.py` 실행하여 조문 단위 JSONL 생성 |
| 벡터DB 재빌드 | 미실행 | `python -m vectorstores.build_vectordb --all --force` |
| Parent Document Retrieval 구현 | 미구현 | parent_id 메타데이터 기반 인접 문서 검색 로직 |
| 검색 품질 A/B 테스트 | 미실행 | 개선 전/후 동일 질의에 대한 검색 결과 비교 |

### 검색 품질 테스트 질의 예시

| 질의 | 기대 변화 |
|------|----------|
| "근로기준법 제56조 내용" | 조문 단위로 정확히 검색 (vs 800자 청크에서 조문 일부만 검색) |
| "최저임금 위반 시 처벌" | 판례 summary에서 처벌 관련 요지 검색 |
| "연차유급휴가 해석례" | 질의-회답 쌍이 온전히 검색 |
| "부가세 신고 절차" | 테이블 포함 가이드가 온전히 검색 |
