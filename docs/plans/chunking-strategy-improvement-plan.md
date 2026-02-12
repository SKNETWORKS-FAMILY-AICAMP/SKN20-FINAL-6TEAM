# 전체 도메인 청킹 전략 개선 계획

## 목표

1. 법령 조문 경계 파괴 문제 해결 (P0)
2. LLM에 전달되는 컨텍스트 잘림 문제 해결 (P0)
3. 판례 하드커트, 테이블 파괴, Q&A 분리 등 비법률 도메인 개선 (P1)
4. bge-m3 모델 용량에 맞는 chunk_size 재조정 (P2)
5. Parent Document Retrieval을 위한 메타데이터 기반 마련 (P2)

## 예상 효과

| 메트릭 | 개선 전 | 개선 후 |
|--------|---------|---------|
| 법령 조문 검색 정확도 | 조문 경계 파괴로 낮음 | 조문 단위 독립 검색 |
| LLM 컨텍스트 활용 | 800자 청크 중 500자만 전달 | 2000자까지 온전히 전달 |
| 판례 전문 활용 | 5,000자 하드커트 | 전문 보존 (summary/detail 분리) |
| 테이블 데이터 무결성 | 분할 시 파괴 가능 | 테이블 블록 보존 |
| Q&A 쌍 무결성 | 1,500자 초과 시 분리 | 질의-회답 쌍 보존 |

---

## 핵심 문제 상세

### 문제 1: 법령 조문 경계 파괴 (P0)

**현상**: `process_laws()`에서 법령 1건의 모든 조문을 하나의 `content`로 합친 후, `RecursiveCharacterTextSplitter(800자, 100자 overlap)`로 일률 분할. 조문 경계와 무관하게 800자 단위로 잘려 "제56조 ① 사용자는 연장근로에 대하여..." 같은 조문이 중간에서 끊김.

**영향**: law_common_db 전체. "근로기준법 제56조 내용 알려줘" 같은 질문에 정확한 조문 검색 불가.

**해결**: 조문 단위 분할 → 법령 1건을 N개 JSONL 레코드로 분리.

### 문제 2: format_context_length=500 (P0)

**현상**: `rag/chains/rag_chain.py`에서 `doc.page_content[:settings.format_context_length]`로 LLM에 전달할 컨텍스트를 자름. chunk_size=800이어도 실제 LLM에는 500자만 전달.

**영향**: 모든 도메인. chunk_size를 올려도 효과 없음.

**해결**: `format_context_length` 500 → 2000, `source_content_length` 300 → 500.

### 문제 3: 판례 full_text[:5000] 하드커트 (P1)

**현상**: `process_court_cases()`에서 판례 전문이 5,000자 초과 시 `full_text[:5000]`으로 자른 후 800자 분할. 판결 이유의 핵심 논증이 후반부에 있을 경우 유실.

**영향**: finance_tax_db, hr_labor_db의 판례 검색 품질.

**해결**: summary(판시사항+판결요지)와 detail(판례 전문) 2개 레코드로 분리.

### 문제 4: 세무 가이드 마크다운 테이블 파괴 (P1)

**현상**: `extracted_documents_final.jsonl`에 포함된 마크다운 테이블(`|` 구분 행)이 RecursiveCharacterTextSplitter에 의해 행 중간에서 분할될 수 있음.

**영향**: finance_tax_db의 세무 가이드 검색 품질.

**해결**: 테이블 인식 splitter(`table_aware`) 추가.

### 문제 5: Q&A 쌍 분리 (P1)

**현상**: 노무 해석례(`labor_interpretation.jsonl`)의 질의-회시 쌍이 1,500자 초과 시 중간에서 분리. 질의와 회시가 다른 청크에 배치되어 검색 시 맥락 유실.

**영향**: hr_labor_db의 해석례 검색 품질.

**해결**: Q&A 보존 splitter(`qa_aware`) 추가.

### 문제 6: 4대보험 파일명 불일치 (P1)

**현상**: `vectorstores/config.py`에서 `hr_major_insurance.jsonl`을 참조하지만, 실제 전처리 스크립트 출력은 `hr_4insurance_documents.jsonl`과 `hr_insurance_edu.jsonl`.

**영향**: hr_labor_db에 4대보험 데이터가 로드되지 않음.

**해결**: config의 파일명 매핑을 실제 출력에 맞게 수정.

### 문제 7: chunk_size=800이 bge-m3 대비 과도하게 보수적 (P2)

**현상**: bge-m3 최대 8,192토큰 대비 800자(≈400~560토큰)는 모델 용량의 ~6%만 활용. 문맥 보존 부족.

