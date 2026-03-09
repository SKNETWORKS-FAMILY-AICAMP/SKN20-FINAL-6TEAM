# Write-Through 품질 개선 계획

> 기준: Reusability, Idempotency, Cohesion, Coupling, Testability, Readability, Maintainability, Extensibility, Atomicity, Robustness, Efficiency, Observability, Security, Consistency

## 변경 파일 요약

| 파일 | 변경 | 우선도 |
|------|------|--------|
| `rag/routes/_write_through.py` | 경쟁조건 수정 + 입력 검증 + 로그 레벨 | P0, P2, P3 |
| `rag/routes/chat.py` | `_get_agent_code()` 추출 + 캐시 경로 명시적 None | P1, P2 |
| `rag/tests/test_write_through.py` | 테스트 스위트 신규 생성 | P0 |
| `backend/apps/histories/service.py` | 멱등키에 session 조건 추가 | P1 |
| `rag/utils/config/settings.py` | 중복 필드 정의 삭제 | P2 |

**변경 없는 파일**: `_session_memory.py`, `session_migrator.py`, `main.py`, `chatStore.ts`, `batch_schemas.py`

---

## P0 — 즉시

### Step 1. `_get_http_client()` 경쟁조건 수정

**파일**: `rag/routes/_write_through.py:16-23`
**기준**: Robustness

현재 전역 `_http_client`를 lock 없이 check-then-set → 동시 `create_task` 시 클라이언트 leak.

```python
# Before
_http_client: httpx.AsyncClient | None = None

def _get_http_client() -> httpx.AsyncClient:
    global _http_client
    if _http_client is None or _http_client.is_closed:
        _http_client = httpx.AsyncClient(timeout=10.0)
    return _http_client
```

```python
# After — lifespan 초기화 방식
_http_client: httpx.AsyncClient | None = None

def init_http_client() -> None:
    """lifespan startup에서 1회 호출."""
    global _http_client
    _http_client = httpx.AsyncClient(timeout=10.0)

def _get_http_client() -> httpx.AsyncClient:
    if _http_client is None or _http_client.is_closed:
        raise RuntimeError("write-through http client not initialized")
    return _http_client
```

`rag/main.py` lifespan에서 `init_http_client()` 호출 추가 (Redis 초기화 옆).
이벤트 루프 시작 전 단일 스레드에서 초기화 → 경쟁조건 원천 제거.

### Step 2. `test_write_through.py` 테스트 스위트 생성

**파일**: `rag/tests/test_write_through.py` (신규)
**기준**: Testability

```
테스트 케이스:
1. save_turn_to_db — 성공 (status 201, saved_count=1)
2. save_turn_to_db — Backend 거부 (status 400/500 → warning 로그)
3. save_turn_to_db — 네트워크 타임아웃 (httpx.TimeoutException → warning 로그)
4. save_turn_to_db — 멱등 skip (status 201, skipped_count=1)
5. schedule_write_through — 익명 skip (user_id=None → 즉시 return)
6. schedule_write_through — session_id=None → 즉시 return
7. schedule_write_through — 정상 호출 (create_task 확인)
```

httpx mock: `pytest-httpx` 또는 `respx` 사용. `_http_client`를 fixture에서 `init_http_client()` → 테스트 후 `close_http_client()`.

---

## P1 — 안정성

### Step 3. `_get_agent_code()` 헬퍼 추출

**파일**: `rag/routes/chat.py`
**기준**: Reusability, Maintainability

현재 동일 로직이 8회 복붙 (4곳 × `append_session_turn` + `schedule_write_through`):

```python
DOMAIN_TO_AGENT_CODE.get(domains[0], "A0000001") if domains else "A0000001"
```

`chat.py` 상단에 헬퍼 추가:

```python
def _get_agent_code(domains: list[str] | None) -> str:
    return DOMAIN_TO_AGENT_CODE.get(domains[0], "A0000001") if domains else "A0000001"
```

8곳 모두 `agent_code=_get_agent_code(domains)` 로 교체.

### Step 4. 멱등키에 session 조건 추가

