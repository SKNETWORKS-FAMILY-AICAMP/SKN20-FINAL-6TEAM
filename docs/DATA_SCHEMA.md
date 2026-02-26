# Bizi 데이터 통합 스키마

> 이 문서는 RAG 시스템에서 사용하는 모든 전처리 데이터의 스키마를 정의합니다.
> 모든 전처리기(`scripts/preprocessing/`)는 이 스키마를 따라야 합니다.

## 통합 스키마

모든 전처리된 문서는 동일한 JSON Lines(JSONL) 형식을 따릅니다.

```json
{
  "id": "TYPE_SOURCE_ID",
  "type": "law | interpretation | court_case | guide | announce | labor_qa",
  "domain": "startup_funding | finance_tax | hr_labor | legal",
  "title": "문서 제목 (사용자 표시용)",
  "content": "RAG 검색용 본문 (벡터/BM25 검색의 유일한 대상)",
  "source": {
    "name": "출처 기관명 (사용자 표시용)",
    "url": "원본 URL (사용자 표시용, nullable)",
    "collected_at": "2026-01-20T11:43:48"
  },
  "effective_date": "YYYY-MM-DD (optional)",
  "related_laws": ["근로기준법 제56조", "소득세법 제94조"],
  "metadata": {}
}
```

---

## 필드 설명

### 필수 필드

| 필드 | 타입 | 설명 |
|------|------|------|
| `id` | string | 문서 고유 ID (ID 체계 참조) |
| `type` | string | 문서의 **형식/종류** (law, court_case, guide 등) |
| `domain` | string | 문서의 **주제 분류** (4개 도메인 중 하나) |
| `title` | string | 제목 (사용자 표시용) |
| `content` | string | RAG 검색용 본문 |
| `source` | object | 출처 정보 |

### 선택 필드

| 필드 | 타입 | 설명 |
|------|------|------|
| `effective_date` | string | 시행일/마감일 (YYYY-MM-DD) |
| `related_laws` | string[] | 관련 법령 참조 목록 (예: `["근로기준법 제56조"]`) |
| `metadata` | object | 타입별 추가 데이터 (최소화 원칙) |

---

## domain 분류 규칙 (4개 도메인)

### domain 값과 에이전트/컬렉션 매핑

| JSONL `domain` | 컬렉션 키 (코드) | ChromaDB 컬렉션 | 검색 에이전트 |
|----------------|-----------------|-----------------|-------------|
| `startup_funding` | `startup_funding` | `startup_funding_db` | StartupFundingAgent |
| `finance_tax` | `finance_tax` | `finance_tax_db` | FinanceTaxAgent |
| `hr_labor` | `hr_labor` | `hr_labor_db` | HRLaborAgent |
| `legal` | `law_common` | `law_common_db` | 모든 에이전트 (공유) |

**`legal` vs `law_common` 관계**: JSONL의 `domain: "legal"`은 문서 주제(법령/해석례)를 의미합니다. 코드의 `law_common`은 컬렉션 내부 키입니다. 컬렉션 라우팅은 파일명 기반(`FILE_TO_COLLECTION_MAPPING`)이므로 이 차이가 검색에 영향을 주지 않습니다.

### domain 키워드 가이드

| domain | 설명 | 키워드 |
|--------|------|--------|
| `startup_funding` | 창업/지원사업/마케팅 | 창업, 사업자등록, 법인설립, 지원사업, 보조금, 공고, 마케팅 |
| `finance_tax` | 재무/세무/회계 | 세법, 소득세, 법인세, 부가가치세, 회계, 재무 |
| `hr_labor` | 인사/노무/법률 | 근로, 노동, 고용, 임금, 퇴직, 해고, 4대보험 |
| `legal` | 법령/법령해석 (공통) | 법률 전문, 해석례 (모든 에이전트가 공유) |

---

## type 분류 규칙 (6개 타입)

### type: 문서의 형식/종류