**근거**: 한글 1자 ≈ 0.5~0.7 토큰. 1,500자 ≈ 750~1,050 토큰(모델 용량의 ~13%). 검색 정밀도와 문맥 보존의 균형점.

**해결**: 전체 chunk_size를 1,500~2,000으로 상향.

---

## 수정 대상 파일

| 파일 | 변경 내용 | Phase |
|------|----------|-------|
| `scripts/preprocessing/preprocess_laws.py` | 법령 조문 단위 분할, 해석례 Q&A 보존, 판례 summary/detail 분리 | 1, 2 |
| `rag/vectorstores/config.py` | 청킹 설정 전면 개편, chunk_size 상향, splitter_type 추가 | 1, 2 |
| `rag/vectorstores/loader.py` | 테이블 인식 splitter, Q&A 보존 splitter 추가 | 2 |
| `rag/utils/config.py` | `format_context_length`, `source_content_length` 상향 | 1 |

---

## Phase 1: 법령 조문 단위 분할 + context length 수정 (P0)

### 1-A. `preprocess_laws.py` — `process_laws()` 재구현

**변경 전**: 법령 1건 → JSONL 1행 (모든 조문을 하나의 content로 합침)
**변경 후**: 법령 1건 → JSONL N행 (조문 단위 독립 레코드)

#### 상수 정의

```python
MIN_ARTICLE_CHUNK = 200   # 이 미만이면 인접 조문과 병합 (부칙 등)
MAX_ARTICLE_CHUNK = 3000  # 이 초과면 항(clause) 단위로 분할 (제2조 정의 등)
```

#### 분할 전략

```
조문 순회:
  if len(조문) > MAX_ARTICLE_CHUNK (3000):
      → 버퍼 출력 → 항(clause) 단위로 분할
  elif 버퍼 + 조문 > MAX_ARTICLE_CHUNK:
      → 버퍼 출력 → 새 버퍼 시작
  elif len(조문) < MIN_ARTICLE_CHUNK (200):
      → 인접 조문과 병합 (버퍼에 축적)
  else:
      → 버퍼 출력 → 독립 레코드로 출력
```

#### 출력 JSONL 구조

일반 조문 (독립 레코드):
```json
{
  "id": "LAW_010719_A56",
  "type": "law_article",
  "domain": "hr_labor",
  "title": "근로기준법 제56조 (연장·야간 및 휴일 근로)",
  "content": "[근로기준법]\n소관부처: 고용노동부\n시행일: 2024-02-09\n\n제56조(연장·야간 및 휴일 근로)\n① 사용자는 연장근로에 대하여...",
  "metadata": {
    "law_id": "010719",
    "law_name": "근로기준법",
    "ministry": "고용노동부",
    "article_number": "56",
    "article_title": "연장·야간 및 휴일 근로",
    "article_range": "56",
    "parent_id": "LAW_010719",
    "filter_method": "org_mapping",
    "filter_reason": "소관부처: 고용노동부"
  }
}
```

병합된 소형 조문 (부칙 등):
```json
{
  "id": "LAW_010719_A120-122",
  "title": "근로기준법 제120조~제122조",
  "metadata": {
    "article_range": "120-122",
    "parent_id": "LAW_010719"
  }
}
```

대형 조문 항 단위 분할 (제2조 정의 등):
```json
{
  "id": "LAW_010719_A2-part1",
  "title": "근로기준법 제2-1조",
  "metadata": {
    "article_range": "2-part1",
    "parent_id": "LAW_010719"
  }
}
```

#### 핵심 함수

| 함수 | 역할 |
|------|------|
| `_format_article_text(article)` | 조문 1개를 포맷팅된 텍스트로 변환 |
| `_split_large_article_by_clauses(...)` | 대형 조문을 항 단위로 분할하여 기록 |
| `_build_article_doc(...)` | 조문 단위 JSONL 레코드 생성 |
| `_determine_filter_info(ministry, domain)` | 필터 메서드/이유 결정 |
| `process_laws(...)` | 메인 처리 — 조문 순회, 분할/병합 판단, 출력 |

#### 도메인 분류

조문 단위 분할 후에도 도메인 분류는 **법령 전체 텍스트 기반**으로 수행. 같은 법령의 모든 조문은 동일 도메인으로 분류됨.

---

### 1-B. `preprocess_laws.py` — `process_interpretations()` Q&A 보존

**변경 전**: 질의요지 + 회답 + 이유를 하나의 content로 합침
**변경 후**: core(질의+회답) + reason(이유) 분리

