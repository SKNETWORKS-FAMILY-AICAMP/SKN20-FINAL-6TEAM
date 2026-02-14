# Testing Rules

## Python (pytest)

### 테스트 위치
```
backend/tests/
├── conftest.py       # 공통 fixture
├── unit/             # 단위 테스트
├── integration/      # 통합 테스트
└── e2e/              # E2E 테스트

rag/tests/
├── conftest.py
├── unit/
├── integration/
└── evaluation/       # RAGAS 평가 테스트
```

### 커버리지 목표
- **비즈니스 로직**: ≥80%
- **API 엔드포인트**: ≥70%
- **전체**: ≥75%

### 테스트 명명 규칙
```python
def test_<function_name>_<scenario>_<expected_result>():
    """함수명_시나리오_예상결과 형식"""
    pass

# Examples
def test_create_user_with_valid_data_returns_user():
    pass

def test_create_user_with_duplicate_email_raises_error():
    pass
```

### Fixture 사용
```python
# conftest.py
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

@pytest.fixture
def db_session():
    """테스트용 DB 세션"""
    engine = create_engine("sqlite:///:memory:")
    Session = sessionmaker(bind=engine)
    session = Session()
    yield session
    session.close()

@pytest.fixture
def sample_user(db_session):
    """샘플 사용자 생성"""
    user = User(email="test@example.com", name="Test User")
    db_session.add(user)
    db_session.commit()
    return user
```

### Mock 사용 (외부 의존성)
```python
from unittest.mock import Mock, patch

@patch("apps.auth.service.send_email")
def test_register_sends_welcome_email(mock_send_email):
    # Arrange
    mock_send_email.return_value = True

    # Act
    result = register_user(email="new@example.com")

    # Assert
    mock_send_email.assert_called_once()
    assert result.email == "new@example.com"
```

### pytest 실행 명령어
```bash
# 전체 테스트
pytest

# 커버리지 포함
pytest --cov=apps --cov-report=html

# 특정 마커
pytest -m "not slow"

# 병렬 실행
pytest -n auto
```

---

## TypeScript (Vitest)

### 테스트 위치
```
frontend/src/
├── components/
│   └── Button/
│       ├── Button.tsx
│       └── Button.test.tsx    # 컴포넌트와 같은 위치
├── hooks/
│   └── useAuth.test.ts
└── __tests__/                  # 통합 테스트
```

### 커버리지 목표
- **훅/유틸리티**: ≥80%
- **컴포넌트**: ≥60% (통합 테스트 보완)

### 테스트 명명 규칙
```typescript
describe('Button', () => {
  it('should render label correctly', () => {});
  it('should call onClick when clicked', () => {});
  it('should be disabled when disabled prop is true', () => {});
});
```

### React Testing Library 사용
```typescript
import { render, screen, fireEvent } from '@testing-library/react';
import { Button } from './Button';

describe('Button', () => {
  it('should call onClick handler when clicked', () => {
    const handleClick = vi.fn();
    render(<Button label="Click me" onClick={handleClick} />);

    fireEvent.click(screen.getByRole('button'));

    expect(handleClick).toHaveBeenCalledTimes(1);
  });
});
```

### data-testid 속성 사용
```tsx
// 컴포넌트
<button data-testid="submit-button">Submit</button>

// 테스트
const button = screen.getByTestId('submit-button');
```

### Vitest 실행 명령어
```bash
# 전체 테스트
npm run test

# 감시 모드
npm run test:watch

# 커버리지
npm run test:coverage

# UI 모드
npm run test:ui
```

---

## RAG 테스트 (RAGAS)

### 평가 메트릭
- **Faithfulness**: 답변이 컨텍스트에 충실한가
- **Answer Relevancy**: 답변이 질문에 관련있는가
- **Context Precision**: 검색된 컨텍스트가 정확한가
- **Context Recall**: 필요한 컨텍스트가 모두 검색되었나

### 평가 테스트
```python
# rag/tests/evaluation/test_rag_quality.py
from ragas import evaluate
from ragas.metrics import faithfulness, answer_relevancy

def test_rag_answer_quality():
    # Given
    test_cases = [
        {
            "question": "사업자등록 절차는?",
            "ground_truth": "홈택스 또는 세무서 방문..."
        }
    ]

    # When
    results = evaluate_rag(test_cases)

    # Then
    assert results["faithfulness"] >= 0.8
    assert results["answer_relevancy"] >= 0.7
```

---

## TDD 워크플로우

### Red-Green-Refactor
1. **RED**: 실패하는 테스트 먼저 작성
2. **GREEN**: 테스트 통과하는 최소 코드 작성
3. **REFACTOR**: 코드 품질 개선 (테스트는 계속 통과)

### 커밋 타이밍
```bash
# RED 단계 후
git commit -m "[test] add failing test for user registration"

# GREEN 단계 후
git commit -m "[feat] implement user registration"

# REFACTOR 단계 후
git commit -m "[refactor] extract validation logic"
```

---

## CI/CD 통합

### 필수 검증 항목
- [ ] 모든 테스트 통과
- [ ] 커버리지 임계값 충족
- [ ] 린트 에러 없음
- [ ] 타입 체크 통과

```yaml
# .github/workflows/test.yml
- name: Run Tests
  run: |
    pytest --cov=apps --cov-fail-under=75
    npm run test -- --coverage
```
