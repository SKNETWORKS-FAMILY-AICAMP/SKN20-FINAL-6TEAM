# Documentation Cleanup Plan

## Overview

프로젝트의 .md 문서들을 역할별로 정리하고, 깨진 참조 수정 및 폴더 재구성.

## 변경 계획

### 1. RAG 평가 보고서 → `docs/reports/` 이동

**대상 파일 (5개):**
- `docs/RAG_FEATURE_TOGGLE_AUDIT.md`
- `docs/RAGAS_V4_IMPROVEMENT_REPORT.md`
- `docs/RAGAS_V4_QUALITY_IMPROVEMENT.md`
- `docs/RAGAS_V4_REPORT.md`
- `docs/TOGGLE_OPTIMIZATION_RESULTS.md`

**Action:** `docs/reports/` 폴더 생성 후 이동. 이력용으로만 유지.

### 2. `docs/DOCKER_GUIDE.md` → 삭제 또는 archive

**이유:** 사용자 대상 실행 가이드이므로 Claude Code에 불필요. README.md에 이미 실행 방법 존재.
**Action:** `docs/archive/`로 이동.

### 3. `docs/LAW_DATA_PIPELINE.md` + `docs/DATA_SCHEMA.md` 병합 검토

**현황:**
- `DATA_SCHEMA.md` (604줄): 전체 데이터 통합 스키마
- `LAW_DATA_PIPELINE.md` (614줄): 법률 데이터 전처리 파이프라인

**Action:** `LAW_DATA_PIPELINE.md`에서 스키마 관련 내용을 `DATA_SCHEMA.md`로 병합. 파이프라인 고유 내용은 `scripts/` 참조로 대체. 사용자 확인 후 실행.

### 4. `frontend/FORM.md` 위치 확인

**현황:** `frontend/FORM.md` (2,346줄)은 `.claude/agents/react-form-architect.md`에서 참조됨. `.claude/` 내부에는 복사본 없음.
**역할:** `rag/ARCHITECTURE.md`와 동일 — "설계 먼저 확인 → 구체화 → 수정"하는 설계 문서.
**Action:** 현재 위치 유지 (agent가 `frontend/FORM.md`를 직접 참조). 변경 없음.

### 5. `AGENTS.md` 파일들 업데이트

**현황:** 각 서비스의 `AGENTS.md`는 Claude Code 미사용자를 위한 가이드.
**Action:** 각 `AGENTS.md`에 해당 서비스 `CLAUDE.md`의 핵심 내용 반영 (깨진 참조 수정 포함).

대상:
- `AGENTS.md` (root, 339줄)
- `backend/AGENTS.md` (66줄)
- `frontend/AGENTS.md` (58줄)
- `rag/AGENTS.md` (56줄)
- `scripts/AGENTS.md` (258줄)
- `data/AGENTS.md` (45줄)

### 6. `tasks/lessons.md` 생성

**현황:** root `CLAUDE.md`에서 참조하지만 파일이 존재하지 않음.
**Action:** 빈 템플릿 생성.

### 7. `docs/security/` — 유지

**현황:** `AWS_SECRETS_MIGRATION.md` (133줄), `PHASE0_AUDIT_REPORT.md` (306줄)
**Action:** 운영 문서이므로 현재 위치 유지. 변경 없음.

### 8. `docs/HUMAN_MARKDOWN.md` — 유지

**현황:** `/update-docs` 커맨드에서 사용하는 README/RELEASE 생성 템플릿 (159줄).
**Action:** 현재 위치 유지. 변경 없음.

### 9. `docs/*_RELEASE.md` — 유지

**현황:** `backend_RELEASE.md`, `frontend_RELEASE.md`, `rag_RELEASE.md`, `scripts_RELEASE.md`
**Action:** 이력용 누적 문서. 현재 위치 유지.

### 10. 건드리지 않는 파일

- `RULE.md`: 사용자가 직접 삭제 예정
- `산출물/`: 제출용, 열어보지 않음
- `PRD.md`: 사용자가 직접 처리 예정
- `Bizi_Claude_Code_improvement.md`: 이번 작업의 참조 문서
- `qa_test/*.md`: RAG 평가용 테스트 데이터셋
- `data/CLAUDE.md` (336줄): 간소화 대상이지만 이번 계획 범위 밖 (사용자 요청 시)

## 실행 순서

1. `docs/reports/` 생성 + RAG 보고서 5개 이동
2. `docs/archive/` 생성 + `DOCKER_GUIDE.md` 이동
3. `tasks/lessons.md` 템플릿 생성
4. `AGENTS.md` 파일들에 CLAUDE.md 핵심 내용 반영
5. `LAW_DATA_PIPELINE.md` + `DATA_SCHEMA.md` 병합 (사용자 확인 후)

## 영향 범위

- Claude Code 동작에 영향 없음 (CLAUDE.md, rules/, skills/ 변경 없음)
- AGENTS.md는 Claude Code 미사용자 대상이라 Claude 동작과 무관
- 폴더 이동은 git history에 rename으로 기록됨