| type | 설명 | 예시 |
|------|------|------|
| `law` | 법령 전문 (법률 + 조문) | 근로기준법, 소득세법 |
| `interpretation` | 법령해석례, 행정해석 | 고용노동부 해석례, 기획재정부 해석례 |
| `court_case` | 판례 (법원 판결) | 대법원 판례, 행정법원 판례 |
| `guide` | 가이드/매뉴얼 | 창업 가이드, 세제지원 가이드, 4대보험 가이드 |
| `announce` | 지원사업 공고 | 기업마당 공고, K-Startup 공고 |
| `labor_qa` | 노동 질의회시 (Q&A) | 근로기준법 질의회시집 |

### type과 domain 혼동 주의

type은 **문서 형식**, domain은 **주제 분류**입니다. 두 값은 독립적입니다.

| 예시 | type | domain | 설명 |
|------|------|--------|------|
| 근로기준법 전문 | `law` | `legal` | 법령(형식)이고 법령공통(주제) |
| 소득세법 전문 | `law` | `legal` | 법령(형식)이고 법령공통(주제) |
| 세무 판례 | `court_case` | `finance_tax` | 판례(형식)이고 세무(주제) |
| 노동 판례 | `court_case` | `hr_labor` | 판례(형식)이고 노동(주제) |
| 창업 가이드 | `guide` | `startup_funding` | 가이드(형식)이고 창업(주제) |
| 세제지원 가이드 | `guide` | `finance_tax` | 가이드(형식)이고 세무(주제) |
| 4대보험 가이드 | `guide` | `hr_labor` | 가이드(형식)이고 노동(주제) |
| 지원사업 공고 | `announce` | `startup_funding` | 공고(형식)이고 창업(주제) |
| 노동 해석례 | `interpretation` | `legal` | 해석례(형식)이고 법령공통(주제) |

> **현재 데이터 참고**: 기존 전처리 데이터에는 domain에 `tax`, `labor`, `startup`, `funding`, `legal` 등 구(舊) 값이 사용된 레코드가 있습니다. 새 전처리기 개발 시에는 4-domain 규칙을 따르되, 기존 데이터는 별도 마이그레이션 작업에서 수정합니다. RAG 시스템은 컬렉션 라우팅을 파일명 기반으로 하므로 기존 데이터의 domain 불일치가 검색에 직접적 영향을 주지 않습니다.

---

## 파일별 domain 매핑

| 파일 | 현재 domain | 새 domain | 컬렉션 |
|------|------------|-----------|--------|
| `laws_full.jsonl` | `tax` (오류) | `legal` | law_common_db |
| `interpretations.jsonl` | `legal` | `legal` | law_common_db |
| `court_cases_tax.jsonl` | `tax` | `finance_tax` | finance_tax_db |
| `extracted_documents_final.jsonl` | `guide` (오류) | `finance_tax` | finance_tax_db |
| `court_cases_labor.jsonl` | `court_case` (오류) | `hr_labor` | hr_labor_db |
| `labor_interpretation.jsonl` | `labor` | `hr_labor` | hr_labor_db |
| `hr_major_insurance.jsonl` | `guide` (오류) | `hr_labor` | hr_labor_db |
| `announcements.jsonl` | `funding` | `startup_funding` | startup_funding_db |
| `industry_startup_guide_filtered.jsonl` | `startup` | `startup_funding` | startup_funding_db |
| `startup_procedures_filtered.jsonl` | `startup` | `startup_funding` | startup_funding_db |

---

## ID 체계

각 문서 타입별 고유 ID 형식입니다. 중복을 방지하기 위해 반드시 이 형식을 따라야 합니다.

