# Runtime Verification Handoff (2026-02-25)

## Goal
- Verify that recent contextual-quality improvements are reflected in live Docker runtime.

## What Was Confirmed Today
- Code-side changes were applied for:
  - query rewrite metadata (`query_rewrite_applied`, `query_rewrite_reason`, `query_rewrite_time`)
  - timeout cause (`timeout_cause`)
  - contextual evaluation pipeline additions
- Static syntax checks for edited core files passed locally.

## Runtime Findings (Important)
1. Before restart:
   - `POST /api/rag/chat` returned normal response.
   - But `evaluation_data` did **not** include new metadata fields (`query_rewrite_*`, `timeout_cause`).

2. After `bizi-rag` restart:
   - `POST /api/rag/chat` returned `502 Bad Gateway`.
   - Backend internal check to `http://rag:8001/health` failed with `Connection refused`.
   - `bizi-rag` became effectively non-serving on port `8001`.

## Key Logs Observed
- Repeated logging formatter failure:
  - `ValueError: Formatting field not found in record: 'request_id'`
- Chroma warmup-related failure:
  - `too many SQL variables`
- Large volume of logging errors likely obscuring normal startup signal.

## Repro Commands Used
```powershell
Invoke-RestMethod -Uri 'http://localhost/api/rag/chat' -Method Post -ContentType 'application/json' -Body $body
docker restart bizi-rag
docker exec bizi-backend python -c "import requests; print(requests.get('http://rag:8001/health', timeout=5).status_code)"
docker logs --tail 400 bizi-rag
```

## Priority for Tomorrow
1. Restore `rag` service health first.
   - Ensure `rag:8001` is reachable from `backend` container.
2. Fix startup blockers:
   - logging formatter `request_id` dependency issue
   - Chroma warmup query path causing `too many SQL variables`
3. Re-run functional verification:
   - `POST /api/rag/chat` with history (multi-turn case)
   - confirm `evaluation_data` contains:
     - `query_rewrite_applied`
     - `query_rewrite_reason`
     - `query_rewrite_time`
     - `timeout_cause`
4. If healthy, run contextual evaluation batch + CI gate.

## Ready-to-Run Validation Case
```json
{
  "message": "그럼 필요 서류는?",
  "history": [
    {"role": "user", "content": "사업자 등록 절차 알려줘"},
    {"role": "assistant", "content": "사업자 등록은 관할 세무서 또는 홈택스에서 진행합니다."}
  ]
}
```

