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
    ├── law/                   # 법령, 해석례, 판례
    │   ├── laws_full.jsonl
    │   ├── law_lookup.json
    │   ├── interpretations.jsonl
    │   └── court_cases_*.jsonl
    ├── labor/                 # 노동 질의회시
    │   └── labor_qa.jsonl
    ├── finance/               # 세무일정, 세제지원
    │   └── tax_schedule.jsonl
    └── startup_support/       # 창업 가이드
        ├── industries.jsonl
        └── startup_procedures.jsonl
```

---

## 데이터 흐름

```
┌─────────────────────────────────────────────────────────────┐
│                     외부 데이터 소스                          │
│  - 기업마당 API, K-Startup API                              │
│  - 국가법령정보센터 API                                       │
│  - PDF 다운로드 (질의회시집, 세제지원 등)                      │
└──────────────────────┬──────────────────────────────────────┘
                       │ scripts/crawling/*
                       ▼
┌─────────────────────────────────────────────────────────────┐
│                    data/origin/                              │
│  원본 데이터 저장 (JSON, PDF, CSV 등)                         │
└──────────────────────┬──────────────────────────────────────┘
                       │ scripts/preprocessing/*
                       ▼
┌─────────────────────────────────────────────────────────────┐
│                  data/preprocessed/                          │
│  전처리된 JSONL 파일 (통합 스키마)                             │
└──────────────────────┬──────────────────────────────────────┘
                       │ rag/vectorstores/
                       ▼
┌─────────────────────────────────────────────────────────────┐
│                    ChromaDB (Vector DB)                      │
│  임베딩 + 메타데이터 저장                                      │
└─────────────────────────────────────────────────────────────┘
```

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

모든 전처리된 문서는 동일한 스키마를 따릅니다:

```json
{
  "id": "LAW_010719",
  "type": "law",
  "domain": "legal",
  "title": "근로기준법",
  "content": "제1조(목적) 이 법은 헌법에 따라...",
  "source": {
    "name": "국가법령정보센터",
    "url": "https://law.go.kr/법령/근로기준법",
    "collected_at": "2026-01-20T11:43:48"
  },
  "effective_date": "2024-02-09",
  "related_laws": [
    {
      "law_id": "LAW_010719",
      "law_name": "근로기준법",
      "article_ref": "제15조"
    }
  ],
  "metadata": {}
}
```

### 필드 설명

| 필드 | 타입 | 필수 | 설명 |
|------|------|------|------|
| `id` | string | O | 문서 고유 ID |
| `type` | string | O | 문서 유형 (law, interpretation, guide, schedule 등) |
| `domain` | string | O | 도메인 (legal, tax, labor, startup, funding, marketing) |
| `title` | string | O | 제목 |
| `content` | string | O | RAG 검색용 본문 |
| `source` | object | O | 출처 정보 |
| `effective_date` | string | - | 시행일/마감일 (YYYY-MM-DD) |
| `related_laws` | array | - | 관련 법령 참조 |
| `metadata` | object | - | 타입별 추가 데이터 |

### ID 체계

| 타입 | ID 형식 | 예시 |
|------|---------|------|
| 법령 | `LAW_{law_id}` | `LAW_010719` |
| 해석례 | `INTERP_{기관}_{id}` | `INTERP_SMBA_313107` |
| 판례 | `COURT_{domain}_{id}` | `COURT_LABOR_12345` |
| 공고 | `ANNOUNCE_{source}_{id}` | `ANNOUNCE_BIZINFO_123` |
| 가이드 | `GUIDE_{업종코드}` | `GUIDE_011000` |
| 일정 | `SCHEDULE_TAX_{날짜}_{순번}` | `SCHEDULE_TAX_20260126_001` |
| 질의회시 | `LABOR_QA_{장}_{페이지}_{순번}` | `LABOR_QA_1_15_001` |

### 도메인 분류

| 도메인 | 설명 | 키워드 |
|--------|------|--------|
| `tax` | 세무/회계 | 세법, 소득세, 법인세, 부가가치세 |
| `labor` | 노동/인사 | 근로, 노동, 고용, 임금, 퇴직, 해고 |
| `startup` | 창업/사업자 | 사업자, 창업, 법인설립, 업종, 인허가 |
| `funding` | 지원사업 | 지원사업, 보조금, 정책자금, 공고 |
| `legal` | 법률 | 상법, 민법, 공정거래, 계약 |
| `marketing` | 마케팅 | 광고, 홍보, 브랜딩 |

---

## 출력 파일 상세

### law/laws_full.jsonl

법령 전문 (법률 + 조문)

```json
{
  "id": "LAW_010719",
  "type": "law",
  "domain": "labor",
  "title": "근로기준법",
  "content": "제1조(목적) 이 법은 헌법에 따라...\n제2조(정의)...",
  "metadata": {
    "ministry": "고용노동부",
    "enforcement_date": "20240209",
    "article_count": 116
  }
}
```

### law/law_lookup.json

법령명 → law_id 매핑 (참조 연결용)

```json
{
  "근로기준법": "LAW_010719",
  "최저임금법": "LAW_012345",
  ...
}
```

### law/interpretations.jsonl

법령해석례

```json
{
  "id": "INTERP_LABOR_123456",
  "type": "interpretation",
  "domain": "labor",
  "title": "연장근로수당 산정 기준",
  "content": "질의: ... 회신: ...",
  "related_laws": [
    {"law_id": "LAW_010719", "law_name": "근로기준법", "article_ref": "제56조"}
  ],
  "metadata": {
    "organization": "고용노동부",
    "case_no": "근로기준정책과-5076"
  }
}
```

### labor/labor_qa.jsonl

노동 질의회시 (PDF 추출)

```json
{
  "id": "LABOR_QA_1_15_001",
  "type": "labor_qa",
  "domain": "labor",
  "title": "연장근로 계산 방법",
  "content": "[질의] 연장근로수당은 어떻게 계산하나요?\n[회시] 연장근로수당은...",
  "metadata": {
    "chapter": "1",
    "section": "근로시간",
    "admin_no": "근로기준정책과-5076",
    "admin_date": "2018.8.1"
  }
}
```

### startup_support/industries.jsonl

업종별 창업 가이드

```json
{
  "id": "GUIDE_011000",
  "type": "guide",
  "domain": "startup",
  "title": "음식점업 창업 가이드",
  "content": "[개요] 음식점업은...\n[인허가] 영업신고...",
  "metadata": {
    "industry_code": "011000",
    "category": "음식점업"
  }
}
```

### finance/tax_schedule.jsonl

세무 신고 일정

```json
{
  "id": "SCHEDULE_TAX_20260126_001",
  "type": "schedule",
  "domain": "tax",
  "title": "법인세 신고",
  "content": "법인세 신고 및 납부 마감일입니다.",
  "effective_date": "2026-01-26",
  "metadata": {
    "tax_type": "법인세",
    "deadline_type": "신고"
  }
}
```

---

## 데이터 품질 검증

### 검증 체크리스트

- [ ] 모든 JSONL 레코드가 통합 스키마 준수
- [ ] 필수 필드 (id, type, domain, title, content) 존재
- [ ] ID 형식 규칙 준수
- [ ] `related_laws[].law_id`가 `law_lookup.json`에 존재
- [ ] 한글 인코딩 정상 (깨짐 없음)

### 예상 레코드 수

| 파일 | 예상 수 |
|------|---------|
| laws_full.jsonl | ~5,500 |
| interpretations.jsonl | ~8,600 |
| court_cases_*.jsonl | ~3,000 |
| labor_qa.jsonl | ~500 |
| industries.jsonl | ~1,600 |
| tax_schedule.jsonl | ~240 |

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
- 전체 preprocessed: ~50MB

---

## 참고 문서

- [scripts/CLAUDE.md](../scripts/CLAUDE.md) - 크롤링/전처리 스크립트 가이드
- [scripts/data_pipeline.md](../scripts/data_pipeline.md) - 전처리 파이프라인 상세 설명
- [rag/CLAUDE.md](../rag/CLAUDE.md) - RAG 시스템 가이드
- [CLAUDE.md](../CLAUDE.md) - 프로젝트 전체 가이드
