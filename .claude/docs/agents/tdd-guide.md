# TDD Guide 에이전트

## 개요

테스트 주도 개발(TDD) 워크플로우를 안내하는 에이전트입니다.

## 사용 시점

- 새 기능 개발 전 테스트 작성
- TDD 방법론 안내 필요 시
- 테스트 코드 작성 도움 필요 시

## 호출 방법

```
TDD로 이 기능을 개발하고 싶어요: [기능 설명]
```

또는:
```
이 함수에 대한 테스트를 먼저 작성해주세요
```

## Red-Green-Refactor 사이클

### 1. RED (실패하는 테스트)
- 구현할 기능의 테스트 먼저 작성
- 테스트 실행 → 실패 확인
- "구현이 없어서" 실패해야 함

### 2. GREEN (최소 구현)
- 테스트 통과하는 가장 간단한 코드
- 완벽할 필요 없음
- 추가 기능 구현 금지

### 3. REFACTOR (리팩토링)
- 테스트 통과 상태 유지
- 중복 제거
- 명명 개선
- 구조 정리

## Python 테스트 예시

```python
# tests/unit/test_user_service.py
import pytest

class TestUserService:
    @pytest.fixture
    def service(self, db_session):
        return UserService(db_session)

    # RED: 먼저 실패하는 테스트
    def test_create_user_returns_user_with_id(self, service):
        user_data = UserCreate(email="test@example.com")

        user = service.create(user_data)

        assert user.id is not None
```

## TypeScript 테스트 예시

```typescript
// Button.test.tsx
describe('Button', () => {
  // RED: 먼저 실패하는 테스트
  it('should call onClick when clicked', () => {
    const handleClick = vi.fn();
    render(<Button onClick={handleClick} />);

    fireEvent.click(screen.getByRole('button'));

    expect(handleClick).toHaveBeenCalled();
  });
});
```

## 워크플로우

### 새 기능 개발
1. 요구사항 분석
2. 테스트 케이스 목록 작성
3. 첫 번째 테스트 작성 (RED)
4. 최소 구현 (GREEN)
5. 리팩토링 (REFACTOR)
6. 다음 테스트로 반복

### 버그 수정
1. 버그 재현 테스트 작성
2. 테스트 실패 확인
3. 버그 수정
4. 테스트 통과 확인

## 커밋 타이밍

```bash
# RED 후
git commit -m "test: add failing test for user registration"

# GREEN 후
git commit -m "feat: implement user registration"

# REFACTOR 후
git commit -m "refactor: extract validation logic"
```

## 관련 스킬

- `/pytest-suite`: Python 테스트 스위트 생성
- `/test-backend`: Backend 테스트 실행
- `/test-frontend`: Frontend 테스트 실행