| 타입 | ID 형식 | 예시 |
|------|---------|------|
| 법령 | `LAW_{law_id}` | `LAW_010719` |
| 해석례 | `INTERP_{id}` | `INTERP_313107` |
| 판례 | `CASE_{id}` | `CASE_613209` |
| 공고 | `ANNOUNCE_{source}_{id}` | `ANNOUNCE_BIZINFO_PBLN_000000000117858` |
| 창업 가이드 | `STARTUP_GUIDE_{업종코드}` | `STARTUP_GUIDE_011000` |
| 창업 절차 | `STARTUP_PROCEDURES_{id}` | `STARTUP_PROCEDURES_1009` |
| 질의회시 | `INTER_C{장}_S{절}_{순번}` | `INTER_C01_S01_01` |
| 세제지원 가이드 | `TAX_GUIDE_{순번}` | `TAX_GUIDE_001` |
| 4대보험 가이드 | `MAJOR_INSURANCE_HR_{순번}` | `MAJOR_INSURANCE_HR_1` |

> **현재 데이터 참고**: 기존 데이터에 `MAGOR_INSURNACE_HR_*` 등 오타가 포함된 ID가 있습니다. 새 전처리기에서는 위 규칙을 따르세요.

---

## 사용자 표시 정보

`title`, `source.name`, `source.url` 3가지가 **사용자 표시용 핵심 필드**입니다.

| 필드 | 용도 | 예시 |
|------|------|------|
| `title` | 검색 결과 제목 표시 | "근로기준법", "2026년 창업성장기술개발사업" |
| `source.name` | 출처 기관명 (신뢰성 판단) | "국세청", "국가법령정보센터", "기업마당", "대법원" |
| `source.url` | 원본 문서 URL (향후 출처 링크 표시) | `https://law.go.kr/...`, `null` 허용 |

### 현재 RAG 파이프라인 활용 상태

| JSONL 필드 | ChromaDB 저장 | RAG 응답 전달 | Frontend 표시 |
|-----------|--------------|--------------|-------------|
| `title` | `metadata.title` | `SourceDocument.title` | O |
| `source.name` | `metadata.source_name` | `SourceDocument.source` | O |
| `source.url` | `metadata.source_url` | 미포함 (코드 미구현) | X (향후 구현) |

이 3가지 필드는 모든 전처리기에서 **가능한 한 반드시 채워야** 합니다.

---

## metadata 설계 규칙

### 설계 원칙

- **ChromaDB 호환**: `str | int | float | bool`만. `list | dict | None` 금지
- **목적 중심**: 필터링 가능한 필드만 metadata에 보존
- **검색 정보는 content에**: 벡터/BM25 검색에 필요한 정보는 content에 포함
- **표시 정보는 top-level에**: title, source.url은 이미 top-level 필드

### 타입별 허용 metadata 필드 (최소화)

| type | metadata 필드 | 용도 |
|------|--------------|------|
| `law` | `law_id: str` | 법령 식별/중복제거 |
| `interpretation` | `case_no: str` | 사건번호 인용 |
| `court_case` | `case_no: str`, `court_name: str` | 인용, 필터링 가능 |
| `guide` | `industry_code: str` | 기업 프로필 매칭 |
| `announce` | `region: str`, `support_type: str` | 지역/유형 필터링 |
| `labor_qa` | (없음) | 필터 유용 필드 없음 |

### metadata에 넣지 말아야 할 것

다음 필드들은 검색/표시 코드에서 조회되지 않으므로 metadata에 포함하지 않습니다:

| 제거 대상 | 이유 |
|-----------|------|
| `ministry`, `enforcement_date`, `article_count` | 법령 기본 정보 — 검색/필터 미사용 |
| `answer_date`, `answer_org`, `question_org` | 해석례 부가 정보 — content에 포함하면 충분 |
| `court_type`, `decision_type`, `decision`, `category`, `reference` | 판례 부가 정보 — content에 포함, reference는 HTML 포함 긴 문자열 |
| `chapter`, `chapter_title`, `section`, `section_title`, `qa_count` | 문서 구조 정보 — 검색/필터 미사용 |
| `organization`, `target_type`, `apply_method`, `contact`, `target`, `exclusion`, `amount` | 공고 상세 정보 — content에 포함하면 벡터 검색 가능 |
| `hashtags` (list), `sections` (list), `related_laws` (list) | 복합 타입 — ChromaDB 미저장 |
| `start_date`, `end_date` | 기간 정보 — effective_date에 마감일 저장, content에 기간 포함 |