#### 분리 전략

```
1. Core 청크: "[제목]\n\n질의요지:\n{질의}\n\n회답:\n{회답}"
   - id: INTERP_{item_id}
   - metadata.chunk_type: "core"
   - 절대 분리 금지

2. Reason 청크 (이유가 300자 이상일 때만):
   - id: INTERP_{item_id}_reason
   - content: "[제목]\n질의: {질의 앞 150자}...\n\n이유:\n{이유}"
   - metadata.chunk_type: "reason"
   - metadata.parent_id: INTERP_{item_id}
```

**근거**: 해석례에서 "질의요지"와 "회답"은 불가분의 관계. 분리되면 검색 시 "이 회답이 어떤 질의에 대한 것인지" 맥락이 유실됨. 이유(reason)는 보충 설명으로, 별도 검색 단위로도 유의미함.

---

### 1-C. `vectorstores/config.py` — 법률 파일 청킹 설정 변경

전처리에서 조문 단위로 분할 완료했으므로, 벡터 빌드 시 추가 청킹은 안전망 역할:

```python
"laws_full.jsonl": ChunkingConfig(chunk_size=2000, chunk_overlap=200),
"interpretations.jsonl": ChunkingConfig(chunk_size=2000, chunk_overlap=200),
```

`OPTIONAL_CHUNK_THRESHOLD`: 1500 → **3500** (전처리에서 MAX_ARTICLE_CHUNK=3000으로 제어)

---

### 2-A. `rag/utils/config.py` — format_context_length 상향

```python
# 변경 전
format_context_length: int = Field(default=500, ...)
source_content_length: int = Field(default=300, ...)

# 변경 후
format_context_length: int = Field(default=2000, ...)
source_content_length: int = Field(default=500, ...)
```

**근거**: 조문 단위 청크의 평균 길이는 500~2,000자. `format_context_length=500`이면 chunk_size를 올려도 LLM에 500자만 전달되어 개선 효과가 없음. 2,000으로 상향하여 조문 내용을 온전히 LLM에 전달.

**영향 범위**: `rag/chains/rag_chain.py:369`에서 `doc.page_content[:settings.format_context_length]`로 사용됨.

---

## Phase 2: 비법률 도메인 개선 (P1)

### 3-A. `preprocess_laws.py` — 판례 summary/detail 분리

**변경 전**: 판례 전문(`full_text`)이 5,000자 초과 시 `full_text[:5000]`으로 하드커트
**변경 후**: 판례 1건 → 2개 JSONL 레코드

```
1. Summary 청크 (항상 생성):
   - id: CASE_{item_id}_summary
   - content: 사건 헤더 + 판시사항 + 판결요지
   - metadata.chunk_type: "summary"
   - metadata.parent_id: CASE_{item_id}

2. Detail 청크 (full_text가 있을 때만):
   - id: CASE_{item_id}_detail
   - content: 사건 헤더 + 판례내용 전문 (하드커트 없음)
   - metadata.chunk_type: "detail"
   - metadata.parent_id: CASE_{item_id}
```

**근거**: 판결요지는 짧고 검색 적합성이 높음 → summary 청크로 분리. 판례 전문은 상세 근거가 필요할 때 활용 → detail 청크로 보존. 하드커트 제거로 판결 이유 후반부 유실 방지.

---

### 3-B. `loader.py` — 테이블 인식 splitter (`table_aware`)

`_split_with_table_awareness()` 메서드 추가. `extracted_documents_final.jsonl`에 적용.

#### 알고리즘

```
1. 텍스트를 행 단위로 순회하며 테이블 블록과 일반 텍스트 블록으로 분리
   - 테이블 행: "|"로 시작하고 "|"로 끝나는 연속 행
   - 일반 텍스트: 그 외

2. 블록을 chunk_size 이내로 병합:
   - 테이블 블록: 절대 분할하지 않음 (chunk_size 초과해도 보존)
   - 일반 텍스트: RecursiveCharacterTextSplitter로 분할
   - 테이블 + 주변 텍스트가 chunk_size 이내면 하나의 청크로 병합
```

#### config 설정

```python
"extracted_documents_final.jsonl": ChunkingConfig(
    chunk_size=1500, chunk_overlap=150, splitter_type="table_aware",
),
```

---

### 3-C. `loader.py` — Q&A 보존 splitter (`qa_aware`)

`_split_preserving_qa()` 메서드 추가. `labor_interpretation.jsonl`에 적용.

#### 알고리즘

