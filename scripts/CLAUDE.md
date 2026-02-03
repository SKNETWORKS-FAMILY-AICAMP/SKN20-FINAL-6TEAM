# Scripts - 데이터 크롤링 및 전처리 스크립트

> **이 문서는 Claude Code를 위한 자기 완결적 개발 가이드입니다.**
> 다른 AI 에이전트는 [AGENTS.md](./AGENTS.md)를 참조하세요.

## 개요

Bizi RAG 시스템에 필요한 데이터를 수집(크롤링)하고 전처리하는 스크립트를 관리합니다.
수집된 데이터는 `data/origin/`에 저장되고, 전처리된 데이터는 `data/preprocessed/`에 JSONL 형식으로 저장됩니다.

## 기술 스택

- Python 3.10+
- requests, httpx (HTTP 클라이언트)
- BeautifulSoup4 (웹 크롤링)
- OpenAI API (텍스트 추출/요약)
- easyocr, OpenCV (PDF OCR)
- pymupdf (PDF 텍스트 추출)
- olefile (HWP 파일 처리)

## 프로젝트 구조

```
scripts/
├── CLAUDE.md                      # 이 파일
├── AGENTS.md                      # AI 에이전트 개발 가이드
├── data_pipeline.md               # 전처리 파이프라인 상세 설명
│
├── crawling/                      # 데이터 수집 스크립트
│   ├── collect_all_laws.py        # 전체 법령 일괄 수집
│   ├── collect_labor_laws.py      # 노동 관련 법령 수집
│   ├── collect_court_cases.py     # 판례 수집
│   ├── collect_law_interpretations.py  # 법령해석례 수집
│   └── collect_announcements.py   # 기업마당/K-Startup API 공고 수집
│
└── preprocessing/                 # 데이터 전처리 스크립트
    ├── preprocess_announcements.py     # 공고 데이터 전처리
    ├── preprocess_laws.py              # 법령/해석례 전처리
    ├── preprocess_court_cases.py       # 판례 전처리
    ├── preprocess_labor_qa.py          # 노동 질의회시 PDF → JSONL
    ├── preprocess_hr_insurance.py      # 4대보험 전처리
    ├── preprocess_startup_guide.py     # 창업 가이드 전처리
    └── preprocess_startup_procedures.py # 창업 절차 전처리
```

## 데이터 흐름

```
┌─────────────────────────────────────────────────────────────┐
│                     외부 데이터 소스                          │
│  - 기업마당 API (지원사업 공고)                                │
│  - K-Startup API (스타트업 지원사업)                          │
│  - 국가법령정보센터 API (법령, 해석례, 판례)                    │
│  - PDF 파일 (질의회시집, 세무 가이드 등)                       │
└──────────────────────┬──────────────────────────────────────┘
                       │ scripts/crawling/*
                       ▼
┌─────────────────────────────────────────────────────────────┐
│               data/origin/ (원본 데이터)                      │
│  - 근로기준법 질의회시집.pdf                                   │
│  - laws_full.json, prec_*.json, expc_*.json                │
│  - startup_guide_complete.json                             │
│  - 세무일정.csv, 세제지원.pdf                                  │
└──────────────────────┬──────────────────────────────────────┘
                       │ scripts/preprocessing/*
                       ▼
┌─────────────────────────────────────────────────────────────┐
│             data/preprocessed/ (전처리 데이터)                 │
│  ├── law/             # 법령, 해석례, 판례 JSONL             │
│  ├── labor/           # 노동 질의회시 JSONL                  │
│  ├── finance/         # 세무일정, 가이드 JSONL               │
│  └── startup_support/ # 창업 가이드 JSONL                   │
└──────────────────────┬──────────────────────────────────────┘
                       │ rag/vectorstores/
                       ▼
┌─────────────────────────────────────────────────────────────┐
│                    ChromaDB (Vector DB)                      │
└─────────────────────────────────────────────────────────────┘
```

---

## 크롤러 (crawling/)

### 1. collect_all_laws.py

전체 현행 법령을 일괄 수집합니다.

```bash
python collect_all_laws.py --api-key YOUR_KEY
python collect_all_laws.py --max 100  # 테스트용 100개만
```

**특징:**
- 페이지네이션으로 전체 법령 순회
- 체크포인트 저장 → 중단 후 재개 가능
- 10페이지마다 중간 저장

### 2. collect_labor_laws.py

노동 관련 법령을 선별 수집합니다.

```python
from scripts.crawling.collect_labor_laws import LawCollector

collector = LawCollector(api_key=LAW_API_KEY)
laws = await collector.search_laws("근로기준법")
detail = await collector.get_law_detail(law_id)
```

**수집 대상:**
- 노동 관련 법률 (근로기준법, 최저임금법, 퇴직급여보장법 등)
- 시행령/시행규칙
- 고시/훈령

