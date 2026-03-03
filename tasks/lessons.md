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