### metadata 저장 매핑

`metadata` 객체의 값은 ChromaDB에 `meta_` 접두사로 저장됩니다.

```json
// JSONL
"metadata": {
  "region": "경기",           // -> meta_region (저장됨)
  "support_type": "기술개발"   // -> meta_support_type (저장됨)
}
```

---

## related_laws 형식

### 변경: `object[]` -> `string[]` (optional)

```json
// Before (복잡한 구조, law_id가 대부분 null)
"related_laws": [
  {"law_id": "LAW_010719", "law_name": "근로기준법", "article_ref": "제56조"}
]

// After (단순 문자열 배열)
"related_laws": ["근로기준법 제56조"]
```

- **Optional**: 관련 법령이 없으면 필드 자체를 생략
- **ChromaDB 미저장**: list 타입이므로 ChromaDB에 저장 안 됨 (기존과 동일)
- **content 포함 필수**: 검색에 필요하면 content에 `[관련법령] 근로기준법 제56조` 형태로 포함

---

## content 필드 RAG 최적화 가이드

`content` 필드는 벡터 임베딩과 BM25 키워드 검색의 **유일한 대상**입니다. `title`은 메타데이터로만 저장되고 검색에 사용되지 않으므로, 검색에 필요한 모든 정보는 content에 포함해야 합니다.

### 공통 원칙

1. **title을 content 상단에 포함**: title이 벡터 임베딩에 포함되지 않으므로, content 첫 줄에 제목을 넣어야 청킹 후에도 문맥이 유지됨
2. **검색 키워드를 content에 포함**: 메타데이터(지역, 대상, 금액 등)에만 저장하면 벡터/BM25 검색으로 찾을 수 없음
3. **구조화된 마커 사용**: `[섹션명]`, `질의요지:`, `회답:` 등의 마커로 내용 구분

### 타입별 content 구조 가이드

#### 공고(announce)

검색 키워드가 될 핵심 메타데이터를 content 상단에 포함합니다.

```
[공고명] 2026년 창업성장기술개발사업
[주관기관] 중소벤처기업부
[지역] 전국
[지원대상] 창업 7년 이내 중소기업
[지원유형] 기술개발
[지원금액] 최대 3억원
[신청기간] 2026-01-15 ~ 2026-02-28
[신청방법] 온라인 접수

사업 개요: ...
지원 내용 상세: ...
```

#### 법령(law)

조문 번호 앞에 줄바꿈을 넣어 청킹 시 조문 단위 분할을 유도합니다.

```
[근로기준법]

제1조(목적) 이 법은 헌법에 따라 근로조건의 기준을 정함으로써...

제2조(정의) ... 이 법에서 사용하는 용어의 뜻은 다음과 같다...

제3조(근로조건의 기준) 이 법에서 정하는 근로조건은 최저기준이므로...
```

#### 해석례/질의회시(interpretation, labor_qa)

Q&A 구조를 명확히 표시합니다.

```
[제목] 연장근로수당 산정 기준

[질의]
통상임금에 포함되는 수당의 범위는 어떻게 되나요?

[회시]
통상임금이란 근로자에게 정기적이고 일률적으로 소정근로 또는 총근로에 대하여 지급하기로 정한 금품을 말합니다...
```

#### 판례(court_case)

사건 핵심 정보를 상단에 요약합니다.

```
[사건번호] 2023다12345
[법원] 대법원
[판결일] 2024-03-15
[주제] 부당해고 무효 확인

[주문]
원심판결을 파기하고...

[이유]
1. 사건의 경위...
2. 판단...
```

#### 가이드(guide)

섹션 마커로 구조화합니다.

```
[음식점업 창업 가이드]

[개요]
음식점업은 한국표준산업분류상 '음식점 및 주점업'에 해당하며...

[인허가]
영업신고: 관할 구청에 영업신고서 제출...
위생교육: 한국식품위생교육원에서 위생교육 이수...

[필요자금]
초기 투자비용: 임차보증금, 인테리어, 설비 등...
```

