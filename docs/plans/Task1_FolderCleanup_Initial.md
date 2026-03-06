# Task 1 — Initial Folder Cleanup

> 목표: 프로덕션 배포 전 불필요한 파일/아티팩트를 제거하여 저장소를 정리한다.
> 원칙: 기능 수정 없음. 리팩토링 아님. 테스트 파일 삭제 금지. `.gitignore`/`.git/info` 수정 금지.
> 의사결정: 삭제/보관/재배치 등 여러 방법이 가능한 경우, `AskUserQuestion`으로 사용자에게 선택지를 제시하고 확인을 받은 후 진행한다.

---

## Phase 1 — Windows 아티팩트 및 빈 파일 제거

### 대상 파일
| 파일 | 크기 | 사유 |
|------|------|------|
| `/nul` | 0B | Windows `NUL` 디바이스 리다이렉트 실수로 생성된 파일 |
| `rag/nul` | 0B | 동일 |
| `qa_test/convert_log.txt` | 0B | 빈 로그 파일 (변환 결과 없음) |
| `package-lock.json` (루트) | 102B | 빈 lock 파일 (packages: {}) — 루트에 package.json 없음 |

### 실행 절차
1. 각 파일이 Git에서 추적되지 않음을 확인 (`git ls-files <path>`)
2. 추적 중이면 `git rm --cached` 후 삭제
3. 추적되지 않으면 직접 삭제
4. 전체 테스트 실행하여 영향 없음 확인

---

## Phase 2 — Docker Compose 파일 정리

### 제거 대상
| 파일 | 용도 | 제거 사유 |
|------|------|-----------|
| `docker-compose.local.yaml` | 로컬 개발 (ChromaDB + local model) | 프로덕션 불필요 |
| `docker-compose.no-rag.yaml` | RAG 없는 테스트 | 프로덕션 불필요 |
| `docker-compose.override.yaml` | Docker Compose 자동 오버라이드 | 프로덕션에서 의도치 않은 오버라이드 위험 |

### 유지 대상
| 파일 | 용도 |
|------|------|
| `docker-compose.yaml` | 기본 개발/스테이징 환경 |
| `docker-compose.prod.yaml` | 프로덕션 배포 |
| `docker-compose.e2e-test.yaml` | E2E 테스트 |

### 관련 정리
| 파일 | 조치 |
|------|------|
| `nginx.local.conf` | `docker-compose.local.yaml` 전용 → 제거 |
| `nginx.conf` | `docker-compose.yaml` 용 → 유지 |
| `nginx.prod.conf` | `docker-compose.prod.yaml` 용 → 유지 |

### 실행 절차
1. 제거 대상 파일들의 참조 확인 (scripts/, docs/ 등에서 참조 여부)
2. `CLAUDE.md`의 Commands 섹션에서 `docker-compose.local.yaml` 참조 업데이트
3. 파일 삭제
4. 나머지 compose 파일이 정상 동작하는지 `docker compose -f <file> config` 로 검증

---

## Phase 3 — RAG 로그/결과 파일 정리

### 대상 파일
| 파일 | 크기 | 사유 |
|------|------|------|
| `rag/log.txt` | 37KB | 1월 29일자 오래된 로그 |
| `rag/logs/` 디렉토리 | ~263KB | `.gitignore`에 `logs` 포함 → Git 미추적. 로컬 정리만 |
| `rag/output/` 디렉토리 | 가변 | 생성된 문서 임시 저장소 — 프로덕션에서는 동적 생성 |
| `rag/results/` 디렉토리 | ~3개 JSON | 평가 결과 — `.gitignore` 확인 후 처리 |

### 실행 절차
1. `git ls-files` 로 각 파일의 Git 추적 여부 확인
2. 추적되는 파일만 `git rm` 으로 제거
3. 미추적 파일은 로컬에서만 삭제 (선택적)

---

## Phase 4 — 대용량 백업 파일 처리

### 대상
| 파일 | 크기 | 사유 |
|------|------|------|
| `chromadb_backup.tar.gz` | 742MB | 벡터DB 백업 — `.gitignore`에 포함 |
| `chromadb_backup.manifest` | 81B | 백업 메니페스트 — `.gitignore`에 포함 |

### 실행 절차
1. `.gitignore`에 이미 포함되어 Git 미추적임을 확인
2. 백업이 다른 곳(S3 등)에 보관되어 있는지 확인
3. 로컬 디스크 정리 목적으로만 삭제 (Git 커밋 불필요)

---

## Phase 5 — mock-rag 디렉토리 삭제

### 대상
- `mock-rag/` 디렉토리 전체 (`Dockerfile` + `main.py`)

### 실행 절차
1. 프로젝트 전체에서 `mock-rag` 참조 검색:
   - `grep -rn "mock-rag" --include="*.yaml" --include="*.md" --include="*.sh" --include="*.py" --include="*.ts"`
2. 발견된 참조를 일반 `rag` 서비스로 수정 (docker-compose 서비스명, URL 등)
3. `mock-rag/` 디렉토리 삭제 (`git rm -r mock-rag/`)
4. 수정된 compose 파일 검증: `docker compose -f <file> config`

---

## Phase 6 — 기타 정리 및 문서 참조 업데이트

### 점검 항목
| 항목 | 조치 |
|------|------|
| `migrate_chroma_volume.sh` (루트) | Task 5에서 `scripts/vectordb/`로 재배치 예정 → **유지** |
| `Dockerfile.batch` + `.dockerignore` | batch job 용 — 사용 중이면 유지 |
| `Dockerfile.nginx` | nginx 빌드용 — 사용 중이면 유지 |
| `cli.py` (루트) | RAG CLI 진입점 — `rag/cli.py`와 중복 여부 확인 |
| `.ssh/` | `.gitignore`에 포함 확인. Git 미추적이면 로컬 전용으로 유지 |

### 문서 업데이트
- `CLAUDE.md`: `docker-compose.local.yaml` 참조 제거/수정
- `README.md`: 제거된 파일 참조가 있으면 수정
- `scripts/README.md`: 관련 참조 업데이트

---

## Phase 7 — 검증

### 체크리스트
- [ ] `git status` 로 의도한 파일만 변경되었는지 확인
- [ ] `docker compose -f docker-compose.yaml config` 정상
- [ ] `docker compose -f docker-compose.prod.yaml config` 정상
- [ ] `docker compose -f docker-compose.e2e-test.yaml config` 정상
- [ ] `.venv/bin/pytest backend/tests/ -v` 통과
- [ ] `.venv/bin/pytest rag/tests/ -v` 통과
- [ ] `cd frontend && npm run test` 통과
- [ ] 삭제한 파일이 테스트에서 참조되지 않음
- [ ] 기능 변경 없음 확인
