# 세션 타임아웃 1시간 + 게스트 턴 쿼터 합산

> 작성일: 2026-03-04

## Context

1. **세션 비활동 타임아웃**: 현재 Redis 세션 TTL이 25시간(90000초)으로, 사실상 비활동 만료가 없는 것과 같음. OWASP/NIST 권고에 따라 1시간 비활동 시 세션 만료로 변경.
2. **게스트 턴 합산**: 기존 유저가 로그아웃 → 게스트 10회 → 로그인 순환으로 "공짜 턴"을 얻는 악용 방지. 게스트 턴을 유저 쿼터에 합산하는 인프라 구축. **쿼터 값/타입(일일/세션당/총)은 추후 결정.**

---

## 기능 1: 세션 비활동 타임아웃 → 1시간

### 변경 파일

#### 1-1. `rag/utils/config/settings.py` (L504-521)

기본값 3개 변경 + description 업데이트:

| 설정 | 변경 전 | 변경 후 | 이유 |
|------|---------|---------|------|
| `session_memory_ttl_seconds` | 90000 (25h) | 4500 (75min) | 1시간 비활동 + 15분 마이그레이션 버퍼 |
| `session_migrate_ttl_threshold` | 3600 (1h) | 900 (15min) | TTL ≤ 15분인 세션을 마이그레이션 대상으로 |
| `session_migrate_interval` | 3600 (1h) | 300 (5min) | 15분 윈도우에서 최소 3번 체크 |

threshold < ttl 자동 조정 validator 추가 (기존 `enforce_production_security` 패턴):
```python
if self.session_migrate_ttl_threshold >= self.session_memory_ttl_seconds:
    self.session_migrate_ttl_threshold = self.session_memory_ttl_seconds // 3
```

#### 1-2. `.env.example` (L142-147)

주석의 기본값과 설명 업데이트 (90000→4500, 3600→300/900)

#### 1-3. `rag/CLAUDE.md` Session Memory 테이블

기본값 업데이트 (90000→4500)

### 배포 노트

- 설정 변경 후 기존 Redis 키는 이전 TTL(90000s) 유지
- 사용자가 다음 메시지를 보내면 새 TTL(4500s)로 갱신됨 (`_session_memory.py` L131 `EXPIRE`)
- 최악의 경우 기존 세션이 ~25시간 후 만료 → 자연 소멸, 강제 조치 불필요

### 변경하지 않는 파일

- `rag/jobs/session_migrator.py` — settings에서 동적으로 읽으므로 변경 불필요
- `rag/routes/_session_memory.py` — `_session_ttl()` 함수로 동적 참조
- 프론트엔드 비활동 경고 UI — 후속 작업으로 분리

---

## 기능 2: 게스트 턴 쿼터 합산 인프라

> **쿼터 값/타입은 추후 결정.** 현재는 `AUTHENTICATED_DAILY_LIMIT = null` (무제한)로 두고, 인프라만 구축.

### Phase 2-A: Backend 메시지 카운트 API

#### 2-A-1. `backend/apps/histories/service.py`

`get_message_count_today(user_id: int) -> int` 메서드 추가:
- `today_start = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)` 사용
  (DB의 `create_date`가 `datetime.now()` 로컬 타임 기준이므로 동일하게 맞춤 — `models.py` L85 참고)
- `select(func.count()).select_from(History).where(user_id, use_yn=True, create_date >= today_start)`
- `from sqlalchemy import func` import 추가 필요 (현재 `service.py`에 미존재)

#### 2-A-2. `backend/apps/histories/schemas.py`

`MessageQuotaResponse` 스키마 추가:
```python
class MessageQuotaResponse(BaseModel):
    today_count: int
    daily_limit: int | None = None  # None = 무제한
    remaining: int | None = None
```

> **메모**: `ConfigDict(from_attributes=True)` 불필요. 이 스키마는 ORM 모델 매핑이 아닌 수동 생성 응답이므로 `model_config` 없이 사용. (기존 `HistoryResponse` 등은 ORM 매핑이라 `from_attributes=True` 필요.)

#### 2-A-3. `backend/apps/histories/router.py`

`GET /histories/quota` 엔드포인트 추가:
- `Depends(get_current_user)` 인증 필수
- `service.get_message_count_today()` 호출
- `MessageQuotaResponse` 반환

