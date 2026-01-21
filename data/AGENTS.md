# Data 개발 가이드

> 이 문서는 AI 에이전트가 데이터 크롤링/전처리 스크립트 개발을 지원하기 위한 가이드입니다.

## 개요
BizMate의 RAG 시스템에 필요한 데이터를 수집하고 전처리하는 스크립트를 관리합니다.
수집된 데이터는 벡터DB(ChromaDB)에 임베딩되어 저장됩니다.

## 프로젝트 구조
```
data/
├── CLAUDE.md              # 개발 가이드
├── AGENTS.md              # 이 파일
├── requirements.txt
│
├── crawlers/              # 크롤러 스크립트
│   ├── __init__.py
│   ├── base.py            # 기본 크롤러 클래스
│   ├── bizinfo.py         # 기업마당 API
│   ├── kstartup.py        # K-Startup API
│   ├── law.py             # 국가법령정보센터
│   └── tax.py             # 국세청 데이터
│
├── preprocessors/         # 전처리 스크립트
│   ├── __init__.py
│   ├── cleaner.py         # 텍스트 정제
│   ├── chunker.py         # 텍스트 분할
│   └── embedder.py        # 임베딩 생성
│
├── pipelines/             # 파이프라인
│   ├── __init__.py
│   ├── base.py            # 기본 파이프라인 클래스
│   ├── funding_pipeline.py
│   ├── law_pipeline.py
│   └── tax_pipeline.py
│
├── raw/                   # 원본 데이터 (gitignore)
├── processed/             # 전처리 데이터 (gitignore)
│
└── scripts/               # 유틸리티 스크립트
    ├── run_all.py
    ├── sync_vectordb.py
    └── schedule.py
```

## 코드 작성 규칙

### 1. 크롤러 클래스
```python
# crawlers/base.py
from abc import ABC, abstractmethod
import httpx

class BaseCrawler(ABC):
    def __init__(self, api_key: str | None = None):
        self.api_key = api_key
        self.client = httpx.AsyncClient()

    @abstractmethod
    async def fetch(self) -> list[dict]:
        """데이터 수집"""
        pass

    @abstractmethod
    async def parse(self, raw_data: dict) -> dict:
        """데이터 파싱"""
        pass

    async def run(self) -> list[dict]:
        raw_data = await self.fetch()
        return [await self.parse(item) for item in raw_data]
```

### 2. 크롤러 구현
```python
# crawlers/bizinfo.py
from crawlers.base import BaseCrawler

class BizinfoCrawler(BaseCrawler):
    BASE_URL = "https://www.bizinfo.go.kr/uss/rss/bizRss.do"

    async def fetch(self) -> list[dict]:
        response = await self.client.get(
            self.BASE_URL,
            params={"api_key": self.api_key}
        )
        return response.json()["data"]

    async def parse(self, raw_data: dict) -> dict:
        return {
            "title": raw_data["pblancNm"],
            "content": raw_data["bsnsSumryCn"],
            "deadline": raw_data["rcptEndDt"],
            "organization": raw_data["jrsdInsttNm"],
            "source": "bizinfo"
        }
```

### 3. 전처리 함수
```python
# preprocessors/cleaner.py
import re
from bs4 import BeautifulSoup

def clean_html(text: str) -> str:
    """HTML 태그 제거"""
    soup = BeautifulSoup(text, "html.parser")
    return soup.get_text()

def normalize_whitespace(text: str) -> str:
    """공백 정규화"""
    return re.sub(r'\s+', ' ', text).strip()

def clean_text(text: str) -> str:
    """텍스트 정제 파이프라인"""
    text = clean_html(text)
    text = normalize_whitespace(text)
    return text
```

### 4. 청커 (텍스트 분할)
```python
# preprocessors/chunker.py
from langchain.text_splitter import RecursiveCharacterTextSplitter

def create_chunker(
    chunk_size: int = 1000,
    chunk_overlap: int = 200
) -> RecursiveCharacterTextSplitter:
    return RecursiveCharacterTextSplitter(
        chunk_size=chunk_size,
        chunk_overlap=chunk_overlap,
        separators=["\n\n", "\n", ".", " "]
    )

def chunk_documents(
    documents: list[str],
    chunk_size: int = 1000,
    chunk_overlap: int = 200
) -> list[str]:
    chunker = create_chunker(chunk_size, chunk_overlap)
    chunks = []
    for doc in documents:
        chunks.extend(chunker.split_text(doc))
    return chunks
```

