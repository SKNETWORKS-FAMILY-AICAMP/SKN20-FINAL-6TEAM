# Data - 데이터 크롤링 및 전처리

> **이 문서는 Claude Code를 위한 자기 완결적 개발 가이드입니다.**
> 다른 AI 에이전트는 [AGENTS.md](./AGENTS.md)를 참조하세요.

## 개요
Bizi의 RAG 시스템에 필요한 데이터를 수집하고 전처리하는 스크립트를 관리합니다.
수집된 데이터는 벡터DB(ChromaDB)에 임베딩되어 저장됩니다.

## 기술 스택
- Python 3.10+
- requests, httpx (HTTP 클라이언트)
- BeautifulSoup4 (웹 크롤링)
- pandas (데이터 처리)
- langchain (텍스트 분할)

## 프로젝트 구조
```
data/
├── CLAUDE.md              # 이 파일
├── AGENTS.md              # AI 에이전트 개발 가이드
├── requirements.txt       # 의존성
│
├── crawlers/              # 크롤러 스크립트
│   ├── __init__.py
│   ├── bizinfo.py         # 기업마당 API 크롤러
│   ├── kstartup.py        # K-Startup API 크롤러
│   ├── law.py             # 국가법령정보센터 크롤러
│   └── tax.py             # 국세청 데이터 크롤러
│
├── preprocessors/         # 전처리 스크립트
│   ├── __init__.py
│   ├── cleaner.py         # 텍스트 정제
│   ├── chunker.py         # 텍스트 분할 (청킹)
│   └── embedder.py        # 임베딩 생성
│
├── pipelines/             # 파이프라인 (수집 → 전처리 → 저장)
│   ├── __init__.py
│   ├── funding_pipeline.py    # 지원사업 파이프라인
│   ├── law_pipeline.py        # 법령 파이프라인
│   └── tax_pipeline.py        # 세무 파이프라인
│
├── raw/                   # 원본 데이터 (git에서 제외)
│   ├── funding/
│   ├── law/
│   └── tax/
│
├── processed/             # 전처리된 데이터 (git에서 제외)
│   ├── funding/
│   ├── law/
│   └── tax/
│
└── scripts/               # 유틸리티 스크립트
    ├── run_all.py         # 전체 파이프라인 실행
    ├── sync_vectordb.py   # 벡터DB 동기화
    └── schedule.py        # 스케줄러 (cron 대체)
```

## 실행 방법

### 환경 설정
```bash
cd data
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate
pip install -r requirements.txt
```

### 개별 크롤러 실행
```bash
# 지원사업 데이터 수집
python -m crawlers.bizinfo

# 법령 데이터 수집
python -m crawlers.law

# 세무 데이터 수집
python -m crawlers.tax
```

### 파이프라인 실행
```bash
# 지원사업 전체 파이프라인
python -m pipelines.funding_pipeline

# 법령 전체 파이프라인
python -m pipelines.law_pipeline

# 전체 파이프라인 실행
python scripts/run_all.py
```

### 벡터DB 동기화
```bash
python scripts/sync_vectordb.py
```

## 데이터 소스

### 1. 지원사업 데이터 (REQ-FA-001, REQ-FA-002)
| 소스 | API/URL | 설명 |
|------|---------|------|
| 기업마당 | Open API | 정부 지원사업 공고 |
| K-Startup | Open API | 스타트업 지원사업 |

### 2. 법령 데이터 (REQ-HR-001, REQ-HR-002)
| 소스 | API/URL | 설명 |
|------|---------|------|
| 국가법령정보센터 | Open API | 법령, 시행령, 시행규칙 |
| 고용노동부 | 웹 크롤링 | 근로기준법 해설 |

### 3. 세무/회계 데이터 (REQ-TA-001~004)
| 소스 | API/URL | 설명 |
|------|---------|------|
| 국세청 | 웹 크롤링 | 세법 해설서, 신고 가이드 |
| 홈택스 | 웹 크롤링 | 전자신고 매뉴얼 |

