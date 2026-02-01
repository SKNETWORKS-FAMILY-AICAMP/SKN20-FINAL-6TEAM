# Bizi Claude Code - Quick Reference

## Project Agents (5)

| Agent | Trigger | Description |
|-------|---------|-------------|
| `code-reviewer` | "코드 리뷰해줘", 코드 작성 후 자동 | 코드 품질, 보안, 성능 리뷰 |
| `fastapi-architect` | "API 만들어줘", backend/ 작업 | FastAPI 라우터/서비스/스키마 |
| `rag-specialist` | "RAG 에이전트", "벡터DB", rag/ 작업 | LangChain/LangGraph/ChromaDB |
| `tdd-guide` | "테스트 작성해줘", "TDD" | Red-Green-Refactor 안내 |
| `react-form-architect` | "폼 만들어줘", form 작업 | React 폼 컴포넌트 |

## Plugin Agents (Active)

| Agent | Trigger | Source |
|-------|---------|--------|
| `build-error-resolver` | Build/type 에러 발생 시 | everything-claude-code |
| `planner` | Complex feature planning | everything-claude-code |
| `code-reviewer` | Confidence-based code review | everything-claude-code |
| `python-reviewer` | Python 코드 변경 후 | everything-claude-code |
| `security-reviewer` | Auth, user input, API 작업 시 | everything-claude-code |
| `tdd-guide` | TDD workflow enforcement | everything-claude-code |

## Plugin Agents (Do NOT Use)

`go-*`, `database-reviewer` (PostgreSQL), `e2e-runner`, `doc-updater` - 프로젝트와 무관

## Project Commands (8)

| Command | Description |
|---------|-------------|
| `/test-rag` | RAG 서비스 테스트 실행 |
| `/test-backend` | Backend pytest 실행 |
| `/test-frontend` | Frontend Vitest 실행 |
| `/lint` | 전체 코드 린트 |
| `/typecheck` | TypeScript/Python 타입 검사 |
| `/build-vectordb` | ChromaDB 벡터 인덱스 빌드 |
| `/cli-test` | RAG CLI 대화형 테스트 |
| `/update-docs` | CLAUDE.md/AGENTS.md 자동 갱신 |

## Recommended Plugin Skills

| Skill | Description |
|-------|-------------|
| `/plan` | 요구사항 분석 + 구현 계획 수립 |
| `/tdd` | TDD 워크플로우 강제 |
| `/python-review` | Python 코드 리뷰 (PEP 8, 타입 힌트) |
| `/security-review` | 보안 취약점 체크 |
| `/python-patterns` | Python 베스트 프랙티스 |
| `/frontend-patterns` | React/TypeScript 패턴 |
| `/coding-standards` | TypeScript/React 코딩 표준 |
| `/python-testing` | pytest 전략 |
| `/frontend-design` | 프론트엔드 디자인 |

## Project Skills (5)

| Skill | Description |
|-------|-------------|
| `/rag-agent` | RAG 에이전트 클래스 생성 |
| `/pytest-suite` | pytest 테스트 스위트 생성 |
| `/fastapi-endpoint` | FastAPI 엔드포인트 보일러플레이트 |
| `/react-component` | React 컴포넌트 + 테스트 |
| `/cli-test` | RAG CLI 대화형 테스트 |

## Active Hooks

### PreToolUse
- `python-type-hint-check`: Python 파일 수정 시 타입 힌트 권장
- `env-file-security-warning`: .env 파일 수정 시 보안 경고
- `git-push-review`: git push 전 리뷰 체크리스트

### PostToolUse
- `pytest-failure-analysis`: pytest 실패 시 분석 제안
- `lint-error-summary`: 린트 에러 카테고리별 요약
- `doc-staleness-reminder`: git commit 후 문서 갱신 알림
- `console-log-warning`: JS/TS 편집 후 console.log 확인

### SessionStart
- `show-branch-info`: 현재 브랜치 + 마지막 커밋 표시

## Active Plugins (3)

| Plugin | Purpose |
|--------|---------|
| `everything-claude-code` | 에이전트, 스킬, 훅, 패턴 통합 |
| `pr-review-toolkit` | PR 리뷰 전문 에이전트 |
| `ralph-loop` | 반복 작업 자동화 |

## Disabled Plugins

| Plugin | Reason |
|--------|--------|
| `hookify` | everything-claude-code 훅 체계로 대체 |
| `feature-dev` | planner + feature-planner 스킬로 대체 |