### 5. 파이프라인
```python
# pipelines/funding_pipeline.py
from crawlers.bizinfo import BizinfoCrawler
from crawlers.kstartup import KstartupCrawler
from preprocessors.cleaner import clean_text
from preprocessors.chunker import chunk_documents
from preprocessors.embedder import embed_documents

async def run_funding_pipeline():
    # 1. 수집
    bizinfo = BizinfoCrawler(api_key=BIZINFO_API_KEY)
    kstartup = KstartupCrawler(api_key=KSTARTUP_API_KEY)

    data = await bizinfo.run() + await kstartup.run()

    # 2. 정제
    cleaned = [clean_text(item["content"]) for item in data]

    # 3. 청킹
    chunks = chunk_documents(cleaned, chunk_size=1000)

    # 4. 임베딩 & 저장
    await embed_documents(chunks, collection="funding")

    return len(chunks)
```

## 데이터 스키마

### 지원사업 (funding)
```python
class FundingDocument:
    title: str           # 공고 제목
    content: str         # 공고 내용
    deadline: str        # 마감일 (YYYY-MM-DD)
    organization: str    # 주관기관
    target: str          # 지원 대상
    amount: str          # 지원 금액
    source: str          # 출처 (bizinfo, kstartup)
    url: str             # 원본 URL
```

### 법령 (law)
```python
class LawDocument:
    title: str           # 법령명
    article: str         # 조항 번호
    content: str         # 조항 내용
    level: int           # 계층 (1: 법령, 2: 시행령, 3: 시행규칙)
    parent: str | None   # 상위 법령
    effective_date: str  # 시행일
```

### 세무 (tax)
```python
class TaxDocument:
    title: str           # 제목
    category: str        # 카테고리 (법인세, 부가세, 원천세 등)
    content: str         # 내용
    year: int            # 연도
    source: str          # 출처
```

## 파일 수정 시 확인사항

### 새 크롤러 추가
1. `crawlers/base.py` 상속
2. `crawlers/{source}.py` 생성
3. `fetch()`, `parse()` 메서드 구현
4. `crawlers/__init__.py`에 export 추가

### 새 파이프라인 추가
1. `pipelines/{domain}_pipeline.py` 생성
2. 수집 → 정제 → 청킹 → 저장 단계 구현
3. `scripts/run_all.py`에 등록

### 청킹 전략 변경
1. `preprocessors/chunker.py` 수정
2. 도메인별 chunk_size, chunk_overlap 설정
3. 변경 후 전체 재인덱싱 필요

## 환경 변수
```
OPENAI_API_KEY=
BIZINFO_API_KEY=
KSTARTUP_API_KEY=
LAW_API_KEY=
CHROMA_HOST=localhost
CHROMA_PORT=8002
```

## 테스트
```bash
# 유닛 테스트
pytest tests/

# 크롤러 테스트 (API 호출)
pytest tests/crawlers/ -v

# 전처리 테스트
pytest tests/preprocessors/ -v
```

## 주의사항

### API 호출 제한
- 기업마당 API: 일 10,000건
- K-Startup API: 일 5,000건
- 법령 API: 일 10,000건

### 크롤링 에티켓
- robots.txt 준수
- 요청 간격: 최소 1초
- User-Agent 명시
- 에러 시 재시도 로직 (exponential backoff)

### 데이터 저장
- `raw/`: 원본 JSON/XML 저장 (디버깅용)
- `processed/`: 전처리된 데이터 저장
- 두 폴더 모두 `.gitignore`에 추가

### 벡터DB 동기화
- 증분 업데이트 우선 (전체 재인덱싱 최소화)
- 중복 문서 체크 (hash 기반)
- 삭제된 공고 처리 (soft delete)
