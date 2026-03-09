# Write-Through (즉시 이중 저장) + Lazy Reload (DB 세션 재개)

## Context

현재 Redis가 24시간 동안 유일한 데이터 저장소 → Redis 장애 시 대화 데이터 영구 손실 위험.
또한 24시간+ 비활성 세션 재개 시 멀티턴 컨텍스트가 끊김.

**목표**: 매 턴마다 Redis + MySQL 이중 저장 (MySQL은 비동기), DB 세션 재개 시 멀티턴 복원.

## 변경 파일 요약

| 파일 | 변경 | 유형 |
|------|------|------|
| `rag/routes/_write_through.py` | 비동기 MySQL 저장 모듈 | **신규** |
| `rag/routes/chat.py` | 4곳에 `schedule_write_through()` 호출 추가 | 수정 |
| `rag/main.py` | 종료 시 httpx 클라이언트 정리 | 수정 |
| `frontend/src/stores/chatStore.ts` | DB 세션 ID를 결정적으로 생성 | 수정 (1줄) |

**변경 없는 파일**: `_session_memory.py`, `session_migrator.py`(안전망 유지), Backend 전체

---

## Step 1. `rag/routes/_write_through.py` 신규 생성

비동기 fire-and-forget MySQL 저장 모듈.

```python
# 핵심 함수 2개:
async def save_turn_to_db(user_id, session_id, question, answer, agent_code, evaluation_data, timestamp)
    # httpx로 POST /histories/batch (단건 턴) → 실패 시 로그만

def schedule_write_through(user_id, session_id, question, answer, ...)
    # user_id 없으면 (익명) skip
    # asyncio.create_task(save_turn_to_db(...))
```

- 기존 `POST /histories/batch` + `X-Internal-Key` 인증 재사용 → Backend 변경 없음
- 배치 endpoint의 멱등성(question + answer[:200] 중복체크)이 마이그레이션 잡과의 중복 방지
- 공유 `httpx.AsyncClient` (connection pooling), timeout 10초

## Step 2. `rag/routes/chat.py` 4곳에 호출 추가

`append_session_turn()` 바로 뒤에 `schedule_write_through()` 추가:

| 위치 | 라인 | 경로 |
|------|------|------|
| 일반 응답 캐시 히트 | 113~122 뒤 | `chat()` 함수 |
| 일반 응답 정상 | 198~208 뒤 | `chat()` 함수 |
| 스트리밍 캐시 히트 | 310~322 뒤 | `generate()` 제너레이터 |
| 스트리밍 정상 | 546~559 뒤 | `generate()` 제너레이터 |

각 호출은 동일한 인자(user_id, session_id, question, answer, agent_code, evaluation_data)를 전달.

## Step 3. `rag/main.py` 종료 훅 추가

라인 194~196 부근, `close_redis_client()` 옆에:
```python
from routes._write_through import close_http_client
await close_http_client()
```

## Step 4. `frontend/src/stores/chatStore.ts` DB 세션 ID 수정

라인 376:
```typescript
// Before:  id: generateId(),
// After:   id: `db-${detail.root_history_id}`,
```

결정적 ID → 같은 DB 세션을 여러 번 열어도 동일한 session_id → RAG seed 로직(`chat.py:95-97`)이 자동으로 Redis에 히스토리 복원.

---

## 설계 근거

1. **마이그레이션 잡 유지**: 안전망 역할. Write-through 실패 시 기존 배치 마이그레이션이 보완. 멱등성으로 중복 방지.
2. **익명 사용자 skip**: `user_id` 없으면 MySQL 저장 불가 → 기존 Redis-only 동작 유지.
3. **스트리밍 중 비동기**: `schedule_write_through()`는 `asyncio.create_task()`로 fire-and-forget. 스트리밍 블로킹 없음, MySQL 실패해도 응답 영향 없음.
4. **DB 세션 재개 스레딩**: 재개된 세션은 `db-{root_history_id}` ID로 새 MySQL 스레드 생성. 원본 스레드는 별도 보존. 사용자는 UI에서 전체 대화를 이어서 볼 수 있음.

## 검증 방법

1. **Write-Through 테스트**: 로그인 상태에서 채팅 → MySQL `history` 테이블에 즉시 INSERT 확인
2. **멱등성 테스트**: 마이그레이션 잡 수동 실행 → `skipped_count > 0` 확인 (중복 없음)
3. **익명 테스트**: 비로그인 채팅 → MySQL 저장 안 됨, Redis만 저장 확인
4. **DB 세션 재개**: 25시간+ 경과된 세션 클릭 → 이전 대화 맥락 유지되어 멀티턴 정상 작동
5. **실패 복원**: Backend 다운 상태에서 채팅 → Redis 정상, 로그에 warning → Backend 복구 후 마이그레이션 잡이 catch-up
