# Release Notes

## [2026-02-12] - 법령 전처리 대폭 개선 + 4대보험/세정세무 전처리 추가

### Features
- 4대보험 PDF 전처리 스크립트 추가 (`preprocess_hr_insurance_edu.py`)
- 세정세무 전처리 Upstage+OpenAI 연동 대폭 확장 (`preprocess_tax.py`)

### Refactoring
- 법령 전처리 대폭 개선: 조문 단위 분할, 소형 병합/대형 항 분할 로직 추가 (`preprocess_laws.py`)

## [2026-02-09] - 전처리 스크립트 추가 및 개선

### Features
- 세정세제 전처리 스크립트 추가 (preprocess_tax.py)
- 법령 전처리 스크립트 개선 (preprocess_laws.py 리팩토링)
- 추출 문서 정제 데이터 추가 (extracted_documents_cleaned.jsonl)

## [2026-02-08] - 초기 릴리즈

### 핵심 기능
- **법령 일괄 수집**: 국가법령정보센터 API, 페이지네이션 + 체크포인트 재개
- **노동 법령 수집**: 근로기준법, 최저임금법 등 노동 관련 법률/시행령/시행규칙
- **판례 수집**: 노동/세무 관련 판례
- **법령해석례 수집**: 중기부, 고용노동부, 국세청 해석례
- **지원사업 공고 수집**: 기업마당/K-Startup API, HWP 첨부파일 텍스트 추출, OpenAI 자동 정보 추출
- **PDF OCR 전처리**: 질의회시집 PDF에서 Q&A 추출 (easyocr + OpenCV + 템플릿 매칭)
- **통합 스키마 변환**: 법령, 판례, 해석례, 공고, 4대보험, 창업 가이드 JSONL 정규화
- **크롤링 에티켓 준수**: robots.txt 준수, 요청 간격 1초, exponential backoff

### 기술 스택
- Python 3.10+ + requests + httpx + BeautifulSoup4
- pymupdf + easyocr + OpenCV (PDF/OCR)
- olefile (HWP 처리)
- OpenAI API (텍스트 추출/요약)

### 파일 통계
- 총 파일: 17개