---

## 메타데이터와 RAG 시스템

### ChromaDB에 저장되는 메타데이터

JSONL의 각 필드가 ChromaDB에 다음과 같이 저장됩니다:

| JSONL 필드 | ChromaDB 저장 | 설명 |
|-----------|---------------|------|
| `content` | `page_content` | 벡터 임베딩 + BM25 검색 대상 |
| `id` | `metadata.id` | 문서 ID (청크 시 `{id}_{chunk_index}`) |
| `type` | `metadata.type` | 문서 형식 |
| `domain` | `metadata.domain` | 주제 분류 |
| `title` | `metadata.title` | 제목 (검색 미사용, 출처 표시용) |
| `source.name` | `metadata.source_name` | 출처 기관명 (출처 표시용) |
| `source.url` | `metadata.source_url` | 출처 URL (향후 출처 링크용) |
| `source.collected_at` | `metadata.collected_at` | 수집 일시 |
| `effective_date` | `metadata.effective_date` | 시행일/마감일 |
| `metadata.*` | `metadata.meta_*` | 추가 메타데이터 (`meta_` 접두사) |
| `related_laws` | 저장 안 됨 | list 타입이므로 ChromaDB 미저장 |
| (자동 생성) | `metadata.source_file` | 원본 JSONL 파일명 |
| (청크 시) | `metadata.chunk_index` | 청크 순번 |
| (청크 시) | `metadata.original_id` | 원본 문서 ID |

### 검색에 활용되는 필드

| 필드 | 활용 방식 |
|------|----------|
| `content` (page_content) | 벡터 임베딩 검색 + BM25 키워드 검색 + Re-ranking |
| `title` | 응답 포맷팅 시 출처 표시 |
| `source_name` | 응답 포맷팅 시 출처 인용 |

### 검색에 활용되지 않는 필드 (저장만 됨)

| 필드 | 비고 |
|------|------|
| `type`, `domain` | 컬렉션 라우팅은 파일명 기반. 향후 메타데이터 필터링 가능 |
| `effective_date` | 저장만 되고 날짜 필터링 미구현 |
| `source_url` | 저장만 됨. 향후 Frontend 출처 링크에 활용 예정 |
| `meta_*` | 저장만 됨. 향후 필터링 가능 |

---

## 날짜 형식 규칙

| 필드 | 형식 | 예시 |
|------|------|------|
| `effective_date` | `YYYY-MM-DD` | `2026-02-28` |
| `source.collected_at` | ISO 8601 | `2026-01-20T11:43:48` |

기간이 있는 경우 (예: 공고 신청기간) `effective_date`에 마감일을 저장하고, 시작일/종료일은 content에 포함합니다.

---

## 타입별 상세 스키마

### law (법령)

```json
{
  "id": "LAW_010719",
  "type": "law",
  "domain": "legal",
  "title": "근로기준법",
  "content": "[근로기준법]\n\n제1조(목적) 이 법은 헌법에 따라...\n\n제2조(정의)...",
  "source": {
    "name": "국가법령정보센터",
    "url": "https://law.go.kr/법령/근로기준법",
    "collected_at": "2026-01-20T11:43:48"
  },
  "effective_date": "2024-02-09",
  "metadata": {
    "law_id": "010719"
  }
}
```

### interpretation (해석례)

```json
{
  "id": "INTERP_313107",
  "type": "interpretation",
  "domain": "legal",
  "title": "연장근로수당 산정 기준",
  "content": "[연장근로수당 산정 기준]\n\n[질의]\n통상임금에 포함되는 수당의 범위는?\n\n[회시]\n통상임금이란...",
  "source": {
    "name": "고용노동부",
    "url": "https://...",
    "collected_at": "2026-01-20T11:43:48"
  },
  "related_laws": ["근로기준법 제56조"],
  "metadata": {
    "case_no": "근로기준정책과-5076"
  }
}
```

### labor_qa (노동 질의회시)

