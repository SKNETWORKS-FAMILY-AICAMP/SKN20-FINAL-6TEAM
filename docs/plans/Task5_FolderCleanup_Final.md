# Task 5 — Final Folder Cleanup

> 목표: Task 2~4 완료 후 최종 저장소 상태를 프로덕션 배포에 적합하게 정리한다.
> 원칙: Task 1과 동일 규칙 적용. 추가로 Task 2~4에서 발생한 잔여물까지 포함.
> **주의: 이 계획은 초안이며, Task 4까지 무결하게 완료된 후 실제 저장소 상태를 기반으로 재검증/수정할 예정.**

---

## Phase 1 — Task 2~4 잔여물 점검

### 1.1 버그 수정 과정 잔여물
| 점검 대상 | 조치 |
|----------|------|
| 디버깅용 `console.log` 추가 | 제거 (vite.config.ts에서 프로덕션 drop 확인) |
| 디버깅용 `print()` / `logger.debug()` | 불필요한 것 제거 |
| 임시 테스트 파일 | 정식 테스트가 아니면 제거 |
| `/chrome` 테스트 중 생성된 스크린샷/GIF | 제거 |

### 1.2 보안 수정 과정 잔여물
| 점검 대상 | 조치 |
|----------|------|
| 보안 스캔 결과 파일 | 문서로 보관 또는 제거 |
| 임시 패치 파일 | 정식 코드에 통합 확인 |

### 1.3 리팩토링 과정 잔여물
| 점검 대상 | 조치 |
|----------|------|
| 빈 파일 (모듈 분리 후 잔여) | 제거 |
| 미사용 import | 제거 |
| 백업 파일 (`.bak`, `.orig`) | 제거 |
| 주석 처리된 코드 블록 | 제거 |

---

## Phase 2 — 빌드 아티팩트 정리

### 점검 항목
| 대상 | 조치 |
|------|------|
| `frontend/dist/` | `.gitignore`에 포함 확인. 로컬 빌드 잔여물 삭제 |
| `__pycache__/` 디렉토리 | `.gitignore`에 포함 확인. 로컬 정리 |
| `.pytest_cache/` | `.gitignore`에 포함 확인. 로컬 정리 |
| `node_modules/` | `.gitignore`에 포함 확인 |
| `rag/output/` | 동적 생성 디렉토리 — 비어있어야 함 |

---

## Phase 3 — 파일 재배치

### 이동 대상
| 현재 위치 | 이동 위치 | 사유 |
|----------|----------|------|
| `PRD.md` (루트) | `docs/PRD.md` | 프로젝트 요구사항 문서 — docs 하위가 논리적 |
| `migrate_chroma_volume.sh` (루트) | `scripts/vectordb/migrate_chroma_volume.sh` | ChromaDB 볼륨 마이그레이션 — scripts/vectordb 하위에 관련 스크립트 존재 |

### 실행 절차
1. `git mv PRD.md docs/PRD.md`
2. `git mv migrate_chroma_volume.sh scripts/vectordb/migrate_chroma_volume.sh`
3. 프로젝트 전체에서 이전 경로 참조 검색 및 업데이트:
   - `grep -rn "PRD.md" --include="*.md" --include="*.py" --include="*.ts"`
   - `grep -rn "migrate_chroma_volume" --include="*.md" --include="*.sh" --include="*.yaml"`
4. `CLAUDE.md`, `README.md` 등에서 경로 참조 수정

---

## Phase 4 — 디렉토리 구조 최종 검증

