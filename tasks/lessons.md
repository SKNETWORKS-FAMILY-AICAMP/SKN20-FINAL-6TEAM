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