```json
{
  "id": "INTER_C01_S01_01",
  "type": "labor_qa",
  "domain": "hr_labor",
  "title": "연장근로 계산 방법",
  "content": "[연장근로 계산 방법]\n\n[질의]\n연장근로수당은 어떻게 계산하나요?\n\n[회시]\n연장근로수당은...",
  "source": {
    "name": "근로기준법 질의회시집",
    "url": null,
    "collected_at": "2026-01-20T11:43:48"
  },
  "metadata": {}
}
```

### court_case (판례)

```json
{
  "id": "CASE_613209",
  "type": "court_case",
  "domain": "finance_tax",
  "title": "양도소득세 부과처분 취소",
  "content": "[사건번호] 2023두12345\n[법원] 대법원\n[판결일] 2024-03-15\n\n[주문]\n원심판결을 파기하고...\n\n[이유]\n...",
  "source": {
    "name": "대법원",
    "url": "https://...",
    "collected_at": "2026-01-20T11:43:48"
  },
  "related_laws": ["소득세법 제94조"],
  "metadata": {
    "case_no": "2023두12345",
    "court_name": "대법원"
  }
}
```

### guide (가이드)

```json
{
  "id": "STARTUP_GUIDE_011000",
  "type": "guide",
  "domain": "startup_funding",
  "title": "음식점업 창업 가이드",
  "content": "[음식점업 창업 가이드]\n\n[개요]\n음식점업은...\n\n[인허가]\n영업신고...",
  "source": {
    "name": "창업진흥원",
    "url": "https://...",
    "collected_at": "2026-01-20T11:43:48"
  },
  "metadata": {
    "industry_code": "011000"
  }
}
```

### announce (지원사업 공고)

```json
{
  "id": "ANNOUNCE_BIZINFO_PBLN_000000000117858",
  "type": "announce",
  "domain": "startup_funding",
  "title": "2026년 창업성장기술개발사업",
  "content": "[공고명] 2026년 창업성장기술개발사업\n[주관기관] 중소벤처기업부\n[지역] 전국\n[지원대상] 창업 7년 이내 중소기업\n[지원유형] 기술개발\n[지원금액] 최대 3억원\n[신청기간] 2026-01-15 ~ 2026-02-28\n\n사업 개요: ...",
  "source": {
    "name": "기업마당",
    "url": "https://www.bizinfo.go.kr/...",
    "collected_at": "2026-01-20T11:43:48"
  },
  "effective_date": "2026-02-28",
  "metadata": {
    "region": "전국",
    "support_type": "기술개발"
  }
}
```

> 지원사업 공고는 지역/대상/금액 등 핵심 메타데이터를 **content에 포함**해야 벡터 검색으로 찾을 수 있습니다. metadata에는 필터링용 `region`, `support_type`만 저장합니다.

---

## 출력 파일 위치

### 실제 파일 목록

| 경로 | 컬렉션 | 청킹 | 레코드 수 |
|------|--------|------|-----------|
| `data/preprocessed/law/laws_full.jsonl` | law_common_db | 조건부 | 5,539 |
| `data/preprocessed/law/interpretations.jsonl` | law_common_db | 조건부 | 8,604 |
| `data/preprocessed/finance/court_cases_tax.jsonl` | finance_tax_db | 필수 | 1,949 |
| `data/preprocessed/finance/extracted_documents_final.jsonl` | finance_tax_db | 필수 | 124 |
| `data/preprocessed/labor/court_cases_labor.jsonl` | hr_labor_db | 필수 | 981 |
| `data/preprocessed/labor/labor_interpretation.jsonl` | hr_labor_db | 조건부 | 399 |
| `data/preprocessed/labor/hr_major_insurance.jsonl` | hr_labor_db | 조건부 | 5 |
| `data/preprocessed/startup_support/announcements.jsonl` | startup_funding_db | 안 함 | 510 |
| `data/preprocessed/startup_support/industry_startup_guide_filtered.jsonl` | startup_funding_db | 안 함 | 1,589 |
| `data/preprocessed/startup_support/startup_procedures_filtered.jsonl` | startup_funding_db | 조건부 | 10 |

