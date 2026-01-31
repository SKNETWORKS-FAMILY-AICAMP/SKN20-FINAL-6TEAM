# Scripts AI 에이전트 가이드

> **이 문서는 RAG 에이전트 및 다른 AI 시스템을 위한 가이드입니다.**
> Claude Code 개발 가이드는 [CLAUDE.md](./CLAUDE.md)를 참조하세요.

## 개요

`scripts/` 폴더는 Bizi RAG 시스템에 필요한 데이터를 수집하고 전처리하는 스크립트를 관리합니다.
- `crawling/`: 외부 API/웹에서 데이터 수집
- `preprocessing/`: 원본 데이터를 RAG용 JSONL로 변환

## 프로젝트 구조

```
scripts/
├── CLAUDE.md                      # 상세 개발 가이드
├── AGENTS.md                      # 이 파일
├── data_pipeline.md               # 전처리 파이프라인 상세 설명
│
├── crawling/                      # 데이터 수집
│   ├── announcement_collector.py  # 기업마당/K-Startup 공고 수집
│   ├── law_collector.py           # 법령 수집
│   ├── collect_all_laws.py        # 전체 법령 일괄 수집
│   ├── collect_court_cases.py     # 판례 수집
│   └── collect_law_interpretations.py  # 해석례 수집
│
└── preprocessing/                 # 데이터 전처리
    ├── announcement_preprocessor.py    # 공고 전처리
    ├── law_preprocessor.py             # 법령/해석례/판례 전처리
    ├── startup_guide_preprocessor.py   # 창업 가이드 전처리
    ├── startup_procedures_preprocessor.py  # 창업 절차 전처리
    ├── labor_qa_preprocessor.py        # 노동 질의회시 PDF 전처리
    └── court.py                        # 판례 전처리
```

## 코드 작성 규칙

### 1. 크롤러 작성

```python
"""
{데이터소스} 수집기

{API/웹사이트 설명}
{API 문서 URL}

수집 대상:
- {수집 항목 1}
- {수집 항목 2}
"""
import os
import httpx
from dataclasses import dataclass
from typing import List, Dict, Optional

# 환경 변수에서 API 키 로드
API_KEY = os.getenv("API_KEY_NAME", "")

# 상수 정의 (하드코딩 금지)
BASE_URL = "https://api.example.com"
TIMEOUT = 30


@dataclass
class CollectedItem:
    """수집된 데이터 구조"""
    id: str
    title: str
    content: str
    # ...


class DataCollector:
    """데이터 수집기"""

    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or API_KEY

    async def fetch(self, query: str) -> List[Dict]:
        """데이터 조회"""
        async with httpx.AsyncClient(timeout=TIMEOUT) as client:
            response = await client.get(
                f"{BASE_URL}/search",
                params={"key": self.api_key, "q": query}
            )
            response.raise_for_status()
            return response.json()

    def parse(self, raw_data: Dict) -> CollectedItem:
        """원본 데이터 파싱"""
        return CollectedItem(
            id=raw_data.get("id", ""),
            title=raw_data.get("title", ""),
            content=raw_data.get("content", ""),
        )
```

### 2. 전처리기 작성