### 3. collect_court_cases.py

노동/세무 관련 판례를 수집합니다.

### 4. collect_law_interpretations.py

법령해석례(중기부, 고용노동부, 국세청 등)를 수집합니다.

### 5. collect_announcements.py

기업마당/K-Startup API에서 지원사업 공고를 수집합니다.

```python
from scripts.crawling.collect_announcements import AnnouncementProcessor

processor = AnnouncementProcessor()
results = processor.process(count=10, vrf_str='b')  # 기업마당 10개
results = processor.process(count=0, vrf_str='k')   # K-Startup 전체
```

**주요 기능:**
- 기업마당/K-Startup API 호출
- HWP 첨부파일 다운로드 및 텍스트 추출
- OpenAI API로 지원대상/제외대상/지원금액 추출
- 모집중인 공고만 필터링

---

## 전처리기 (preprocessing/)

### 1. preprocess_announcements.py

공고 데이터를 통합 스키마로 변환합니다.

```bash
python -m scripts.preprocessing.preprocess_announcements
```

**입력:** `data/origin/announcements/*.json`
**출력:** `data/preprocessed/funding/announcements.jsonl`

### 2. preprocess_laws.py

법령, 해석례를 통합 스키마로 변환합니다.

```bash
python -m scripts.preprocessing.preprocess_laws
```

**입력:**
- `law-raw/01_laws_full.json` (5,539 법령)
- `law-raw/expc_전체.json` (8,604 해석례)

**출력:**
- `data/preprocessed/law/laws_full.jsonl`
- `data/preprocessed/law/law_lookup.json`
- `data/preprocessed/law/interpretations.jsonl`

### 3. preprocess_court_cases.py

판례를 통합 스키마로 변환합니다.

```bash
python -m scripts.preprocessing.preprocess_court_cases
```

**입력:** `law-raw/prec_*.json` (판례)
**출력:** `data/preprocessed/law/court_cases_*.jsonl`

### 4. preprocess_labor_qa.py

노동 질의회시 PDF에서 Q&A를 추출합니다.

```bash
python -m scripts.preprocessing.preprocess_labor_qa
```

**입력:** `data/origin/근로기준법 질의회시집.pdf`
**출력:** `data/preprocessed/labor/labor_qa.jsonl`

**주요 기능:**
- OCR + 템플릿 매칭으로 질의/회시 마커 탐지
- 장/절 구조 파싱
- 행정번호, 날짜 추출

### 5. preprocess_hr_insurance.py

4대보험 데이터를 전처리합니다.

```bash
python -m scripts.preprocessing.preprocess_hr_insurance
```

### 6. preprocess_startup_procedures.py

창업절차 가이드를 RAG용 포맷으로 변환합니다.

```bash
python -m scripts.preprocessing.preprocess_startup_procedures
```

**입력:** `data/origin/startup_support/startup_procedures.json`
**출력:** `data/preprocessed/startup_support/startup_procedures.jsonl`

### 7. preprocess_startup_guide.py

업종별 창업 가이드를 변환합니다.

```bash
python -m scripts.preprocessing.preprocess_startup_guide
```

---

## 통합 스키마

모든 전처리기는 동일한 스키마를 따릅니다. 상세 스키마 정의는 [docs/DATA_SCHEMA.md](../docs/DATA_SCHEMA.md)를 참조하세요.

**필수 필드**: `id`, `type`, `domain`, `title`, `content`, `source`

---

## 환경 변수

```bash
# .env 파일 (프로젝트 루트)

# API 키
K-STARTUP_API_KEY=          # K-Startup API
BIZINFO_API_KEY=            # 기업마당 API
LAW_API_KEY=                # 국가법령정보센터 API
OPENAI_API_KEY=             # OpenAI (텍스트 추출용)

# 경로 (선택)
DATA_ORIGIN_PATH=data/origin
DATA_PROCESSED_PATH=data/preprocessed
```

---

## 코드 품질
`.claude/rules/coding-style.md`, `.claude/rules/security.md` 참조

### 크롤링 에티켓

- robots.txt 준수
- 요청 간격: 최소 1초
- User-Agent 명시
- 에러 시 재시도 로직 (exponential backoff)

---

## 참고 문서

- [docs/DATA_SCHEMA.md](../docs/DATA_SCHEMA.md) - 통합 스키마 정의
- [data_pipeline.md](./data_pipeline.md) - 전처리 파이프라인 상세 설명
- [data/CLAUDE.md](../data/CLAUDE.md) - 데이터 폴더 가이드
- [rag/CLAUDE.md](../rag/CLAUDE.md) - RAG 시스템 가이드
- [CLAUDE.md](../CLAUDE.md) - 프로젝트 전체 가이드