```
1. "질의 :" / "회시 :" 패턴으로 텍스트를 블록 분리
2. 질의-회시 쌍을 하나의 단위로 보존
3. 쌍이 chunk_size 이내: 그대로 하나의 청크
4. 쌍이 chunk_size 초과:
   - 회시 부분만 RecursiveCharacterTextSplitter로 분할
   - 각 분할 청크에 질의를 prefix로 유지 (맥락 보존)
5. Q&A 패턴이 없으면 기본 splitter로 fallback
```

#### config 설정

```python
"labor_interpretation.jsonl": ChunkingConfig(
    chunk_size=1500, chunk_overlap=150, splitter_type="qa_aware",
),
```

---

### 3-D. 4대보험 파일명 통일

| 위치 | 변경 전 | 변경 후 |
|------|---------|---------|
| `vectorstores/config.py` FILE_TO_COLLECTION_MAPPING | `hr_major_insurance.jsonl` | `hr_4insurance_documents.jsonl`, `hr_insurance_edu.jsonl` |
| `vectorstores/config.py` FILE_CHUNKING_CONFIG | `hr_major_insurance.jsonl` | `hr_4insurance_documents.jsonl`, `hr_insurance_edu.jsonl` |
| `vectorstores/config.py` ChunkingConfig.OPTIONAL_CHUNK_FILES | `hr_major_insurance.jsonl` | `hr_4insurance_documents.jsonl`, `hr_insurance_edu.jsonl` |

실제 전처리 스크립트 출력:
- `preprocess_hr_insurance.py` → `hr_4insurance_documents.jsonl`
- `preprocess_hr_insurance_edu.py` → `hr_insurance_edu.jsonl`

---

### 3-E. chunk_size 전면 재검토

| 파일 | 변경 전 | 변경 후 | splitter | 근거 |
|------|---------|---------|----------|------|
| `laws_full.jsonl` | 800/100 | 2000/200 | default | 조문 단위 평균 500~2,000자, 안전망 |
| `interpretations.jsonl` | 800/100 | 2000/200 | default | Q&A 쌍 보존 |
| `court_cases_tax.jsonl` | 800/100 | 1500/150 | default | 판례 요지+이유 장문 |
| `court_cases_labor.jsonl` | 800/100 | 1500/150 | default | 판례 요지+이유 장문 |
| `extracted_documents_final.jsonl` | 800/100 | 1500/150 | table_aware | 테이블 포함 중문 |
| `labor_interpretation.jsonl` | 800/100 | 1500/150 | qa_aware | Q&A 쌍 보존 |
| `startup_procedures_filtered.jsonl` | 1000/200 | 1500/200 | default | 현행과 유사, 소폭 상향 |
| `hr_4insurance_documents.jsonl` | - (신규) | 1500/150 | default | 섹션 기반 |
| `hr_insurance_edu.jsonl` | - (신규) | 1500/150 | default | 섹션 기반 |

`OPTIONAL_CHUNK_THRESHOLD`: 1500 → **3500**

---

## Phase 3: Parent Document Retrieval 메타데이터 (P2)

현재 구현에서는 **메타데이터만 준비** (실제 retrieval 로직 구현은 향후 과제):

| 데이터 유형 | parent_id 형식 | 용도 |
|------------|---------------|------|
| 법령 조문 | `LAW_{law_id}` | 같은 법령의 다른 조문 추적 |
| 해석례 reason | `INTERP_{item_id}` | core ↔ reason 연결 |
| 판례 detail | `CASE_{item_id}` | summary ↔ detail 연결 |

향후 활용 시나리오:
- "근로기준법 제56조" 검색 → 해당 조문 + 같은 법령의 인접 조문 컨텍스트 제공
- 판례 summary 검색 → 연결된 detail 청크를 추가 컨텍스트로 활용

---

## 구현 순서 및 의존성

```
Phase 1 (P0 — 법률 + context length):
  ├─ 1-A. preprocess_laws.py — process_laws() 조문 단위 분할
  ├─ 1-B. preprocess_laws.py — process_interpretations() Q&A 보존
  ├─ 1-C. vectorstores/config.py — 법률 청킹 설정 변경
  └─ 2-A. rag/utils/config.py — format_context_length 상향

Phase 2 (P1 — 비법률 도메인):
  ├─ 3-A. preprocess_laws.py — process_court_cases() 판례 분리
  ├─ 3-B. loader.py — 테이블 인식 splitter 추가
  ├─ 3-C. loader.py — Q&A 보존 splitter 추가
  ├─ 3-D. vectorstores/config.py — 파일명 불일치 해결
  └─ 3-E. vectorstores/config.py — chunk_size 전면 재검토

Phase 3 (P2 — 메타데이터):
  └─ parent_id 메타데이터 일관 적용 (Phase 1, 2에서 함께 구현)
```

