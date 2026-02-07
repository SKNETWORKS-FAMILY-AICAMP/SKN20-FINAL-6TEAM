# Data - 데이터 저장소

> **이 문서는 Claude Code를 위한 자기 완결적 개발 가이드입니다.**
> 다른 AI 에이전트는 [AGENTS.md](./AGENTS.md)를 참조하세요.

## 개요

Bizi RAG 시스템에서 사용하는 모든 데이터를 저장하는 폴더입니다.
- `origin/`: 원본 데이터 (크롤링 결과, PDF 파일 등)
- `preprocessed/`: 전처리된 데이터 (JSONL 형식, RAG 입력용)

## 프로젝트 구조

```
data/
├── CLAUDE.md                  # 이 파일
├── AGENTS.md                  # AI 에이전트 개발 가이드
│
├── origin/                    # 원본 데이터 (크롤링/다운로드)
│   ├── 근로기준법 질의회시집.pdf
│   ├── law/                   # 법령 원본 (법령정보센터)
│   ├── startup_support/       # 창업 가이드 원본
│   ├── finance/               # 세무/회계 원본
│   └── labor/                 # 노동/인사 원본
│
└── preprocessed/              # 전처리된 데이터 (JSONL)
    ├── law/                   # 법령, 해석례
    │   ├── laws_full.jsonl           # 법령 전문 (5,539건)
    │   └── interpretations.jsonl     # 법령해석례 (8,604건)
    ├── finance/               # 세무 판례, 세제지원 가이드
    │   ├── court_cases_tax.jsonl            # 세무 판례 (1,949건)
    │   └── extracted_documents_final.jsonl  # 세제지원 가이드 (124건)
    ├── labor/                 # 노동 판례, 질의회시, 4대보험
    │   ├── court_cases_labor.jsonl      # 노동 판례 (981건)
    │   ├── labor_interpretation.jsonl   # 질의회시 (399건)
    │   └── hr_major_insurance.jsonl     # 4대보험 가이드 (5건)
    └── startup_support/       # 공고, 창업 가이드
        ├── announcements.jsonl                    # 지원사업 공고 (510건)
        ├── industry_startup_guide_filtered.jsonl  # 업종별 창업 가이드 (1,589건)
        └── startup_procedures_filtered.jsonl      # 창업 절차 (10건)
```

## 데이터 흐름
외부 소스 → `scripts/crawling/` → `data/origin/` → `scripts/preprocessing/` → `data/preprocessed/` → `rag/vectorstores/` → ChromaDB
상세 다이어그램: [scripts/CLAUDE.md](../scripts/CLAUDE.md) 참조

---

## origin/ (원본 데이터)

크롤링 또는 다운로드한 원본 데이터입니다.

### 파일 목록

| 경로 | 형식 | 설명 |
|------|------|------|
| `근로기준법 질의회시집.pdf` | PDF | 고용노동부 질의회시집 (2018-2023) |
| `law/01_laws_full.json` | JSON | 전체 법령 (5,539건, 304MB) |
| `law/expc_전체.json` | JSON | 법령해석례 (8,604건) |
| `law/prec_labor.json` | JSON | 노동 판례 |
| `law/prec_tax.json` | JSON | 세무 판례 |
| `startup_support/startup_guide_complete.json` | JSON | 업종별 창업 가이드 (1,589건) |
| `startup_support/startup_procedures.json` | JSON | 창업 절차 가이드 |
| `finance/국세청_세무일정.csv` | CSV | 세무 신고 일정 (238건) |
| `finance/2025 중소기업세제·세정지원.pdf` | PDF | 세제 지원 가이드 |
| `labor/4대보험 신고.pdf` | PDF | 4대보험 가이드 |

---

## preprocessed/ (전처리 데이터)

RAG 시스템에 입력되는 통합 스키마 형식의 JSONL 파일입니다.

### 통합 스키마

상세 스키마 정의는 [docs/DATA_SCHEMA.md](../docs/DATA_SCHEMA.md)를 참조하세요.

**필수 필드**: `id`, `type`, `domain`, `title`, `content`, `source`