**파일**: `backend/apps/histories/service.py:275-287`
**기준**: Idempotency

현재: `user_id + question + answer[:200]` → 다른 세션의 동일 Q&A가 skip됨.

```python
# Before
dup_stmt = (
    select(History)
    .where(
        History.user_id == data.user_id,
        History.question == turn.question,
        History.answer.startswith(answer_prefix),
        History.use_yn == True,
    )
    .limit(1)
)
```

```python
# After — parent_history_id(=root_id)로 세션 범위 제한
dup_stmt = (
    select(History)
    .where(
        History.user_id == data.user_id,
        History.question == turn.question,
        History.answer.startswith(answer_prefix),
        History.use_yn == True,
    )
    .limit(1)
)
# root_id가 확보된 이후에는 같은 스레드 내로 범위 축소
if root_id is not None:
    dup_stmt = dup_stmt.where(
        History.parent_history_id == root_id,
    )
```

첫 번째 턴(root_id=None)은 기존 방식 유지 (전체 범위 중복체크), 이후 턴은 같은 스레드 내에서만 체크.

---

## P2 — 일관성

### Step 5. 캐시 경로 `evaluation_data=None` 명시

**파일**: `rag/routes/chat.py` — 2곳 (line 124, 339)
**기준**: Consistency

```python
# 캐시 히트 (비스트리밍) line ~124
schedule_write_through(
    ...
    agent_code=_get_agent_code(cached_domains),
    evaluation_data=None,  # 추가: 캐시 히트는 평가 데이터 없음을 명시
)

# 캐시 히트 (스트리밍) line ~339
schedule_write_through(
    ...
    agent_code=_get_agent_code(cached_domains),
    evaluation_data=None,  # 추가
)
```

### Step 6. `settings.py` 중복 필드 삭제

**파일**: `rag/utils/config/settings.py:215-218`
**기준**: Maintainability

```python
# 삭제 대상 (line 215-218) — 두 번째 정의(line 539)가 덮어씀
backend_internal_url: str = Field(
    default="http://backend:8000",
    description="Backend 서비스 내부 URL (Docker 내부 통신용)"
)
```

line 539의 정의만 유지.

### Step 7. `schedule_write_through` 입력 검증 추가

**파일**: `rag/routes/_write_through.py:89-103`
**기준**: Robustness

```python
# Before
def schedule_write_through(...) -> None:
    if not user_id or not session_id:
        return

# After
def schedule_write_through(...) -> None:
    if not user_id or not session_id:
        return
    if not question or not answer:
        return
```

빈 문자열이 Backend `min_length=1` 검증에 걸려 silent reject되는 것을 방지.

---

## P3 — 향후

### Step 8. 미사용 `timestamp` 파라미터 제거

**파일**: `rag/routes/_write_through.py`
**기준**: Readability

`schedule_write_through`와 `save_turn_to_db`에서 `timestamp` 파라미터 삭제.
현재 4곳 호출부 모두 미전달. `batch_schemas.py`의 `timestamp` 필드는 유지 (마이그레이션 잡에서 사용 가능).

### Step 9. 성공 로그 레벨 조정

**파일**: `rag/routes/_write_through.py:76`
**기준**: Observability

```python
# Before
logger.debug("write-through OK: user=%d, session=%s, saved=%d, skipped=%d", ...)

# After
logger.info("write-through OK: user=%d, session=%s, saved=%d, skipped=%d", ...)
```

프로덕션 기본 레벨(INFO)에서 write-through 성공/실패 추적 가능.

---

## 검증 방법

1. **경쟁조건 해소**: `init_http_client()` 미호출 시 `RuntimeError` 발생 확인
2. **테스트 통과**: `.venv/bin/pytest rag/tests/test_write_through.py -v`
3. **헬퍼 추출**: `chat.py`에서 `DOMAIN_TO_AGENT_CODE.get` 직접 호출 0회 확인 (grep)
4. **멱등성**: 같은 사용자, 다른 세션, 동일 Q&A → 둘 다 저장 확인
5. **기존 테스트 회귀 없음**: `.venv/bin/pytest rag/tests/ -v` 전체 통과
