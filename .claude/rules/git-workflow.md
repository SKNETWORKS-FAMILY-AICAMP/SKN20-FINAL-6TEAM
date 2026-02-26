# Git Workflow
- 브랜치: `main`(프로덕션) → `develop`(통합) → `feature/<설명>`, `hotfix/<번호-설명>`
- 커밋: `[feat|fix|docs|refactor|test|chore|style|perf] 설명` (50자 이내)
- PR 대상: develop (hotfix는 main → develop 체리픽)
- main/develop force push 금지
- Claude Code 커밋 footer에 `with Claude Code` 추가
