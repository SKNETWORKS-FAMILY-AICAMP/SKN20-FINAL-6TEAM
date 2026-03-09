# Big Plan — 프로덕션 배포 준비 마스터 플랜

> 생성일: 2026-03-06
> 프로젝트: Bizi (RAG 기반 통합 비즈니스 컨설팅 챗봇)
> 스택: FastAPI + React/TypeScript + LangChain/LangGraph + ChromaDB + MySQL

---

## 프로젝트 현황 요약

| 항목 | 수치 |
|------|------|
| 총 파일 수 (deps 제외) | ~2,766개 |
| 서비스 | Backend(:8000), Frontend(:5173), RAG(:8001), Nginx(:80) |
| Docker Compose | 6개 → 3개로 정리 예정 |
| RAG 테스트 | 29개 (391 passed 기록) |
| Frontend 테스트 | E2E 1개 (docker-smoke) |
| Backend 테스트 | 0개 |

---

## 공통 원칙 — 의사결정 시 사용자 확인

> 모든 Task 수행 중 **여러 가지 접근 방법이 존재하는 경우**, 독단적으로 결정하지 않고 반드시 `AskUserQuestion`을 사용하여 사용자에게 선택지를 제시하고 확인을 받는다.
> 예: 삭제 vs 보관, 리팩토링 범위, 수정 방식, 대체 구현 전략 등

---

## 실행 순서

```
Task 1 — Initial Folder Cleanup
  └─ 불필요 파일 제거, 아티팩트 정리
      ↓
Task 2 — Bug Fixing
  └─ /chrome 브라우저 자동화 + 코드 분석으로 버그 식별/수정
      ↓
Task 3 — Security Audit
  └─ OWASP Top 10 기준 보안 감사 + 취약점 수정
      ↓
Task 4 — Refactoring
  └─ 코드 품질 개선 (동작 변경 없음)
      ↓
Task 5 — Final Folder Cleanup
  └─ Task 2~4 과정에서 생긴 잔여물 최종 정리
```

---

## Task별 범위 요약

### ✅ Task 1 — Initial Folder Cleanup (완료 2026-03-09)
- Windows 아티팩트 (`nul` 파일 2개) 제거
- 빈 파일 (`convert_log.txt`) 제거
- 루트 잡 파일 (`package-lock.json` 102B) 제거
- Docker Compose 3개 제거 (local, no-rag, override)
- 관련 nginx 설정 파일 정리 (`nginx.local.conf`)
- RAG 로그/결과 파일 정리
- `chromadb_backup.*` 대용량 백업 처리
- `mock-rag/` 디렉토리 전체 삭제 + 참조를 일반 rag로 수정
- **유지**: `산출물/`, `test/`, `.gitignore`, `.git/info`

### ✅ Task 2 — Bug Fixing (완료 2026-03-09)
- Docker 환경 기동 → /chrome으로 실제 UI/UX 테스트
- 채팅 플로우 (입력 → 스트리밍 → 출처 표시)
- 인증 플로우 (Google OAuth → 로그인/로그아웃)
- 기업 등록/수정/삭제
- 일정 관리 (캘린더)
- 관리자 대시보드
- 가이드 페이지
- Edge case: 빈 입력, 특수문자, 동시 요청, 네트워크 오류
- **크로스 기능 통합 테스트**: 여러 페이지/기능을 교차 사용 시 발생하는 상태 충돌, 메모리 누수, 경쟁 조건 검증

### ✅ Task 3 — Security Audit (완료 2026-03-09)
- `.env` / `.ssh/` Git 추적 여부 확인
- XSS: React dangerouslySetInnerHTML, markdown 렌더링
- CSRF: 미들웨어 동작 검증
- 인증: JWT 토큰 라이프사이클, 블랙리스트
- API 권한: 엔드포인트별 인증 확인
- 입력 검증: Pydantic 스키마 완전성
- CORS: 프로덕션 설정
- 의존성: known vulnerabilities 스캔

### ✅ Task 4 — Refactoring (완료 2026-03-09)
- 중복 코드 제거
- 컴포넌트 구조 개선 (530줄 CompanyForm 등)
- 명명 일관성
- 에러 핸들링 구조화
- 미사용 의존성 제거
- 모듈 구조 정리
- **모듈/함수 문서화**: 모듈 docstring + public API docstring 추가 (자명한 코드에는 불필요)

### Task 5 — Final Folder Cleanup
- Task 2~4 과정에서 생성된 임시 파일 제거
- 빌드 아티팩트 정리
- 최종 디렉토리 구조 검증
- 문서 동기화 (CLAUDE.md, AGENTS.md)
- **파일 재배치**: `PRD.md` → `docs/PRD.md`, `migrate_chroma_volume.sh` → `scripts/vectordb/migrate_chroma_volume.sh`

---

## 의사결정 기록

| 항목 | 결정 | 이유 |
|------|------|------|
| `산출물/` | 유지 | 프로젝트 히스토리 보존 |
| `test/` | 유지 | 추후 Git 포함 예정 |
| Docker Compose | 3개 유지 (yaml, prod, e2e) | 프로덕션 + 테스트만 필요 |
| /chrome 테스트 | 포함 | 실제 UI/UX 버그 탐색에 활용 |

---

## 세부 계획 파일

- [Task1_FolderCleanup_Initial.md](./Task1_FolderCleanup_Initial.md)
- [Task2_BugFixing.md](./Task2_BugFixing.md)
- [Task3_SecurityAudit.md](./Task3_SecurityAudit.md)
- [Task4_Refactoring.md](./Task4_Refactoring.md)
- [Task5_FolderCleanup_Final.md](./Task5_FolderCleanup_Final.md)
