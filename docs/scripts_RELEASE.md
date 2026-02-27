# Release Notes

## [2026-02-27] - clean_jsonl.py 추가 + 로컬 nginx 서비스명 수정

### Features
- **JSONL 정제 스크립트 추가** (`preprocessing/clean_jsonl.py`): RAG 학습 데이터 전처리용 JSONL 정제 유틸리티 추가 (294줄)

### Bug Fixes
- **로컬 nginx 서비스명 불일치 수정** (`nginx.local.conf` 신규, `docker-compose.local.yaml`): `nginx.conf`의 `rag:8001` 참조가 로컬 환경 서비스명 `mock-rag:8001`과 불일치하여 `/rag/*` 경로 502 발생 — `nginx.local.conf` 분리로 로컬/프로덕션 nginx 설정 독립화

## [2026-02-26] - .claude 설정 정리 및 docs/ 구조 재정비

### Chores
- **.claude/ 설정 파일 정리**: 에이전트(agent) 파일 간소화, 규칙(rules) 파일 경량화, 스킬(skills) 구조 재편 (`code-patterns/`, `test-guide/` 추가, `feature-planner/` 제거), `.claude/docs/` 불필요 문서 삭제
- **커밋 린트 훅 추가** (`.claude/hooks/commit-lint.sh`): 커밋 메시지 형식 검증 훅 신규 추가
- **tasks/ 디렉토리 추가**: `tasks/lessons.md` (실수/교훈 기록), `tasks/claude-improvement.md` (개선 추적) 신규 추가

### Documentation
- **docs/ 구조 재정비**: 보고서 파일들을 `docs/reports/`로 이동, 구버전 가이드를 `docs/archive/`로 이동, `docs/plans/` 신규 추가 (기능 계획 문서용)
- **루트 및 서비스별 CLAUDE.md·AGENTS.md 간소화**: 코드에서 파악 가능한 중복 내용 제거 — 프로젝트 고유 컨텍스트만 유지 (backend, frontend, rag, scripts, data 전 서비스 적용)
- **RULE.md 제거**: 규칙 파일은 `.claude/rules/` 경로로 통합
- **docker-compose.yaml nginx 로깅 설정 제거**: nginx 서비스에서 `json-file` 로그 드라이버 설정 제거 (로컬 dev 환경에서 불필요)

## [2026-02-25] - migrate_chroma_volume.sh 볼륨명 수정

### Bug Fixes
- **볼륨명 오류 수정** (`migrate_chroma_volume.sh`): EC2 실제 데이터 볼륨명이 `bizi_chromadb_data`임을 확인 — `skn20-final-6team_chromadb_data`(빈 볼륨)에서 복사하던 문제 수정

## [2026-02-25] - ChromaDB 볼륨 마이그레이션 스크립트 chmod 오류 수정

### Bug Fixes
- **migrate_chroma_volume.sh chmod 권한 오류 수정**: `cp -a`로 복사된 파일이 컨테이너 내부 root 소유라 호스트 사용자가 `chmod` 불가한 문제 수정 — `chmod -R 777 /dest/`를 `docker run` 내부에서 함께 실행하도록 변경

## [2026-02-25] - ChromaDB 볼륨 bind mount 전환 + 마이그레이션 스크립트

### Infrastructure
- **ChromaDB bind mount 전환** (`docker-compose.prod.yaml`): `chromadb_data` named volume → `./chroma-data:/data` bind mount로 변경 — 호스트 경로 직접 접근으로 볼륨 데이터 관리 단순화, `volumes:` 섹션에서 `chromadb_data` 선언 제거
- **마이그레이션 스크립트 추가** (`migrate_chroma_volume.sh`): 기존 named volume 데이터를 `./chroma-data/`로 복사 → 권한 설정 → `docker compose down/up` → ChromaDB 헬스체크(60초 폴링)까지 자동화 — 기존 named volume은 삭제하지 않으므로 수동 확인 후 제거 가능

## [2026-02-25] - 로그 영속화 및 S3 아카이브 배치 구현

### Features
- **로그 S3 업로드 배치** (`scripts/batch/upload_logs.py`): 로테이션된 로그 파일(.log.N)을 `logs/{service}/YYYY/MM/DD/{filename}` 구조로 S3에 업로드하는 배치 스크립트 신규 추가 — `--dry-run`, `--delete-after-upload`, `--service` 옵션 지원, docker-compose `log-uploader` 서비스(`profiles: ["logs"]`)로 실행
- **S3Uploader 로그 메서드 추가** (`scripts/batch/s3_uploader.py`): `generate_log_key(service, filename, date)` · `upload_log_file(file_path, service, date)` 메서드 추가 — 기존 공고문 업로드와 동일 버킷(`S3_BUCKET_NAME`) 사용
- **Nginx 로그 영속화** (`nginx.conf`, `docker-compose.yaml`): `access_log`/`error_log` 지시어 추가, `nginx-logs` named volume 마운트 및 Docker `json-file` 로그 드라이버(10MB × 3개) 설정 — 컨테이너 재시작 후에도 로그 보존

## [2026-02-24] - 이메일 알림 SMTP → AWS SES 통합

### Features
- **AWS SES 이메일 알림** (`scripts/batch/update_announcements.py`): smtplib/SMTP 제거, boto3 SES로 교체 — EC2 Instance Role 자동 인증, `SES_FROM`·`ALERT_EMAIL_TO` 미설정 시 graceful 건너뜀

## [2026-02-20] - 지원사업 공고 배치 스케줄러 구현 (Docker + systemd)

### Features
- **기업마당 비날짜 신청기간 LLM 판단** (`scripts/crawling/collect_announcements.py`): 상시·세부사업별 상이 등 날짜 파싱 불가 공고를 무조건 제외하던 문제 수정 — `_is_recruiting()` `bool | None` 반환, `date_ambiguous` 플래그 도입, `OpenAIAnalyzer.analyze(check_recruiting=True)`로 문서 본문 기반 LLM 모집 판단

### Bug Fixes
- **기업마당 API 날짜 형식 처리** (`scripts/crawling/collect_announcements.py`): `_is_recruiting()`이 `YYYYMMDD` 형식만 허용하여 공고 959개 전부 필터링되던 문제 수정 — 대시 제거 후 비교하여 `YYYY-MM-DD ~ YYYY-MM-DD` 형식 지원 추가
- **코드 리뷰 이슈 수정** (`scripts/vectordb/builder.py`, `scripts/vectordb/loader.py`, `scripts/batch/update_announcements.py`): upsert doc_id fallback 처리, `ANNOUNCEMENT_RETENTION_DAYS` 비정수값 안전 파싱, `load_db_documents()` `source_files` 필터 파라미터 추가
- **배치 스케줄러 EC2 유저 수정** (`scripts/batch/setup-scheduler.sh`, `scripts/batch/systemd/bizi-announcement-update.service`): `ubuntu` → `ec2-user` (Amazon Linux 계정명 수정)

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