---

## 예상 문서 수 변화

| 컬렉션 | 변경 전 (추정) | 변경 후 (추정) | 변화 |
|--------|--------------|--------------|------|
| law_common_db | 법령 5,539건 → ~14,000 청크 | 조문 ~55,000건 | +294% |
| finance_tax_db | ~3,000 청크 | ~4,000 | +33% |
| hr_labor_db | ~3,000 청크 | ~3,500 | +17% |
| startup_funding_db | ~2,000 | ~2,000 | 변경 없음 |

**주의**: law_common_db의 문서 수가 크게 증가하므로 벡터DB 빌드 시간과 저장 용량 증가 예상.

---

## 검증 방법

### 전처리 검증

```bash
# 1. 전처리 실행
python scripts/preprocessing/preprocess_laws.py

# 2. 조문 단위 분할 확인 (레코드 수가 법령 수보다 크게 증가해야 함)
wc -l data/preprocessed/law/laws_full.jsonl

# 3. 해석례 Q&A 보존 확인
python -c "
import json
with open('data/preprocessed/law/interpretations.jsonl') as f:
    for line in f:
        doc = json.loads(line)
        if doc['metadata'].get('chunk_type') == 'core':
            assert '질의요지' in doc['content']
            assert '회답' in doc['content']
            print(f'OK: {doc[\"id\"]} - Q&A preserved')
            break
"

# 4. 판례 summary/detail 분리 확인
python -c "
import json
with open('data/preprocessed/law/court_cases_tax.jsonl') as f:
    for line in f:
        doc = json.loads(line)
        if '_summary' in doc['id']:
            print(f'Summary: {doc[\"id\"]}, len={len(doc[\"content\"])}')
        elif '_detail' in doc['id']:
            print(f'Detail: {doc[\"id\"]}, len={len(doc[\"content\"])}')
            break
"
```

### 벡터DB 빌드 및 테스트

```bash
# 벡터DB 재빌드
cd rag
.venv/Scripts/python -m vectorstores.build_vectordb --all --force

# RAG 테스트
.venv/Scripts/python -m pytest tests/ -v

# CLI 테스트 (수동)
.venv/Scripts/python -m main --cli
# → "근로기준법 제56조 내용 알려줘"
# → "최저임금 위반 시 처벌은?"
# → "법인세 세무조정이란?"
```

### 검색 품질 비교

개선 전/후 동일 질의에 대한 검색 결과를 비교:

| 질의 | 기대 변화 |
|------|----------|
| "근로기준법 제56조 내용" | 조문 단위로 정확히 검색 (vs 800자 청크에서 조문 일부만 검색) |
| "최저임금 위반 시 처벌" | 판례 summary에서 처벌 관련 요지 검색 |
| "연차유급휴가 해석례" | 질의-회답 쌍이 온전히 검색 |
| "부가세 신고 절차" | 테이블 포함 가이드가 온전히 검색 |

---

## 구현 상태

| 단계 | 상태 | 비고 |
|------|------|------|
| 1-A. 법령 조문 단위 분할 | **완료** | `_format_article_text`, `_split_large_article_by_clauses` 등 5개 함수 추가 |
| 1-B. 해석례 Q&A 보존 | **완료** | core/reason 분리, chunk_type 메타데이터 |
| 1-C. 법률 청킹 설정 변경 | **완료** | chunk_size=2000, overlap=200, threshold=3500 |
| 2-A. format_context_length 상향 | **완료** | 500→2000, 300→500 |
| 3-A. 판례 summary/detail 분리 | **완료** | 하드커트 제거, 2개 레코드 분리 |
| 3-B. 테이블 인식 splitter | **완료** | `_split_with_table_awareness()` |
| 3-C. Q&A 보존 splitter | **완료** | `_split_preserving_qa()` |
| 3-D. 파일명 통일 | **완료** | hr_major_insurance → hr_4insurance_documents + hr_insurance_edu |
| 3-E. chunk_size 전면 재검토 | **완료** | 전 파일 1500~2000으로 상향 |
| 테스트 | **완료** | 376 passed (11 failed는 기존 실패, 이번 변경과 무관) |
| 전처리 재실행 | **미실행** | 원본 데이터(law-raw/) 필요 |
| 벡터DB 재빌드 | **미실행** | 전처리 완료 후 실행 필요 |