## 전처리 파이프라인

### 1. 텍스트 정제 (cleaner.py)
- HTML 태그 제거
- 특수문자 정규화
- 불필요한 공백 제거
- 인코딩 통일 (UTF-8)

### 2. 텍스트 분할 (chunker.py)
```python
# LangChain RecursiveCharacterTextSplitter 사용
from langchain.text_splitter import RecursiveCharacterTextSplitter

splitter = RecursiveCharacterTextSplitter(
    chunk_size=1000,
    chunk_overlap=200,
    separators=["\n\n", "\n", ".", " "]
)
```

### 3. 임베딩 생성 (embedder.py)
```python
# OpenAI Embeddings 사용
from langchain.embeddings import OpenAIEmbeddings

embeddings = OpenAIEmbeddings(model="text-embedding-3-small")
```

## 청킹 전략

### 도메인별 청킹 설정
| 도메인 | chunk_size | chunk_overlap | 설명 |
|--------|------------|---------------|------|
| 지원사업 | 1000 | 200 | 공고문 단위 |
| 법령 | 500 | 100 | 조항 단위 (Hierarchical) |
| 세무 | 800 | 150 | 항목별 가이드 |

### Hierarchical RAG (법령)
```
법령 (상위)
  └── 시행령 (중위)
      └── 시행규칙/사내규정 (하위)
```

## 환경 변수
```
# OpenAI (임베딩용)
OPENAI_API_KEY=

# External APIs
BIZINFO_API_KEY=       # 기업마당 API
KSTARTUP_API_KEY=      # K-Startup API
LAW_API_KEY=           # 국가법령정보센터 API

# ChromaDB
CHROMA_HOST=localhost
CHROMA_PORT=8002

# 데이터 경로
DATA_RAW_PATH=./raw
DATA_PROCESSED_PATH=./processed
```

## 스케줄링

### 데이터 갱신 주기
| 데이터 | 주기 | 설명 |
|--------|------|------|
| 지원사업 | 매일 | 신규 공고, 마감 공고 갱신 |
| 법령 | 주간 | 법령 개정 시 업데이트 |
| 세무 | 월간 | 세법 개정 시 업데이트 |

### 스케줄러 설정
```python
# scripts/schedule.py
from apscheduler.schedulers.blocking import BlockingScheduler

scheduler = BlockingScheduler()

# 매일 오전 6시 지원사업 동기화
scheduler.add_job(sync_funding, 'cron', hour=6)

# 매주 일요일 오전 3시 법령 동기화
scheduler.add_job(sync_law, 'cron', day_of_week='sun', hour=3)
```

---

## 코드 품질 가이드라인 (필수 준수)

### 절대 금지 사항
- **하드코딩 금지**: API 키, 파일 경로, URL 등을 코드에 직접 작성 금지 → 환경 변수 사용
- **매직 넘버/매직 스트링 금지**: chunk_size, 요청 간격 등 설정값을 코드에 직접 사용 금지
- **중복 코드 금지**: 동일한 크롤링/전처리 로직은 base 클래스 또는 유틸 함수로 추출
- **API 키 노출 금지**: 외부 API 키를 코드/로그에 노출 금지

### 필수 준수 사항
- **환경 변수 사용**: 모든 설정값(API 키, 경로, 설정)은 `.env` 파일로 관리
- **상수 정의**: 청킹 설정, API 엔드포인트 등은 상수로 정의
- **타입 힌트 사용**: 함수 파라미터와 반환값에 타입 힌트 필수
- **에러 처리**: API 호출 실패, 파싱 오류 등 예외 처리 필수
- **의미 있는 네이밍**: 크롤러, 파이프라인, 함수명은 역할을 명확히 표현
- **base 클래스 상속**: 새 크롤러/파이프라인은 반드시 base 클래스 상속