> **주의**: `GET /histories/{history_id}` (L267) 보다 **위에** 정의해야 함. 아래에 두면 FastAPI가 "quota"를 `int`로 파싱 시도 → 422 에러.
>
> **삽입 위치**: L213(`POST /batch`) 뒤, L239(`POST /`) 앞에 삽입. 기존 GET 엔드포인트 그룹(L37-210) 마지막이 아닌 POST 사이에 배치하되, path param `GET /{history_id}` (L267) 보다 반드시 위에 위치.

### Phase 2-B: Frontend 쿼터 체크 프레임워크

#### 2-B-1. `frontend/src/lib/constants.ts`

```typescript
export const AUTHENTICATED_DAILY_LIMIT: number | null = null; // 추후 결정
export const AUTHENTICATED_LIMIT_MESSAGE = '오늘의 메시지 사용량을 모두 소진했습니다. 내일 다시 이용해주세요.';
```

#### 2-B-2. `frontend/src/stores/chatStore.ts`

상태 추가:
- `authenticatedMessageCount: number` (초기값 0)
- `incrementAuthenticatedCount()` 메서드
- `setAuthenticatedCount(count: number)` 메서드
- `resetOnLogout()`에 `authenticatedMessageCount: 0` 추가
- `partialize`에는 추가하지 않음 (서버가 진실의 원천, persist 불필요)

#### 2-B-3. `frontend/src/stores/authStore.ts` (L95-98)

login() 순서에 quota fetch 삽입:
```
1. syncGuestMessages()      (기존)
2. resetGuestCount()         (기존)
3. fetchMessageQuota() ← 신규: GET /histories/quota → setAuthenticatedCount()
4. bootstrapFromServerHistories()  (기존)
5. createSession()           (기존)
```

#### 2-B-4. `frontend/src/hooks/useChat.ts` (L58-69)

게스트 제한 체크 다음에 인증 유저 쿼터 체크 추가:
```typescript
if (isAuthenticated && AUTHENTICATED_DAILY_LIMIT !== null
    && authenticatedMessageCount >= AUTHENTICATED_DAILY_LIMIT) {
  // 제한 메시지 표시 후 return
}
```
메시지 전송 성공 후 `incrementAuthenticatedCount()` 호출 (기존 `incrementGuestCount()` 옆)

> **패턴 메모**: `GUEST_LIMIT_MESSAGE`는 현재 `useChat.ts` L12에 로컬 const로 정의되어 있음. `AUTHENTICATED_LIMIT_MESSAGE`는 `constants.ts`에 추가 예정. 구현 시 `GUEST_LIMIT_MESSAGE`도 `constants.ts`로 이동하여 패턴을 통일할 것.

### Phase 2-C: 악용 방지

#### 2-C-1. `frontend/src/stores/chatStore.ts` (L447-453)

`resetOnLogout()`에서 `guestMessageCount: 0` 제거 → 로그아웃해도 게스트 카운트 유지.
게스트 카운트는 `login()` → `resetGuestCount()`에서만 리셋됨 (로그인 후 동기화 완료 시).

---

## 구현 순서

1. **Phase 1**: `settings.py` + `.env.example` + `rag/CLAUDE.md` → RAG 테스트
2. **Phase 2-A**: Backend 서비스/스키마/라우터 → Backend 테스트
3. **Phase 2-B**: Frontend 상수/스토어/훅 → Frontend 테스트
4. **Phase 2-C**: `resetOnLogout` 변경 → 전체 테스트

## 검증 계획

- `rag/tests/` 전체 실행 (Phase 1 후)
- `backend/tests/` 전체 실행 (Phase 2-A 후)
- `frontend/` npm run test (Phase 2-B, 2-C 후)
- 수동 E2E: 게스트 메시지 2회 → 로그인 → `GET /histories/quota`에서 today_count에 2회 포함 확인
- 수동 E2E: 로그아웃 → 게스트 카운트가 리셋되지 않는 것 확인
- 타임존 검증: `get_message_count_today()` 결과가 DB의 `create_date` 기준 오늘 자정~현재 범위인지 확인

## 후속 작업 (본 플랜 범위 외)

- 프론트엔드 세션 만료 감지 UI (비활동 60분 경고 타이머 + RAG 404 시 세션 만료 메시지)
- `GUEST_LIMIT_MESSAGE`를 `constants.ts`로 이동 (Phase 2-B-4 패턴 메모 참고)
