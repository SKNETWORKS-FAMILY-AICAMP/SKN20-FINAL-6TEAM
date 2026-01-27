# BizMate 데이터 전처리 파이프라인

> 원본 데이터를 RAG 시스템에 적합한 통일 스키마로 변환하는 파이프라인

---

## 1. 시스템 개요

### 1.1 아키텍처 다이어그램

```mermaid
flowchart TB
    subgraph Origin["data/origin (원본 데이터)"]
        LAW["law/<br/>01_laws_full.json<br/>02-05_*_expc_full.json"]
        STARTUP["startup_support/<br/>startup_guide_complete.json"]
        FINANCE["finance/<br/>세무일정.csv<br/>세제지원.pdf"]
        LABOR["labor/<br/>4대보험.pdf<br/>질의회시집.pdf"]
    end

    subgraph Pipeline["scripts/preprocessing (전처리 파이프라인)"]
        direction TB
        LP["LawProcessor<br/>법령 처리"]
        IP["InterpretationProcessor<br/>해석례 처리"]
        GP["GuideProcessor<br/>가이드 처리"]
        SP["ScheduleProcessor<br/>일정 처리"]
        PP["PDFProcessor<br/>PDF 처리"]
    end

    subgraph Output["data/processed (출력)"]
        LAWS_OUT["laws/<br/>laws_full.jsonl<br/>law_lookup.json"]
        INTERP_OUT["interpretations/<br/>interpretations.jsonl"]
        COURT_OUT["court_cases/<br/>court_cases_labor.jsonl<br/>court_cases_tax.jsonl"]
        GUIDES_OUT["guides/<br/>industries.jsonl<br/>common_info.jsonl<br/>pdf_guides.jsonl"]
        SCHED_OUT["schedules/<br/>tax_schedule.jsonl"]
    end

    subgraph RAG["RAG System"]
        CHROMA["ChromaDB<br/>Vector Store"]
        AGENT["Multi-Agent<br/>System"]
    end

    LAW --> LP
    LAW --> IP
    STARTUP --> GP
    FINANCE --> SP
    FINANCE --> PP
    LABOR --> PP

    LP --> LAWS_OUT
    IP --> INTERP_OUT
    GP --> GUIDES_OUT
    SP --> SCHED_OUT
    PP --> GUIDES_OUT

    LAWS_OUT --> CHROMA
    INTERP_OUT --> CHROMA
    GUIDES_OUT --> CHROMA
    SCHED_OUT --> CHROMA
    CHROMA --> AGENT

    style Origin fill:#e1f5fe
    style Pipeline fill:#fff3e0
    style Output fill:#e8f5e9
    style RAG fill:#fce4ec
```

### 1.2 개발 원칙

| 원칙 | 설명 | 예시 |
|------|------|------|
| **하드코딩 금지** | 경로, 파일명, 상수값은 config.py에서 관리 | `OUTPUT_DIR = Path(config.OUTPUT_PATH)` |
| **모듈화** | 단일 책임 원칙, 재사용 가능한 함수/클래스 설계 | Processor별 독립 모듈, 공통 유틸 분리 |
| **설정 주입** | 외부 설정 파일(.env, config)을 통한 환경 분리 | `API_KEY = os.getenv("LAW_API_KEY")` |
| **의존성 명시** | 함수/클래스 간 의존 관계를 명확히 문서화 | 섹션 9.2 의존성 그래프 참조 |

---

## 2. 통일 스키마

### 2.1 스키마 구조 다이어그램

```mermaid
erDiagram
    BaseDocument {
        string id PK "LAW_xxx, INTERP_xxx, GUIDE_xxx, SCHEDULE_xxx"
        enum type "law | interpretation | guide | schedule"
        enum domain "legal | tax | labor | startup | funding | marketing"
        string title
        string content "RAG 검색용 본문"
        date effective_date "시행일/마감일"
    }

    Source {
        string name
        string url
        datetime collected_at
    }

    RelatedLaw {
        string law_id FK "법령 ID (nullable)"
        string law_name "법령명"
        string article_ref "제N조 참조"
    }

    Metadata {
        json data "타입별 특수 데이터"
    }

    BaseDocument ||--|| Source : has
    BaseDocument ||--o{ RelatedLaw : references
    BaseDocument ||--|| Metadata : contains
```