**핵심 규칙**:
- `type`은 문서 형식 (law, court_case, guide, announce 등)
- `domain`은 주제 분류 (**4개**: `startup_funding | finance_tax | hr_labor | legal`)
- `content`가 벡터 검색의 **유일한 대상** — 검색에 필요한 정보는 반드시 content에 포함
- `related_laws`는 `string[]` 형식 (예: `["근로기준법 제56조"]`), optional
- `metadata`는 타입별 최소 필드만 포함 (ChromaDB 호환 타입만)

### domain-컬렉션 매핑

| domain | 컬렉션 | 에이전트 |
|--------|--------|---------|
| `startup_funding` | startup_funding_db | StartupFundingAgent |
| `finance_tax` | finance_tax_db | FinanceTaxAgent |
| `hr_labor` | hr_labor_db | HRLaborAgent |
| `legal` | law_common_db | 모든 에이전트 (공유) |

---

## 출력 파일 상세

### law/laws_full.jsonl

법령 전문 (법률 + 조문). 컬렉션: `law_common_db`

```json
{
  "id": "LAW_010719",
  "type": "law",
  "domain": "legal",
  "title": "근로기준법",
  "content": "[근로기준법]\n\n제1조(목적) 이 법은 헌법에 따라...\n\n제2조(정의)...",
  "metadata": {
    "law_id": "010719"
  }
}
```

### law/interpretations.jsonl

법령해석례 (법제처, 국세청 등). 컬렉션: `law_common_db`

```json
{
  "id": "INTERP_313107",
  "type": "interpretation",
  "domain": "legal",
  "title": "연장근로수당 산정 기준",
  "content": "[연장근로수당 산정 기준]\n\n[질의]\n통상임금에 포함되는 수당의 범위는?\n\n[회시]\n통상임금이란...",
  "related_laws": ["근로기준법 제56조"],
  "metadata": {
    "case_no": "근로기준정책과-5076"
  }
}
```

### finance/court_cases_tax.jsonl

세무 판례. 컬렉션: `finance_tax_db`

```json
{
  "id": "CASE_613209",
  "type": "court_case",
  "domain": "finance_tax",
  "title": "양도소득세 부과처분 취소",
  "content": "[사건번호] 2023두12345\n[법원] 대법원\n[판결일] 2024-03-15\n\n[주문]\n...\n\n[이유]\n...",
  "metadata": {
    "case_no": "2023두12345",
    "court_name": "대법원"
  }
}
```

### finance/extracted_documents_final.jsonl

세제지원 가이드 (PDF 추출). 컬렉션: `finance_tax_db`

```json
{
  "id": "TAX_GUIDE_001",
  "type": "guide",
  "domain": "finance_tax",
  "title": "중소기업 세제 지원 안내",
  "content": "[중소기업 세제 지원 안내]\n\n..."
}
```

### labor/court_cases_labor.jsonl

노동 판례. 컬렉션: `hr_labor_db`

```json
{
  "id": "CASE_612991",
  "type": "court_case",
  "domain": "hr_labor",
  "title": "부당해고 무효 확인",
  "content": "[사건번호] 2023다12345\n[법원] 대법원\n\n[주문]\n...\n\n[이유]\n...",
  "metadata": {
    "case_no": "2023다12345",
    "court_name": "대법원"
  }
}
```

### labor/labor_interpretation.jsonl

노동 질의회시 (PDF 추출). 컬렉션: `hr_labor_db`

```json
{
  "id": "INTER_C01_S01_01",
  "type": "labor_qa",
  "domain": "hr_labor",
  "title": "연장근로 계산 방법",
  "content": "[연장근로 계산 방법]\n\n[질의]\n연장근로수당은 어떻게 계산하나요?\n\n[회시]\n연장근로수당은...",
  "metadata": {}
}
```

### labor/hr_major_insurance.jsonl

4대보험 가이드 (PDF 추출). 컬렉션: `hr_labor_db`

```json
{
  "id": "MAJOR_INSURANCE_HR_1",
  "type": "guide",
  "domain": "hr_labor",
  "title": "4대보험 신고 가이드",
  "content": "[4대보험 신고 가이드]\n\n..."
}
```

### startup_support/announcements.jsonl

지원사업 공고. 컬렉션: `startup_funding_db`. 청킹 안 함.