**총 레코드: 19,710건**

### 컬렉션-파일 매핑 상세

컬렉션 라우팅은 `rag/vectorstores/config.py`의 `FILE_TO_COLLECTION_MAPPING`으로 관리됩니다.

| 컬렉션 | 파일 | domain |
|--------|------|--------|
| `startup_funding_db` | announcements, industry_startup_guide_filtered, startup_procedures_filtered | `startup_funding` |
| `finance_tax_db` | court_cases_tax, extracted_documents_final | `finance_tax` |
| `hr_labor_db` | court_cases_labor, labor_interpretation, hr_major_insurance | `hr_labor` |
| `law_common_db` | laws_full, interpretations | `legal` |

### 청킹 전략

`rag/vectorstores/config.py`의 `ChunkingConfig` 참조:

| 유형 | 설정 | 대상 파일 |
|------|------|----------|
| 청킹 안 함 | - | announcements, industry_startup_guide_filtered |
| 조건부 청킹 | content > 1500자 시 적용 | laws_full, interpretations, labor_interpretation, hr_major_insurance, startup_procedures_filtered |
| 필수 청킹 | 항상 적용 | court_cases_tax, extracted_documents_final, court_cases_labor |

기본 청킹 설정: `chunk_size=800`, `chunk_overlap=100`, 구분자: `["\n\n", "\n", ".", " "]`

---

## 데이터 품질 검증

### 검증 체크리스트

- [ ] 모든 JSONL 레코드가 통합 스키마 준수
- [ ] 필수 필드 (id, type, domain, title, content, source) 존재
- [ ] ID 형식 규칙 준수 (중복 없음)
- [ ] type은 문서 형식, domain은 주제 분류 (혼동 없음)
- [ ] domain이 4개 값 중 하나 (`startup_funding | finance_tax | hr_labor | legal`)
- [ ] content에 title/핵심 메타데이터 포함 (벡터 검색 품질)
- [ ] content의 Q&A 구조에 `[질의]`/`[회시]` 마커 사용
- [ ] 날짜 형식 `YYYY-MM-DD` 준수
- [ ] `related_laws`가 `string[]` 형식 (예: `["근로기준법 제56조"]`)
- [ ] 한글 인코딩 정상 (UTF-8)
- [ ] metadata 값이 기본 타입(`str`, `int`, `float`, `bool`)만 포함
- [ ] metadata에 불필요한 필드 없음 (타입별 허용 필드만)
- [ ] `title`, `source.name` 비어있지 않음

### 검증 명령어

```bash
# JSONL 형식 확인
head -3 data/preprocessed/law/laws_full.jsonl | python3 -m json.tool

# 레코드 수 확인
wc -l data/preprocessed/*/*.jsonl

# ID 중복 확인
jq -r '.id' data/preprocessed/law/laws_full.jsonl | sort | uniq -d

# domain 값 분포 확인
jq -r '.domain' data/preprocessed/*/*.jsonl | sort | uniq -c | sort -rn

# metadata 키 확인 (불필요 필드 탐지)
jq -r '.metadata | keys[]' data/preprocessed/*/*.jsonl 2>/dev/null | sort | uniq -c | sort -rn
```

---

## 참고 문서

- [LAW_DATA_PIPELINE.md](./LAW_DATA_PIPELINE.md) - 법률 데이터 전처리 파이프라인 (원본 구조, 정제 과정, 도메인 분류)
- [scripts/CLAUDE.md](../scripts/CLAUDE.md) - 크롤링/전처리 스크립트 개발 가이드
- [data/CLAUDE.md](../data/CLAUDE.md) - 데이터 폴더 개발 가이드
- [rag/CLAUDE.md](../rag/CLAUDE.md) - RAG 시스템 개발 가이드
- [rag/vectorstores/config.py](../rag/vectorstores/config.py) - 벡터DB 설정 (컬렉션 매핑, 청킹)