### 2.2 스키마 정의

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
  "metadata": {         # 필요한 경우 추가
    "ministry": "고용노동부",
    "enforcement_date": "20240209",
    "article_count": 116,
    "related_laws": []      
  }
}
```

---

## 3. 데이터 흐름

### 3.1 처리 순서 다이어그램

```mermaid
sequenceDiagram
    autonumber
    participant M as main.py
    participant LP as LawProcessor
    participant IP as InterpretationProcessor
    participant GP as GuideProcessor
    participant SP as ScheduleProcessor
    participant PP as PDFProcessor
    participant W as JSONLWriter

    Note over M: 파이프라인 시작

    M->>LP: process_laws()
    LP->>LP: JSON 로드 (304MB)
    LP->>LP: 법령 + 조문 통합
    LP->>W: laws_full.jsonl 출력
    LP-->>M: law_lookup.json 반환

    M->>IP: process_interpretations(law_lookup)
    IP->>IP: 법령 참조 추출 (정규식)
    IP->>IP: related_laws 매핑
    IP->>W: *_interp.jsonl 출력

    M->>GP: process_guides(law_lookup)
    GP->>GP: common_info 처리
    GP->>GP: industries 처리
    GP->>W: guides/*.jsonl 출력

    M->>SP: process_schedules()
    SP->>SP: CSV 인코딩 변환
    SP->>W: tax_schedule.jsonl 출력

    M->>PP: process_pdf()
    PP->>PP: 텍스트 추출
    PP->>PP: 섹션 분할
    PP->>W: pdf_guides.jsonl 출력

    Note over M: 파이프라인 완료
```

### 3.2 법령 참조 연결 흐름

```mermaid
flowchart LR
    subgraph Step1["1단계: 법령 처리"]
        LAW["01_laws_full.json"]
        LOOKUP["law_lookup.json<br/>{법령명: law_id}"]
        LAW --> LOOKUP
    end

    subgraph Step2["2단계: 참조 추출"]
        TEXT["해석례/가이드 본문"]
        REGEX["정규식 추출<br/>「법령명」 제N조"]
        TEXT --> REGEX
    end

    subgraph Step3["3단계: 매핑"]
        MATCH["law_lookup 조회"]
        RELATED["related_laws 생성"]
        REGEX --> MATCH
        LOOKUP -.-> MATCH
        MATCH --> RELATED
    end

    style Step1 fill:#e3f2fd
    style Step2 fill:#fff8e1
    style Step3 fill:#e8f5e9
```

---

## 4. 원본 데이터 분석

### 4.1 데이터 소스 현황

```mermaid
pie showData
    title 레코드 수 분포
    "법령 (5,539)" : 5539
    "해석례 (1,100)" : 1100
    "창업가이드 (1,589)" : 1589
    "세무일정 (238)" : 238
    "PDF (~50 섹션)" : 50
```

### 4.2 원본 → 출력 매핑

| 원본 파일 | 형식 | 크기 | 레코드 | 출력 파일 |
|-----------|------|------|--------|-----------|
| `law-raw/01_laws_full.json` | JSON | 304MB | 5,539 법령 | `final_files/data/processed/laws/laws_full.jsonl` |
| `law-raw/expc_전체.json` | JSON | 74MB | 8,604건 | `final_files/data/processed/interpretations/interpretations.jsonl` |
| `law-raw/prec_labor.json` | JSON | 20MB | 981건 | `final_files/data/processed/court_cases/court_cases_labor.jsonl` |
| `law-raw/prec_tax_accounting.json` | JSON | 25MB | 1,949건 | `final_files/data/processed/court_cases/court_cases_tax.jsonl` |
| `data/origin/startup_support/startup_guide_complete.json` | JSON | 3.5MB | 1,589 업종 | `data/processed/guides/industries.jsonl` |
| `data/origin/finance/국세청_세무일정_20260101.csv` | CSV | 20KB | 238건 | `data/processed/schedules/tax_schedule.jsonl` |
| `data/origin/finance/2025 중소기업세제·세정지원 제도.pdf` | PDF | 13MB | - | `data/processed/guides/pdf_guides.jsonl` |
| `data/origin/labor/[PDF]중소벤처기업 4대보험 신고.pdf` | PDF | 637KB | - | `data/processed/guides/pdf_guides.jsonl` |
| `data/origin/labor/근로기준법 질의회시집.pdf` | PDF | 13MB | - | `data/processed/guides/pdf_guides.jsonl` |

---

## 5. ID 체계

### 5.1 ID 생성 규칙

```mermaid
flowchart LR
    subgraph LAW_ID["법령 ID"]
        L1["LAW_"] --> L2["law_id<br/>(원본 ID)"]
        L2 --> L3["LAW_010719"]
    end

    subgraph INTERP_ID["해석례 ID"]
        I1["INTERP_"] --> I2["기관코드_"]
        I2 --> I3["원본ID"]
        I3 --> I4["INTERP_SMBA_313107"]
    end

    subgraph GUIDE_ID["가이드 ID"]
        G1["GUIDE_"] --> G2["업종코드<br/>or 카테고리"]
        G2 --> G3["GUIDE_011000"]
    end

    subgraph SCHED_ID["일정 ID"]
        S1["SCHEDULE_TAX_"] --> S2["날짜_"]
        S2 --> S3["순번"]
        S3 --> S4["SCHEDULE_TAX_20260126_001"]
    end
```

### 5.2 기관 코드 매핑

| 기관명 | 코드 | 도메인 |
|--------|------|--------|
| 중소벤처기업부 | SMBA | startup |
| 고용노동부 | LABOR | labor |
| 국세청 | NTS | tax |
| 공정거래위원회 | FTC | legal |

---

## 6. 도메인 분류

### 6.1 분류 로직

```mermaid
flowchart TD
    START["문서 입력"] --> CHECK_ORG{"기관 정보<br/>있음?"}

    CHECK_ORG -->|Yes| ORG_MAP["기관 기반 분류"]
    ORG_MAP --> SMBA_D["중소벤처기업부 → startup"]
    ORG_MAP --> LABOR_D["고용노동부 → labor"]
    ORG_MAP --> NTS_D["국세청 → tax"]
    ORG_MAP --> FTC_D["공정거래위원회 → legal"]

    CHECK_ORG -->|No| KEYWORD["키워드 기반 분류"]
    KEYWORD --> SCAN["본문 + 제목 스캔"]
    SCAN --> SCORE["키워드 점수 계산"]
    SCORE --> MAX["최고 점수 도메인 선택"]

    SMBA_D --> RESULT["도메인 결정"]
    LABOR_D --> RESULT
    NTS_D --> RESULT
    FTC_D --> RESULT
    MAX --> RESULT

    style CHECK_ORG fill:#fff3e0
    style RESULT fill:#e8f5e9
```

### 6.2 도메인별 키워드

| 도메인 | 키워드 |
|--------|--------|
| **tax** | 세법, 소득세, 법인세, 부가가치세, 국세청, 세금, 세무 |
| **labor** | 근로, 노동, 고용, 임금, 퇴직, 해고, 휴가, 4대보험 |
| **startup** | 사업자, 창업, 법인설립, 업종, 인허가 |
| **funding** | 지원사업, 보조금, 정책자금, 공고 |
| **legal** | 상법, 민법, 특허법, 상표법, 저작권법, 공정거래, 계약 |
| **marketing** | 광고, 홍보, 마케팅, 브랜딩 |

---

## 7. 법령 참조 추출

### 7.1 정규식 패턴

```python
# 법령명 추출
LAW_NAME_PATTERN = r"「([^」]+)」"
# 예: 「근로기준법」 → "근로기준법"

# 조문 참조 추출
ARTICLE_PATTERN = r"제(\d+)조(?:의(\d+))?"
# 예: "제15조" → ("15", None)
# 예: "제2조의3" → ("2", "3")

# 동법/같은 법 처리
SAME_LAW_PATTERN = r"(?:동법|같은\s*법)\s*제(\d+)조"
```

### 7.2 추출 예시

```
입력 텍스트:
"「근로기준법」 제15조 및 같은 법 제18조에 따라..."

추출 결과:
[
  {"law_name": "근로기준법", "law_id": "LAW_010719", "article_ref": "제15조"},
  {"law_name": "근로기준법", "law_id": "LAW_010719", "article_ref": "제18조"}
]
```

---

## 8. 파일 구조

### 8.1 디렉토리 트리

```
SKN20-FINAL-6TEAM/
├── scripts/
│   └── preprocessing/                 # 전처리 스크립트
│       ├── __init__.py
│       ├── config.py                  # 경로, 상수
│       ├── schema.py                  # Pydantic 스키마
│       ├── requirements.txt           # 의존성
│       ├── data_pipeline.md           # 이 문서
│       │
│       ├── utils/
│       │   ├── __init__.py
│       │   ├── id_generator.py        # ID 생성
│       │   ├── law_extractor.py       # 법령 참조 추출
│       │   └── domain_classifier.py   # 도메인 분류
│       │
│       ├── processors/
│       │   ├── __init__.py
│       │   ├── base_processor.py      # 추상 클래스
│       │   ├── law_processor.py       # 법령 처리
│       │   ├── interpretation_processor.py
│       │   ├── guide_processor.py
│       │   ├── schedule_processor.py
│       │   └── pdf_processor.py       # PDF 처리
│       │
│       ├── writers/
│       │   ├── __init__.py
│       │   └── jsonl_writer.py        # JSONL 출력
│       │
│       └── main.py                    # CLI 진입점
│
└── data/
    ├── origin/                        # 원본 데이터 (읽기 전용)
    │   ├── law/
    │   ├── startup_support/
    │   ├── finance/
    │   └── labor/
    │
    └── processed/                     # 전처리 출력
        ├── laws/
        │   ├── laws_full.jsonl
        │   └── law_lookup.json
        ├── interpretations/
        │   └── interpretations.jsonl
        ├── court_cases/
        │   ├── court_cases_labor.jsonl
        │   └── court_cases_tax.jsonl
        ├── guides/
        │   ├── common_info.jsonl
        │   ├── industries.jsonl
        │   └── pdf_guides.jsonl
        └── schedules/
            └── tax_schedule.jsonl
```

---

## 9. 구현 순서

### 9.1 개발 로드맵

```mermaid
gantt
    title 전처리 파이프라인 개발 일정
    dateFormat  YYYY-MM-DD

    section Phase 1: 기반
    config.py           :p1_1, 2026-01-27, 1d
    schema.py           :p1_2, after p1_1, 1d
    id_generator.py     :p1_3, after p1_1, 1d
    law_extractor.py    :p1_4, after p1_2, 1d

    section Phase 2: 유틸
    domain_classifier.py :p2_1, after p1_4, 1d
    jsonl_writer.py     :p2_2, after p1_2, 1d

    section Phase 3: 프로세서
    base_processor.py   :p3_1, after p2_2, 1d
    law_processor.py    :p3_2, after p3_1, 2d
    interpretation_processor.py :p3_3, after p3_2, 1d
    guide_processor.py  :p3_4, after p3_2, 1d
    schedule_processor.py :p3_5, after p3_2, 1d
    pdf_processor.py    :p3_6, after p3_2, 1d

    section Phase 4: 통합
    main.py             :p4_1, after p3_6, 1d
    테스트 및 검증      :p4_2, after p4_1, 2d
```

### 9.2 의존성 그래프

```mermaid
flowchart BT
    CONFIG["config.py"]
    SCHEMA["schema.py"]
    ID_GEN["id_generator.py"]
    LAW_EXT["law_extractor.py"]
    DOMAIN["domain_classifier.py"]
    WRITER["jsonl_writer.py"]
    BASE["base_processor.py"]
    LAW_P["law_processor.py"]
    INTERP_P["interpretation_processor.py"]
    GUIDE_P["guide_processor.py"]
    SCHED_P["schedule_processor.py"]
    PDF_P["pdf_processor.py"]
    MAIN["main.py"]

    CONFIG --> SCHEMA
    SCHEMA --> ID_GEN
    SCHEMA --> LAW_EXT
    CONFIG --> DOMAIN
    SCHEMA --> WRITER
    SCHEMA --> BASE

    BASE --> LAW_P
    ID_GEN --> LAW_P
    LAW_EXT --> LAW_P
    DOMAIN --> LAW_P
    WRITER --> LAW_P

    BASE --> INTERP_P
    LAW_EXT --> INTERP_P
    DOMAIN --> INTERP_P

    BASE --> GUIDE_P
    BASE --> SCHED_P
    BASE --> PDF_P

    LAW_P --> MAIN
    INTERP_P --> MAIN
    GUIDE_P --> MAIN
    SCHED_P --> MAIN
    PDF_P --> MAIN

    style CONFIG fill:#ffcdd2
    style SCHEMA fill:#ffcdd2
    style MAIN fill:#c8e6c9
```

---

## 10. 실행 방법

### 10.1 설치

```bash
cd C:\.workspace\SKN20-FINAL-6TEAM
pip install -r scripts/preprocessing/requirements.txt
```

### 10.2 CLI 명령어

```bash
# 전체 처리
python -m scripts.preprocessing.main --all

# 개별 처리
python -m scripts.preprocessing.main --laws           # 법령만
python -m scripts.preprocessing.main --interpretations # 해석례만
python -m scripts.preprocessing.main --guides         # 가이드만
python -m scripts.preprocessing.main --schedules      # 세무일정만
python -m scripts.preprocessing.main --pdf            # PDF만
```

### 10.3 출력 확인

```bash
# JSONL 파일 미리보기
head -3 data/processed/laws/laws_full.jsonl | jq .

# 레코드 수 확인
wc -l data/processed/*/*.jsonl

