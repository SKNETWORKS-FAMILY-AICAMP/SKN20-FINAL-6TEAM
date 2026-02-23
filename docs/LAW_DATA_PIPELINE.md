# 법률 데이터 전처리 & VectorDB 저장 파이프라인

> **작성일**: 2026-02-12
> **대상 데이터**: 법령, 법령해석례, 판례 (총 11,879건)
> **전처리 스크립트**: `scripts/preprocessing/preprocess_laws.py` (633줄)

---

## 목차

1. [전체 파이프라인 개요](#1-전체-파이프라인-개요)
2. [원본 데이터 (Raw)](#2-원본-데이터-raw)
3. [전처리 과정](#3-전처리-과정)
4. [전처리 결과 (Preprocessed)](#4-전처리-결과-preprocessed)
5. [VectorDB 저장](#5-vectordb-저장)
6. [검색 설정](#6-검색-설정)
7. [파일-컬렉션 매핑 전체 정리](#7-파일-컬렉션-매핑-전체-정리)

---

## 1. 전체 파이프라인 개요

```
[Stage 0] 원본 수집 (크롤링)
  data/law-raw/*.json
      │
      ▼
[Stage 1] 전처리 (preprocess_laws.py)
  - 3단계 도메인 분류
  - 텍스트 정제 (HTML 제거, 공백 정리)
  - 중첩 JSON → 단일 content 평문 통합
  - 법령 참조 추출 (「법령명」 패턴)
  - etc 도메인 분리 (VectorDB 제외)
      │
      ▼
[Stage 2] JSONL 로딩 (loader.py)
  - FILE_TO_COLLECTION_MAPPING으로 컬렉션 결정
  - fallback 파일 탐색 (판례)
      │
      ▼
[Stage 3] 조건부 청킹 (loader.py)
  - RecursiveCharacterTextSplitter (800자/100자 overlap)
  - 법령/해석례: content > 1,500자이면 청킹
  - 판례: 항상 청킹
      │
      ▼
[Stage 4] Document 생성 (loader.py)
  - page_content = content 또는 청크
  - metadata = {id, type, domain, title, source_*, meta_*, ...}
      │
      ▼
[Stage 5] 임베딩 & 저장 (chroma.py)
  - BAAI/bge-m3 임베딩 (1024차원, cosine)
  - batch_size=100 단위로 ChromaDB에 저장
  - HNSW 인덱스 (cosine similarity)
      │
      ▼
[Stage 6] ChromaDB 영속 저장
  - 경로: rag/vectordb/chroma.sqlite3
  - 컬렉션: law_common_db, finance_tax_db, hr_labor_db
```

---

## 2. 원본 데이터 (Raw)

### 2-1. 파일 목록

경로: `data/law-raw/`

| 파일명 | 크기 | 레코드 수 | 형식 | 설명 |
|--------|------|-----------|------|------|
| `01_laws_full.json` | 304 MB | 5,539건 | JSON | 전체 현행 법령 (조문 포함) |
| `expc_전체.json` | 73.6 MB | 8,604건 | JSON | 법령해석례 (법제처 등) |
| `prec_tax_accounting.json` | 24.7 MB | 3,068건 | JSON | 세무/회계 판례 |
| `prec_labor.json` | 19.6 MB | 1,427건 | JSON | 노무/근로 판례 |

### 2-2. 원본 데이터 구조

#### 법령 (`01_laws_full.json`)

4단계 중첩 구조: 법령 > 조문(articles) > 항(clauses) > 호(items)

```json
{
  "type": "현행법령",
  "total_count": 5539,
  "collected_at": "2026-01-20T11:43:48.592993",
  "laws": [
    {
      "law_id": "010719",
      "name": "소득세법",
      "ministry": "기획재정부",
      "enforcement_date": "20250101",
      "articles": [
        {
          "number": "1",
          "title": "목적",
          "content": "제1조(목적) 이 법은 ... <개정 2023.8.8>",
          "clauses": [
            {
              "number": "1",
              "content": "...",
              "items": [
                {"number": "1.", "content": "..."}
              ]
            }
          ]
        }
      ]
    }
  ]
}
```

#### 법령해석례 (`expc_전체.json`)

평면 구조. `question_summary`, `answer`, `reason` 3개 텍스트 필드 분리.

```json
{
  "type": "법령해석례",
  "collected_count": 8604,
  "items": [
    {
      "id": "313107",
      "title": "양도소득세 부과대상 범위",
      "case_no": "05-0096",
      "answer_date": "20051223",
      "answer_org": "법제처",
      "question_org": "국방부",
      "question_summary": "질의 내용...",
      "answer": "회답 내용...",
      "reason": "이유..."
    }
  ]
}
```

#### 판례 (`prec_tax_accounting.json`, `prec_labor.json`)

`<br/>` HTML 태그 대량 포함. 5개 텍스트 필드 분리. 빈 레코드 다수.

```json
{
  "type": "판례",
  "category": "세무/회계",
  "total_count": 3068,
  "items": [
    {
      "id": "613209",
      "case_name": "법인세부과처분무효확인",
      "case_no": "2025두34254",
      "decision_date": "20251204",
      "court_name": "대법원",
      "court_type": "세무",
      "decision_type": "판결",
      "decision": "선고",
      "summary": "<br/> [1] 과세예고통지 및 ...<br/>",
      "decision_summary": "<br/> [1] 과세예고통지는 ...<br/>",
      "reference": "[1] 헌법 제12조 ...<br/>",
      "full_text": "【원고, 피상고인】 ... <br/>【피고, 상고인】 ..."
    }
  ]
}
```

---

## 3. 전처리 과정

스크립트: `scripts/preprocessing/preprocess_laws.py` (633줄)

### 3-1. 텍스트 정제 (`clean_text`)

| 순서 | 규칙 | Before | After |
|------|------|--------|-------|
| 1 | `<br/>` → 줄바꿈 | `과세예고<br/>통지` | `과세예고\n통지` |
| 2 | HTML 태그 제거 | `<개정 2023.8.8>` | (제거) |
| 3 | 연속 3줄+ → 2줄 | `\n\n\n\n` | `\n\n` |
| 4 | 연속 공백/탭 → 단일 | `항목  내용` | `항목 내용` |
| 5 | 줄별 양쪽 공백 제거 | `  제1조  ` | `제1조` |
| 6 | 전각→반각 공백 | `\u3000` | ` ` |

### 3-2. content 필드 조합 방식

#### 법령: 중첩 JSON → 평문 통합

```
[법령명]
소관부처: {ministry}
시행일: {YYYY-MM-DD}

제N조 (조문제목)
조문내용
  항내용
    호내용

제N+1조 (조문제목)
...
```

- 삭제된 조문: 30자 미만 + "삭제" 포함 → 스킵

#### 법령해석례: 3개 필드 통합

```
[해석례 제목]

질의요지:
{question_summary}

회답:
{answer}

이유:
{reason}
```

#### 판례: 구조적 통합 + 잘림

```
[사건명]
사건번호: {case_no}
법원: {court_name}
선고일: {YYYY-MM-DD}

판시사항:
{summary}

판결요지:
{decision_summary}

판례내용:
{full_text}
```

- `full_text`가 5,000자 초과 시 → 앞 5,000자 + `"..."` 추가
- tax 판례 26.5%, labor 판례 32.9%에서 잘림 발생

### 3-3. 날짜 포맷 변환

`YYYYMMDD` → `YYYY-MM-DD` (8자리가 아니면 `null`)

### 3-4. 법령 참조 추출 (`extract_law_references`)

- 정규식: `[「『]([^」』]+)[」』]`로 법령명 추출
- 법령명 다음 50자 이내에서 `제N조` 패턴 매칭
- 중복 제거 후 `related_laws` 배열에 저장
- 법령에서는 미적용 (빈 배열), 해석례/판례에서만 적용

### 3-5. 도메인 분류 (3단계)

#### Stage 1: 소관부처/회답기관 매핑 (최고 우선순위)

| 기관명 | 할당 도메인 |
|--------|-------------|
| 고용노동부 | `hr_labor` |
| 기획재정부 | `finance_tax` |
| 국세청 | `finance_tax` |
| 중소벤처기업부 | `startup_funding` |
| 공정거래위원회 | `startup_funding` |
| 지식재산처 | `startup_funding` |

- 법령: `ministry` 필드, 해석례: `answer_org` 필드로 매칭
- 512건이 이 방법으로 분류 (11.3%)

#### Stage 2: 키워드 매칭

| 도메인 | 대표 키워드 (17~22개) |
|--------|----------------------|
| `finance_tax` | 세법, 소득세, 법인세, 부가가치세, 국세, 과세, 납세, 상속세, 증여세 등 |
| `hr_labor` | 근로, 노동, 고용, 임금, 퇴직, 해고, 휴가, 4대보험, 산재, 최저임금 등 |
| `startup_funding` | 창업, 벤처, 중소기업, 소상공인, 사업자, 법인설립, 특허, 상표, 저작권 등 |
| `general` | 민법, 상법, 행정절차, 행정심판, 전자상거래, 소비자, 개인정보 등 |

- `KEYWORD_OVERRIDES`: "법인세", "법인세법" → `finance_tax` (+5점). "법인" 키워드와의 충돌 방지
- content 전체에서 키워드 출현 횟수를 합산, 최고점 도메인 선택
- 4,016건이 이 방법으로 분류

#### Stage 3: etc 분류

- 모든 도메인 점수가 0이면 `etc`로 분류
- `laws_etc.jsonl`, `interpretations_etc.jsonl`로 별도 저장
- **VectorDB에서 제외** (`FILE_TO_COLLECTION_MAPPING`에 미등록)

#### 판례의 도메인 분류

- 판례는 3단계 분류 미적용
- 원본 파일의 카테고리를 그대로 사용: `tax` → `finance_tax`, `labor` → `hr_labor`

### 3-6. 필터링 요약

| 원본 파일 | 전체 | RAG 관련 | 제외 | 제외 사유 |
|-----------|------|---------|------|-----------|
| `01_laws_full.json` | 5,539 | 4,528 (81.7%) | 1,011 | etc 도메인 |
| `expc_전체.json` | 8,604 | 4,421 (51.4%) | 4,183 | etc 도메인 |
| `prec_tax_accounting.json` | 3,068 | 1,949 (63.5%) | 1,119 | 빈 레코드 |
| `prec_labor.json` | 1,427 | 981 (68.7%) | 446 | 빈 레코드 |
| **합계** | **18,638** | **11,879** | **5,759** | |

---

## 4. 전처리 결과 (Preprocessed)

### 4-1. 파일 목록

경로: `data/preprocessed/law/`

| 파일명 | 크기 | 레코드 수 | 문서 타입 |
|--------|------|-----------|-----------|
| `laws_full.jsonl` | 169.7 MB | 4,528건 | `law` |
| `interpretations.jsonl` | 44.7 MB | 4,421건 | `interpretation` |
| `court_cases_tax.jsonl` | 17.4 MB | 1,949건 | `court_case` |
| `court_cases_labor.jsonl` | 9.8 MB | 981건 | `court_case` |
| **합계** | **241.6 MB** | **11,879건** | |

### 4-2. 통합 JSONL 스키마

모든 파일이 동일한 스키마를 따릅니다.

| 필드 | 타입 | 설명 | 예시 |
|------|------|------|------|
| `id` | string | `LAW_` / `INTERP_` / `CASE_` 접두사 + 원본ID | `"LAW_010719"` |
| `type` | string | `"law"` / `"interpretation"` / `"court_case"` | `"law"` |
| `domain` | string | 도메인 분류 결과 | `"finance_tax"` |
| `title` | string | 문서 제목 | `"소득세법"` |
| `content` | string | 정제된 본문 (평문) | `"[소득세법]\n소관부처: ..."` |
| `source` | object | `{name, url, collected_at}` | |
| `related_laws` | array | 참조 법령 (해석례/판례) | `[{law_name, article_ref}]` |
| `effective_date` | string | 시행일/회답일/선고일 (`YYYY-MM-DD`) | `"2025-01-01"` |
| `metadata` | object | 문서 타입별 부가 정보 | |

### 4-3. content 길이 통계

| 파일 | 최소 | 평균 | 최대 |
|------|------|------|------|
| `laws_full.jsonl` | 65자 | 16,095자 | 530,017자 |
| `interpretations.jsonl` | 630자 | 3,809자 | 14,800자 |
| `court_cases_tax.jsonl` | 296자 | 3,696자 | 10,263자 |
| `court_cases_labor.jsonl` | 389자 | 4,126자 | 12,678자 |

### 4-4. 도메인 분포

| 도메인 | 법령 | 해석례 | 판례(tax) | 판례(labor) | 합계 | 비율 |
|--------|------|--------|-----------|-------------|------|------|
| `startup_funding` | 1,892 | 2,204 | - | - | 4,096 | 34.5% |
| `finance_tax` | 957 | 594 | 1,949 | - | 3,500 | 29.5% |
| `hr_labor` | 964 | 856 | - | 981 | 2,801 | 23.6% |
| `general` | 715 | 767 | - | - | 1,482 | 12.5% |
| **합계** | **4,528** | **4,421** | **1,949** | **981** | **11,879** | |

---

## 5. VectorDB 저장

### 5-1. 컬렉션 구조

| 컬렉션명 | 도메인 키 | 저장 파일 | 설계 의도 |
|----------|-----------|-----------|-----------|
| `law_common_db` | `law_common` | `laws_full.jsonl`, `interpretations.jsonl` | 공통 법률DB (법률 보충 검색용) |
| `finance_tax_db` | `finance_tax` | `court_cases_tax.jsonl` + 세무 데이터 | 세무 에이전트 전용 |
| `hr_labor_db` | `hr_labor` | `court_cases_labor.jsonl` + 노무 데이터 | 인사노무 에이전트 전용 |

### 5-2. 청킹 전략

설정 파일: `rag/vectorstores/config.py`

| 파일 | 청킹 방식 | 조건 | chunk_size | chunk_overlap |
|------|-----------|------|------------|---------------|
| `laws_full.jsonl` | **조건부** | content > 1,500자 | 800 | 100 |
| `interpretations.jsonl` | **조건부** | content > 1,500자 | 800 | 100 |
| `court_cases_tax.jsonl` | **항상** | 무조건 | 800 | 100 |
| `court_cases_labor.jsonl` | **항상** | 무조건 | 800 | 100 |

**텍스트 분할기**: `RecursiveCharacterTextSplitter`
- 구분자 우선순위: `\n\n` → `\n` → `.` → ` `
- 단락 단위 분할 시도 → 줄 → 문장 → 공백 순으로 fallback

**청킹 판단 로직** (`loader.py`):
- `OPTIONAL_CHUNK_FILES`: 법령, 해석례 → 1,500자 임계값 기준
- `ALWAYS_CHUNK_FILES`: 판례 → 항상 청킹
- `_etc.jsonl` 파일: `FILE_TO_COLLECTION_MAPPING`에 미등록 → 자동 제외

### 5-3. 임베딩 모델

| 항목 | 값 |
|------|-----|
| 모델 | `BAAI/bge-m3` |
| 차원 | 1024 |
| 정규화 | `normalize_embeddings=True` |
| 디바이스 | CUDA > MPS > CPU 자동 감지 |
| 유사도 메트릭 | cosine (HNSW 인덱스) |
| 캐시 | `@lru_cache(maxsize=1)` 싱글톤 |

### 5-4. 메타데이터 구조

ChromaDB에 저장되는 메타데이터 필드:

#### 공통 필드 (모든 문서)

| 필드 | 소스 | 예시 |
|------|------|------|
| `id` | JSONL `id` 또는 `{id}_{chunk_index}` | `"LAW_12345"` / `"LAW_12345_0"` |
| `type` | JSONL `type` | `"law"` |
| `domain` | JSONL `domain` | `"finance_tax"` |
| `title` | JSONL `title` | `"소득세법"` |
| `source_file` | 파일명 | `"laws_full.jsonl"` |
| `source_name` | `source.name` | `"국가법령정보센터"` |
| `source_url` | `source.url` | `"https://law.go.kr/..."` |
| `collected_at` | `source.collected_at` | `"2026-01-20"` |
| `effective_date` | JSONL `effective_date` | `"2025-01-01"` |

#### 청킹 시 추가 필드

| 필드 | 설명 | 예시 |
|------|------|------|
| `chunk_index` | 청크 순서 번호 | `0`, `1`, `2`, ... |
| `original_id` | 청킹 전 원본 ID | `"LAW_12345"` |

#### 문서 타입별 `meta_*` 필드

**법령** (`meta_` 접두사로 저장):

| 필드 | 예시 |
|------|------|
| `meta_law_id` | `"12345"` |
| `meta_ministry` | `"기획재정부"` |
| `meta_enforcement_date` | `"20250101"` |
| `meta_article_count` | `178` |
| `meta_filter_method` | `"org_mapping"` / `"keyword"` |
| `meta_filter_reason` | `"소관부처: 기획재정부"` |

**법령해석례**:

| 필드 | 예시 |
|------|------|
| `meta_case_no` | `"05-0096"` |
| `meta_answer_date` | `"20051223"` |
| `meta_answer_org` | `"법제처"` |
| `meta_question_org` | `"국방부"` |
| `meta_filter_method` | `"keyword"` |

**판례**:

| 필드 | 예시 |
|------|------|
| `meta_case_no` | `"2025두34254"` |
| `meta_court_name` | `"대법원"` |
| `meta_court_type` | `"세무"` |
| `meta_decision_type` | `"판결"` |
| `meta_decision` | `"선고"` |
| `meta_category` | `"tax"` / `"labor"` |

### 5-5. ChromaDB 최종 저장 형태

#### 청킹 안 된 문서 (해석례, content <= 1,500자)

```
ChromaDB Record:
  id: "INTERP_123456"

  document (page_content):
    "[양도소득세의 부과대상 자산의 범위]

     질의요지:
     부동산 매도차익에 대한 양도소득세 과세 여부...

     회답:
     「소득세법」 제94조 제1항에 따라..."

  metadata:
    id: "INTERP_123456"
    type: "interpretation"
    domain: "finance_tax"
    title: "양도소득세의 부과대상 자산의 범위"
    source_file: "interpretations.jsonl"
    source_name: "국가법령정보센터"
    effective_date: "2024-03-15"
    meta_answer_org: "기획재정부"
    meta_filter_method: "org_mapping"
    ...

  embedding: [0.012, -0.034, ..., 0.021]  (1024차원)
```

#### 청킹된 문서 (법령, content > 1,500자)

```
ChromaDB Record (chunk 0 of N):
  id: "LAW_12345_0"

  document (page_content):
    "[소득세법]
     소관부처: 기획재정부
     시행일: 2025-01-01

     제1조 (목적)
     이 법은 개인의 소득에 대하여..."  (최대 800자)

  metadata:
    id: "LAW_12345_0"
    type: "law"
    domain: "finance_tax"
    title: "소득세법"
    chunk_index: 0
    original_id: "LAW_12345"
    meta_ministry: "기획재정부"
    meta_article_count: 178
    ...

  embedding: [0.008, -0.041, ..., 0.017]  (1024차원)
```

---

## 6. 검색 설정

### 6-1. Hybrid Search 구조

```
쿼리 입력
   │
   ├── (1) 벡터 검색: ChromaDB similarity_search (k×3건)
   │       cosine distance → 유사도 변환 (1 - distance)
   │
   ├── (2) BM25 검색: 한글/영문 토큰 기반 (k×3건)
   │       BM25Index (지연 초기화)
   │
   ├── (3) 가중 RRF 융합
   │       vector_weight=0.7, bm25_weight=0.3
   │       Reciprocal Rank Fusion (k=60)
   │
   └── (4) Re-ranking
           Cross-encoder (BAAI/bge-reranker-base)
           쿼리-문서 쌍별 관련성 점수 → 상위 top_k 선택
```

### 6-2. 주요 설정값

| 설정 | 기본값 | 설명 |
|------|--------|------|
| `enable_hybrid_search` | `True` | BM25+Vector 하이브리드 검색 |
| `vector_search_weight` | `0.7` | 벡터:BM25 = 7:3 |
| `enable_reranking` | `True` | Cross-encoder 재정렬 |
| `reranker_type` | `"cross-encoder"` | BAAI/bge-reranker-base |
| `retrieval_k` | `3` | 도메인별 검색 결과 수 |
| `retrieval_k_common` | `2` | 공통 법령DB 검색 수 |
| `enable_legal_supplement` | `True` | 법률 키워드 감지 시 law_common_db 보충 검색 |
| `legal_supplement_k` | `3` | 법률 보충 검색 문서 수 |

### 6-3. 법률 보충 검색 (Legal Supplement)

- 주 도메인이 `law_common`이 아닌 질문에서 법률 키워드 감지 시 발동
- `law_common_db`에서 추가 검색 (최대 3건)
- 키워드 기반 판단 (LLM 미사용): `utils/legal_supplement.py`

---

## 7. 파일-컬렉션 매핑 전체 정리

### Before → After → VectorDB 전체 흐름

```
data/law-raw/                      data/preprocessed/law/              ChromaDB
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

01_laws_full.json (5,539건)
  │  3단계 도메인 분류
  │  중첩 JSON → 평문 통합
  │  etc 1,011건 제외
  ├─→ laws_full.jsonl (4,528건) ──────→ law_common_db
  └─→ laws_etc.jsonl (1,011건)         (VectorDB 제외)

expc_전체.json (8,604건)
  │  3단계 도메인 분류
  │  질의/회답/이유 통합
  │  etc 4,183건 제외
  ├─→ interpretations.jsonl (4,421건) ─→ law_common_db
  └─→ interpretations_etc.jsonl        (VectorDB 제외)

prec_tax_accounting.json (3,068건)
  │  빈 레코드 1,119건 제외
  │  HTML 정제, full_text 5,000자 잘림
  └─→ court_cases_tax.jsonl (1,949건) ─→ finance_tax_db

prec_labor.json (1,427건)
  │  빈 레코드 446건 제외
  │  HTML 정제, full_text 5,000자 잘림
  └─→ court_cases_labor.jsonl (981건) ─→ hr_labor_db
```

### 핵심 설계 포인트

1. **법령/해석례 → 공통 컬렉션 (`law_common_db`)**: 모든 에이전트가 법률 보충 검색으로 공유 참조
2. **판례 → 도메인별 컬렉션**: 세무 판례는 `finance_tax_db`, 노동 판례는 `hr_labor_db`에 분리
3. **조건부 청킹**: 짧은 해석례(<=1,500자)는 문맥 손실 없이 통째로, 긴 법령은 800자 단위 분할
4. **etc 자동 제외**: `FILE_TO_COLLECTION_MAPPING`에 미등록 → VectorDB 투입 차단
5. **Fallback 파일 탐색**: 판례 파일이 `law/` 디렉토리에 있지만 다른 도메인에 매핑 → loader가 자동 탐색

---

## 관련 파일

| 파일 | 설명 |
|------|------|
| `scripts/preprocessing/preprocess_laws.py` | 전처리 스크립트 (633줄) |
| `rag/vectorstores/config.py` | 컬렉션 매핑, 청킹 설정 |
| `rag/vectorstores/loader.py` | JSONL → Document 변환 |
| `rag/vectorstores/chroma.py` | ChromaDB 래퍼 |
| `rag/vectorstores/embeddings.py` | 임베딩 모델 설정 |
| `rag/vectorstores/build_vectordb.py` | VectorDB 빌드 스크립트 |
| `rag/utils/search.py` | Hybrid Search 구현 |
| `rag/utils/legal_supplement.py` | 법률 보충 검색 판단 |
