# Release Notes

## [2026-02-20] - 지원사업 공고 배치 스케줄러 구현 (Docker + systemd)

### Features
- **Dockerfile.batch**: torch 제외 경량 배치 이미지 (~1.5GB), RunPod 임베딩 사용
- **Dockerfile.batch.dockerignore**: Nginx용 `.dockerignore`와 분리하여 `scripts/`, `rag/` 포함
- **scripts/batch/requirements.txt**: 배치 전용 의존성 (beautifulsoup4, chromadb, langchain 등)
- **scripts/batch/setup-scheduler.sh**: EC2 systemd 자동 설치 스크립트 (타임존, dry-run, 유닛 설치 포함)
- **docker-compose.prod.yaml**: `batch-updater` 서비스 추가 (`profile: batch`, 메모리 512M)
- **scripts/batch/update_announcements.py**: Slack Webhook → Email SMTP 알림 전환 (smtplib, STARTTLS)
- **.env.example**: SMTP 환경변수 6개 추가 (SMTP_HOST/PORT/USER/PASSWORD/FROM/TO)
- **systemd 유닛**: `docker compose run --rm batch-updater` 방식 전환, 스케줄 18:30 변경
- **scripts/__init__.py** 외 2개: 네임스페이스 패키지 안전장치 추가

## [2026-02-19] - 헬스체크 스크립트 수정 + ChromaDB 메모리 증설

### Bug Fixes
- **health-check.sh**: HTTP→HTTPS 301 리다이렉트 우회 — `curl http://localhost` 대신 `docker exec python` 내부 직접 체크로 변경, 도메인 지정 시 HTTPS curl 프록시 체크 추가 (nginx.prod.conf의 HTTP→HTTPS 리다이렉트와 충돌 해소)
- **docker-compose.prod.yaml**: ChromaDB 메모리 512M→768M 증설 (95% 사용률 OOM 방지)

## [2026-02-19] - 배포 자동화 스크립트 + 복원 스크립트 호환성 개선

### Features
- **배포 자동화 스크립트** (`deploy.sh`): 서비스 자동 배포 스크립트 추가
- **헬스체크 스크립트** (`health-check.sh`): 서비스 헬스체크 스크립트 추가

### Chores
- **chromadb-restore.sh 호환성 개선**: `bc` 미설치 환경에서 `awk` 폴백 처리 추가

## [2026-02-17] - 지원사업 공고 배치 갱신 + VectorDB 빌드 스크립트 + 보안 유틸리티

### Features
- **지원사업 공고 배치 스크립트** (`scripts/batch/update_announcements.py`): 기업마당/K-Startup API에서 공고 수집 → DB upsert, Slack 알림, systemd 타이머 설정 포함
- **S3 업로더** (`scripts/batch/s3_uploader.py`): 공고 첨부파일 S3 업로드 유틸리티
- **VectorDB 빌드 스크립트** (`scripts/vectordb/`): ChromaDB 벡터 인덱스 빌드 — `__main__.py` (CLI 진입점), `builder.py` (빌드 로직), `loader.py` (데이터 로더)
- **환경변수 검증** (`scripts/validate_env.py`): 필수 환경변수 존재 여부 사전 검증
- **시크릿 로더** (`scripts/load_secrets.sh`): AWS Secrets Manager에서 .env 파일 생성

### Security
- **Slack 알림 에러 마스킹** (`update_announcements.py`): `_safe_error_message()` 헬퍼 — DB 연결 에러 시 호스트/비밀번호 노출 방지 (6곳 적용)

## [2026-02-15] - ChromaDB 백업/복원 스크립트 추가

### Features
- ChromaDB Docker 컨테이너 백업/복원 셸 스크립트 추가 (`chromadb-backup.sh`, `chromadb-restore.sh`)

### Bug Fixes
- ChromaDB 백업/복원 스크립트 버그 수정 (Docker 설정 개선)

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