# 법령 lookup 확인
jq 'keys | length' data/processed/laws/law_lookup.json
```

---

## 11. 검증 체크리스트

### 11.1 스키마 검증
- [ ] 모든 JSONL 레코드가 Pydantic 스키마 통과
- [ ] 필수 필드(id, type, domain, title, content) 존재
- [ ] ID 형식 규칙 준수

### 11.2 관계 무결성
- [ ] `related_laws[].law_id`가 `law_lookup.json`에 존재
- [ ] 법령 해석례의 법령 참조가 올바르게 추출

### 11.3 데이터 품질
- [ ] 법령 수: ~5,500개
- [ ] 해석례 수: ~1,100개
- [ ] 가이드 수: ~1,600개
- [ ] 일정 수: ~240개
- [ ] 한글 인코딩 정상 (깨짐 없음)

### 11.4 성능
- [ ] 전체 처리 시간 < 15분
- [ ] 메모리 사용량 < 4GB

---

## 12. 의존성

### requirements.txt

```
pydantic>=2.0
PyPDF2>=3.0
chardet>=5.0
tqdm>=4.0
```

---

## 13. 참고 자료

- [프로젝트 CLAUDE.md](../../CLAUDE.md)
- [데이터 CLAUDE.md](../../data/CLAUDE.md)
