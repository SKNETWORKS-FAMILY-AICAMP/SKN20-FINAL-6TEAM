# Agent Routing Rules

## Project Agents (6)

| Agent | Trigger Conditions | Model |
|-------|-------------------|-------|
| `code-reviewer` | After writing/modifying code, before commits, "리뷰해줘" | sonnet |
| `fastapi-architect` | "API 만들어줘", "엔드포인트 구현", backend/ 작업 | sonnet |
| `rag-specialist` | "RAG 에이전트", "벡터DB", "프롬프트", rag/ 작업 | sonnet |
| `tdd-guide` | "테스트 작성", "TDD", test 파일 작업 | sonnet |
| `react-form-architect` | "폼 만들어줘", form component 작업 | sonnet |
| `docker-tester` | "Docker 테스트", "컨테이너 확인", Docker 빌드/디버깅 | sonnet |

## Plugin Agents (Active - 6)

| Agent | Trigger Conditions | Source |
|-------|-------------------|--------|
| `everything-claude-code:build-error-resolver` | Build/type 에러 발생 시 자동 | everything-claude-code |
| `everything-claude-code:planner` | Complex feature planning, "/plan" | everything-claude-code |
| `everything-claude-code:code-reviewer` | Code review with confidence filtering | everything-claude-code |
| `everything-claude-code:python-reviewer` | Python 코드 변경 후 리뷰 | everything-claude-code |
| `everything-claude-code:security-reviewer` | Auth, user input, API endpoint 작업 시 | everything-claude-code |
| `everything-claude-code:tdd-guide` | TDD workflow enforcement | everything-claude-code |

## Plugin Agents (Do NOT Use)

| Agent | Reason |
|-------|--------|
| `everything-claude-code:go-*` | Go 미사용 프로젝트 |
| `everything-claude-code:database-reviewer` | PostgreSQL 전용, MySQL 사용 중 |
| `everything-claude-code:e2e-runner` | Playwright 직접 설정 완료, docker-tester 에이전트 사용 |
| `everything-claude-code:doc-updater` | `/update-docs` 커맨드로 대체 |
| `feature-dev:*` | 비활성화된 플러그인 |
| `hookify:*` | 비활성화된 플러그인 |

## Routing Priority

1. **Build error** → `build-error-resolver` (즉시)
2. **Security-sensitive code** → `security-reviewer` (자동)
3. **Code written/modified** → `code-reviewer` (프로액티브)
4. **Backend API work** → `fastapi-architect`
5. **RAG/LangChain work** → `rag-specialist`
6. **Test writing** → `tdd-guide`
7. **Form components** → `react-form-architect`
8. **Complex planning** → `planner`
9. **Docker testing/debugging** → `docker-tester`
