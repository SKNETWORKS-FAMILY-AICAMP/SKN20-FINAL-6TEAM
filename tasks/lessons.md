# Lessons Learned

Record mistakes, corrections, and insights during development.

## Template

```
### [Date] - [Brief Title]
- **Mistake**: What went wrong
- **Fix**: How it was resolved
- **Lesson**: What to remember next time
```

## Entries

(Add entries below as they occur)

### 2026-03-03 - RAG Container Missing Runtime Dependency
- **Mistake**: `rag/utils/s3_client.py` imported `boto3`, but `rag/requirements.txt` did not include `boto3`, causing `ModuleNotFoundError` and repeated `bizi-rag` container restarts.
- **Fix**: Added `boto3` to `rag/requirements.txt` so the Docker image installs the AWS SDK at build time.
- **Lesson**: When a service imports an SDK at module import time, verify the dependency is declared in that service's own requirements file before rebuilding containers.

### 2026-03-03 - Login-Dependent E2E Should Use Real Auth State
- **Mistake**: I initially tried to expand Playwright coverage by depending on `/auth/test-login`, but local DB/schema differences and rate limiting made that path unreliable for final feature verification.
- **Fix**: Switched the final verification approach to real Playwright browser interaction with an actual logged-in session for protected pages, and recorded only the scenarios that were truly executed.
- **Lesson**: For final acceptance-style QA, prefer real authentication state over convenience test endpoints unless the test-login path is guaranteed to be stable in the target environment.

### 2026-03-04 - Precreate Capture Paths And Reload After Role-Switch Login
- **Mistake**: I first attempted to save Playwright screenshots into a deliverable image path that did not exist, and later switched browser auth roles with `/auth/test-login` without fully reloading the SPA, so the UI still showed the previous Zustand auth state.
- **Fix**: Created `산출물/7주차/images/user-flows` before capturing assets, then performed a full page reload after role-switch login so the frontend re-read the authenticated user and rendered the correct protected/admin screens.
- **Lesson**: When collecting deliverable screenshots, create the output directory before capture and fully reload the SPA after changing auth cookies so persisted frontend state matches the active server session.

### 2026-03-06 - Shared Product Docs Must Be Synced Across Main And Test
- **Mistake**: I treated `PRD.md` like a branch-local document and updated it on `test` without first reconciling it against the current shipped code and shared branches.
- **Fix**: Re-validated `PRD.md` against the current implementation, rebuilt the canonical document, and synced the same final content to both `main` and `test`.
- **Lesson**: If a document describes the current product rather than an experiment, update it from the latest code reality and keep `main` and shared integration branches aligned together.
