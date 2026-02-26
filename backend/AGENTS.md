# Backend - FastAPI REST API

> General info (tech stack, setup, API docs): [README.md](./README.md)

## File Structure

- **Routers**: `apps/*/router.py` — register in `main.py` via `app.include_router()`
- **Services**: `apps/*/service.py` — business logic layer
- **Models**: `apps/common/models.py` (User, Company, History, Code, File, Announce, Schedule, TokenBlacklist)
- **Schemas**: `apps/*/schemas.py` — Pydantic with `ConfigDict(from_attributes=True)` for responses
- **Dependencies**: `apps/common/deps.py` (get_db, get_current_user — HttpOnly cookie JWT)
- **Config**: `config/settings.py` (Pydantic BaseSettings), `config/database.py` (SQLAlchemy)
- **Token Blacklist**: `apps/auth/token_blacklist.py` (blacklist_token, is_blacklisted, cleanup_expired)
- **Background Tasks**: `apps/*/background.py` — FastAPI BackgroundTasks (e.g., `apps/histories/background.py`)
- **Code patterns**: `.claude/skills/code-patterns/SKILL.md`

## Code Table (main_code)

- `U`: User type (U0000001: admin, U0000002: prospective, U0000003: business owner)
- `B`: Industry code — KSIC-based, 21 major + 232 sub categories
- `A`: Agent code (A0000001~A0000005)
- `H`: Host organization code

## Gotchas

- **Auth**: JWT HttpOnly cookie (access_token + refresh_token), NOT localStorage
- **CSRF**: `CSRFMiddleware` in main.py — POST/PUT/DELETE require `Content-Type: application/json` or `X-Requested-With` header
- **Soft delete**: Company deletion, token blacklist cleanup use `use_yn=False` (no physical delete)
- **FK constraint**: company, history, schedule user FK is `RESTRICT` (NOT CASCADE — prevents accidental cascade deletion)
- **Production**: `ENVIRONMENT=production` disables Swagger/ReDoc
- **Rate Limiting**: `slowapi` on auth/upload endpoints
- **DB schema**: `bizi_db`, port 8000

## MUST NOT

- No hardcoding: API keys, DB connections → `config/settings.py`
- No SQL injection: use SQLAlchemy ORM `select()`, not raw SQL
- No magic numbers/strings: code table values as constants
- No secret exposure: no passwords/tokens in code/logs
- No duplicate code: extract to service classes or utility functions
