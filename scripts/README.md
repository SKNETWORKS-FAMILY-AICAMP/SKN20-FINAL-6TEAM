# Scripts - 데이터 크롤링 및 전처리

> Bizi RAG 시스템에 필요한 데이터를 외부 소스에서 수집하고, VectorDB 입력용 JSONL로 전처리하는 스크립트 모음입니다.

## 주요 기능

- **법령 수집**: 국가법령정보센터 API로 법령/해석례/판례 일괄 수집
- **공고 수집**: 기업마당/K-Startup API로 지원사업 공고 수집, HWP 첨부파일 텍스트 추출
- **PDF OCR**: 질의회시집 등 PDF 파일에서 Q&A 추출 (easyocr + OpenCV)
- **통합 스키마 변환**: 모든 데이터를 동일한 JSONL 스키마로 정규화

## 기술 스택

| 구분 | 기술 |
|------|------|
| 언어 | Python 3.10+ |
| HTTP | requests, httpx |
| 크롤링 | BeautifulSoup4 |
| PDF/OCR | pymupdf, easyocr, OpenCV |
| HWP | olefile |
| AI 추출 | OpenAI API |

## 데이터 흐름

```
외부 소스 (API, PDF, HWP)
        |  scripts/crawling/*
        v
data/origin/             (원본 데이터)
        |  scripts/preprocessing/*
        v
data/preprocessed/       (JSONL - RAG 입력용)
        |  rag/vectorstores/
        v
ChromaDB                 (벡터 DB)
```

## 크롤러

### collect_all_laws.py - 전체 법령 수집

```bash
python collect_all_laws.py --api-key YOUR_KEY
python collect_all_laws.py --max 100    # 테스트용 100개만
```

- 페이지네이션 순회, 체크포인트 저장 (중단 후 재개 가능)

### collect_labor_laws.py - 노동 관련 법령

근로기준법, 최저임금법, 퇴직급여보장법 등 노동 관련 법률/시행령/시행규칙 수집

### collect_court_cases.py - 판례 수집

노동/세무 관련 판례 수집

### collect_law_interpretations.py - 법령해석례 수집

중기부, 고용노동부, 국세청 등의 법령해석례 수집

### collect_announcements.py - 지원사업 공고 수집

```bash
python collect_announcements.py
```

- 기업마당/K-Startup API 호출
- HWP 첨부파일 다운로드 및 텍스트 추출
- OpenAI API로 지원대상/제외대상/지원금액 자동 추출

## 전처리기

| 스크립트 | 입력 | 출력 |
|---------|------|------|
| `preprocess_announcements.py` | `data/origin/announcements/*.json` | `data/preprocessed/funding/announcements.jsonl` |
| `preprocess_laws.py` | `law-raw/01_laws_full.json`, `expc_*.json` | `data/preprocessed/law/laws_full.jsonl`, `interpretations.jsonl` |
| `preprocess_court_cases.py` | `law-raw/prec_*.json` | `data/preprocessed/law/court_cases_*.jsonl` |
| `preprocess_labor_qa.py` | `data/origin/근로기준법 질의회시집.pdf` | `data/preprocessed/labor/labor_qa.jsonl` |
| `preprocess_hr_insurance.py` | 4대보험 데이터 | `data/preprocessed/labor/hr_major_insurance.jsonl` |
| `preprocess_startup_procedures.py` | `data/origin/startup_support/*.json` | `data/preprocessed/startup_support/startup_procedures.jsonl` |
| `preprocess_startup_guide.py` | 업종별 창업 가이드 | `data/preprocessed/startup_support/industry_startup_guide.jsonl` |

### 실행 예시

```bash
python -m scripts.preprocessing.preprocess_laws
python -m scripts.preprocessing.preprocess_court_cases
python -m scripts.preprocessing.preprocess_labor_qa
python -m scripts.preprocessing.preprocess_announcements
```

## 환경 변수

| 변수 | 설명 | 필수 |
|------|------|------|
| `K-STARTUP_API_KEY` | K-Startup API 키 | O |
| `BIZINFO_API_KEY` | 기업마당 API 키 | O |
| `LAW_API_KEY` | 국가법령정보센터 API 키 | O |
| `OPENAI_API_KEY` | OpenAI API 키 (텍스트 추출용) | O |
| `DATA_ORIGIN_PATH` | 원본 데이터 경로 (기본: `data/origin`) | - |
| `DATA_PROCESSED_PATH` | 전처리 데이터 경로 (기본: `data/preprocessed`) | - |

## 관련 문서

- [데이터 스키마 정의](../docs/DATA_SCHEMA.md)
- [전처리 파이프라인 상세](./data_pipeline.md)
- [데이터 폴더 가이드](../data/CLAUDE.md)
- [RAG 서비스](../rag/README.md)