### 기대 구조
```
SKN20-FINAL-6TEAM/
├── .claude/             # Claude Code 설정
├── backend/             # FastAPI Backend
│   ├── apps/            # 기능 모듈
│   ├── config/          # 설정
│   ├── scripts/         # DB 스크립트
│   ├── Dockerfile       # 개발 빌드
│   ├── Dockerfile.prod  # 프로덕션 빌드
│   └── requirements.txt
├── frontend/            # React Frontend
│   ├── src/             # 소스 코드
│   ├── e2e/             # E2E 테스트
│   ├── public/          # 정적 자산
│   └── package.json
├── rag/                 # RAG Service
│   ├── agents/          # 도메인 에이전트
│   ├── chains/          # RAG 체인
│   ├── routes/          # API 라우트
│   ├── utils/           # 유틸리티
│   ├── tests/           # 테스트
│   ├── schemas/         # Pydantic 스키마
│   ├── vectorstores/    # ChromaDB 설정
│   ├── evaluation/      # RAGAS 평가
│   └── requirements.txt
├── scripts/             # 운영 스크립트
│   ├── batch/           # 배치 작업
│   ├── crawling/        # 데이터 수집
│   ├── preprocessing/   # 전처리
│   └── vectordb/        # 벡터DB 빌드
├── data/                # 원천 데이터
├── docs/                # 문서 (PRD.md 포함)
├── tasks/               # 작업 기록
├── test/                # 임시 테스트 (추후 Git 포함 예정)
├── 산출물/               # 주차별 산출물
├── qa_test/             # QA 테스트 데이터
├── runpod-inference/    # RunPod 추론 서버
├── docker-compose.yaml       # 기본 환경
├── docker-compose.prod.yaml  # 프로덕션
├── docker-compose.e2e-test.yaml  # E2E 테스트
├── nginx.conf                # 기본 Nginx
├── nginx.prod.conf           # 프로덕션 Nginx
├── Dockerfile.batch          # 배치 빌드
├── Dockerfile.nginx          # Nginx 빌드
├── .env.example              # 환경변수 템플릿
├── .gitignore
├── CLAUDE.md
├── AGENTS.md
└── README.md
```

### 제거 확인 (Task 1에서 삭제)
- [ ] `nul` (루트)
- [ ] `rag/nul`
- [ ] `package-lock.json` (루트)
- [ ] `qa_test/convert_log.txt`
- [ ] `docker-compose.local.yaml`
- [ ] `docker-compose.no-rag.yaml`
- [ ] `docker-compose.override.yaml`
- [ ] `nginx.local.conf`

---

## Phase 5 — 문서 동기화

### 업데이트 대상
| 문서 | 점검 내용 |
|------|----------|
| `CLAUDE.md` | Commands 섹션 — 제거된 compose 파일 참조 |
| `README.md` | 프로젝트 설명, 시작 가이드 정확성 |
| `AGENTS.md` | 에이전트 역할 설명 최신화 |
| `docs/PRD.md` | 요구사항 상태 (✅/🔧/❌) 최종 갱신 (Phase 3에서 재배치 후) |
| `backend/CLAUDE.md` | Backend 관련 변경사항 반영 |
| `frontend/CLAUDE.md` | Frontend 관련 변경사항 반영 |
| `rag/CLAUDE.md` | RAG 관련 변경사항 반영 |
| `docs/plans/` | 실행 계획 최종 상태 업데이트 |

---

## Phase 6 — 최종 검증

### 빌드 검증
```bash
# Frontend 빌드
cd frontend && npm run build

# Docker 빌드 (전체)
docker compose -f docker-compose.yaml config
docker compose -f docker-compose.prod.yaml config
docker compose -f docker-compose.e2e-test.yaml config
```

### 테스트 실행
```bash
# Backend
.venv/bin/pytest backend/tests/ -v

# RAG
.venv/bin/pytest rag/tests/ -v

# Frontend
cd frontend && npm run test

# Lint
ruff check backend/ rag/
cd frontend && npx eslint .

# Typecheck
cd frontend && npx tsc --noEmit
```

### Git 상태 확인
```bash
git status          # 의도하지 않은 변경 없는지
git diff --stat     # 변경 범위 확인
git log --oneline -5  # 최근 커밋 확인
```

---

## Phase 7 — 최종 커밋 및 태그

### 실행 절차
1. 모든 변경사항 스테이징
2. 커밋 메시지: `[chore] 프로덕션 배포 준비 — 최종 정리`
3. 태그 생성 검토: `v1.0.0-rc1` (Release Candidate)
4. 사용자 확인 후 push