```json
{
  "id": "ANNOUNCE_BIZINFO_PBLN_000000000117858",
  "type": "announce",
  "domain": "startup_funding",
  "title": "2026년 창업성장기술개발사업",
  "content": "[공고명] 2026년 창업성장기술개발사업\n[주관기관] 중소벤처기업부\n[지역] 전국\n[지원대상] 창업 7년 이내 중소기업\n[지원금액] 최대 3억원\n\n사업 개요: ...",
  "effective_date": "2026-02-28",
  "metadata": {
    "region": "전국",
    "support_type": "기술개발"
  }
}
```

> 지원사업 공고는 content에 지역/대상/금액 등 핵심 메타데이터를 포함해야 벡터 검색으로 찾을 수 있습니다.

### startup_support/industry_startup_guide_filtered.jsonl

업종별 창업 가이드. 컬렉션: `startup_funding_db`. 청킹 안 함.

```json
{
  "id": "STARTUP_GUIDE_011000",
  "type": "guide",
  "domain": "startup_funding",
  "title": "음식점업 창업 가이드",
  "content": "[음식점업 창업 가이드]\n\n[개요]\n음식점업은...\n\n[인허가]\n영업신고...",
  "metadata": {
    "industry_code": "011000"
  }
}
```

### startup_support/startup_procedures_filtered.jsonl

창업 절차 가이드. 컬렉션: `startup_funding_db`

```json
{
  "id": "STARTUP_PROCEDURES_1009",
  "type": "guide",
  "domain": "startup_funding",
  "title": "법인설립 절차 가이드",
  "content": "[법인설립 절차 가이드]\n\n..."
}
```

---

## 데이터 품질 검증

### 검증 체크리스트

- [ ] 모든 JSONL 레코드가 통합 스키마 준수
- [ ] 필수 필드 (id, type, domain, title, content, source) 존재
- [ ] ID 형식 규칙 준수 (중복 없음)
- [ ] type은 문서 형식, domain은 주제 분류 (혼동 없음)
- [ ] domain이 4개 값 중 하나 (`startup_funding | finance_tax | hr_labor | legal`)
- [ ] content에 title 포함 (벡터 검색 시 제목으로 검색 가능하도록)
- [ ] content에 검색 키워드 포함 (공고의 지역/대상/금액 등)
- [ ] `related_laws`가 `string[]` 형식 (object[] 아님)
- [ ] 한글 인코딩 정상 (깨짐 없음)
- [ ] metadata에 타입별 허용 필드만 포함 (불필요 필드 없음)
- [ ] metadata 값이 기본 타입만 포함 (list/dict는 ChromaDB 미저장)
- [ ] `title`, `source.name` 비어있지 않음

### 실제 레코드 수

| 파일 | 레코드 수 |
|------|-----------|
| laws_full.jsonl | 5,539 |
| interpretations.jsonl | 8,604 |
| court_cases_tax.jsonl | 1,949 |
| court_cases_labor.jsonl | 981 |
| announcements.jsonl | 510 |
| labor_interpretation.jsonl | 399 |
| extracted_documents_final.jsonl | 124 |
| startup_procedures_filtered.jsonl | 10 |
| hr_major_insurance.jsonl | 5 |
| industry_startup_guide_filtered.jsonl | 1,589 |
| **합계** | **19,710** |

---

## 주의사항

### .gitignore 설정

대용량 원본 데이터는 git에서 제외합니다:

```gitignore
# data/.gitignore
origin/law/*.json
origin/**/*.pdf
origin/**/*.csv
```

### 인코딩

- 모든 파일은 UTF-8 인코딩
- CSV 파일은 EUC-KR인 경우 변환 필요

### 용량

- `origin/law/01_laws_full.json`: 304MB
- 전체 origin: ~500MB
- 전체 preprocessed: ~300MB

---

## 참고 문서

- [docs/DATA_SCHEMA.md](../docs/DATA_SCHEMA.md) - 통합 스키마 정의 (4-domain 규칙, metadata 최소화, content 구조 가이드)
- [scripts/CLAUDE.md](../scripts/CLAUDE.md) - 크롤링/전처리 스크립트 가이드
- [scripts/data_pipeline.md](../scripts/data_pipeline.md) - 전처리 파이프라인 상세 설명
- [rag/CLAUDE.md](../rag/CLAUDE.md) - RAG 시스템 가이드
- [rag/vectorstores/config.py](../rag/vectorstores/config.py) - 벡터DB 설정 (컬렉션 매핑, 청킹)
- [CLAUDE.md](../CLAUDE.md) - 프로젝트 전체 가이드