```python
"""
{데이터타입} 전처리기

{입력 데이터 설명}
{출력 데이터 설명}

Usage:
    python -m scripts.preprocessing.{module_name}
"""
import json
import re
from pathlib import Path
from dataclasses import dataclass, asdict
from typing import List, Dict, Optional

# 경로 설정 (하드코딩 금지)
PROJECT_ROOT = Path(__file__).parent.parent.parent
INPUT_DIR = PROJECT_ROOT / "data" / "origin" / "{source}"
OUTPUT_DIR = PROJECT_ROOT / "data" / "preprocessed" / "{domain}"


@dataclass
class Document:
    """통합 스키마"""
    id: str
    type: str
    domain: str
    title: str
    content: str
    metadata: Dict


def clean_text(text: str) -> str:
    """텍스트 정제"""
    if not text:
        return ""
    # HTML 태그 제거
    text = re.sub(r'<[^>]+>', '', text)
    # 연속 공백 정리
    text = re.sub(r'\s+', ' ', text)
    return text.strip()


def process_file(input_path: Path) -> List[Document]:
    """파일 처리"""
    with open(input_path, 'r', encoding='utf-8') as f:
        data = json.load(f)

    documents = []
    for item in data:
        doc = Document(
            id=f"PREFIX_{item['id']}",
            type="document_type",
            domain="domain_name",
            title=item.get("title", ""),
            content=clean_text(item.get("content", "")),
            metadata={}
        )
        documents.append(doc)

    return documents


def write_jsonl(documents: List[Document], output_path: Path):
    """JSONL 출력"""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, 'w', encoding='utf-8') as f:
        for doc in documents:
            f.write(json.dumps(asdict(doc), ensure_ascii=False) + '\n')


if __name__ == "__main__":
    documents = process_file(INPUT_DIR / "input.json")
    write_jsonl(documents, OUTPUT_DIR / "output.jsonl")
    print(f"Processed {len(documents)} documents")
```

## 통합 스키마

상세 스키마 정의는 [docs/DATA_SCHEMA.md](../docs/DATA_SCHEMA.md)를 참조하세요.

**필수 필드**: `id`, `type`, `domain`, `title`, `content`, `source`

## 파일 수정 시 확인사항

### 새 크롤러 추가

1. `crawling/{source}_collector.py` 생성
2. 환경 변수에 API 키 추가 (`.env`)
3. `CLAUDE.md` 문서 업데이트

### 새 전처리기 추가

1. `preprocessing/{type}_preprocessor.py` 생성
2. 통합 스키마 준수
3. 입출력 경로 상수로 정의
4. `CLAUDE.md` 문서 업데이트

### 스키마 변경

1. 기존 전처리기 모두 수정
2. `data/CLAUDE.md` 스키마 정의 업데이트
3. 벡터DB 재인덱싱 필요

## 환경 변수

```bash
# .env (프로젝트 루트)
K-STARTUP_API_KEY=          # K-Startup API
BIZINFO_API_KEY=            # 기업마당 API
LAW_API_KEY=                # 국가법령정보센터 API
OPENAI_API_KEY=             # OpenAI (텍스트 추출용)
```

## 코드 품질 가이드라인

### 금지 사항

- **하드코딩 금지**: API 키, 파일 경로, URL 등을 코드에 직접 작성 금지
- **매직 넘버 금지**: 임계값, 설정값은 상수로 정의
- **API 키 노출 금지**: 로그/출력에 API 키 포함 금지
- **중복 코드 금지**: 공통 로직은 유틸 함수로 추출

### 필수 사항

- **환경 변수 사용**: 모든 설정값은 `.env` 또는 환경 변수로 관리
- **상수 정의**: 설정값은 모듈 상단에 상수로 정의
- **타입 힌트 사용**: 함수 파라미터와 반환값에 타입 힌트 필수
- **에러 처리**: API 호출 실패, 파싱 오류 등 예외 처리 필수
- **로깅**: logging 모듈 사용 (print 대신)
- **docstring**: 모듈, 클래스, 함수에 docstring 작성

## 테스트

```bash
# 개별 전처리기 실행
python -m scripts.preprocessing.law_preprocessor
python -m scripts.preprocessing.announcement_preprocessor

# 출력 확인
head -3 data/preprocessed/law/laws_full.jsonl | jq .
wc -l data/preprocessed/*/*.jsonl
```

## 크롤링 에티켓

- robots.txt 준수
- 요청 간격: 최소 1초
- User-Agent 명시
- 에러 시 재시도 로직 (exponential backoff)
- API 호출 제한 준수

## 참고 문서

- [docs/DATA_SCHEMA.md](../docs/DATA_SCHEMA.md) - 통합 스키마 정의
- [CLAUDE.md](./CLAUDE.md) - 상세 개발 가이드
- [data_pipeline.md](./data_pipeline.md) - 전처리 파이프라인 상세 설명
- [data/CLAUDE.md](../data/CLAUDE.md) - 데이터 폴더 가이드
