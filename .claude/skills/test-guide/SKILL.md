---
name: test-guide
description: >
  pytest/Vitest 파일 구조, 커버리지 목표(75%+), fixture 패턴,
  RAGAS 평가 테스트를 안내합니다.
  테스트 작성, 테스트 구조 설계, 커버리지 개선 시 사용합니다.
user-invocable: false
---

# Test Guide (Bizi Project)

## 테스트 디렉토리 구조

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

## 커버리지 목표

| 대상 | 목표 |
|------|------|
| 비즈니스 로직 | ≥80% |
| API 엔드포인트 | ≥70% |
| 전체 | ≥75% |
| 훅/유틸리티 (TS) | ≥80% |
| 컴포넌트 (TS) | ≥60% |

## Python 테스트 명명 규칙

```python
def test_<function_name>_<scenario>_<expected_result>():
    pass

# 예시
def test_create_user_with_valid_data_returns_user(): pass
def test_create_user_with_duplicate_email_raises_error(): pass
```

## Mock 패턴 (외부 의존성)

```python
from unittest.mock import patch

@patch("apps.auth.service.send_email")
def test_register_sends_welcome_email(mock_send_email):
    mock_send_email.return_value = True
    result = register_user(email="new@example.com")
    mock_send_email.assert_called_once()
    assert result.email == "new@example.com"
```

## TypeScript (Vitest + React Testing Library)

```typescript
describe('Button', () => {
  it('should call onClick when clicked', () => {
    const handleClick = vi.fn();
    render(<Button label="Click me" onClick={handleClick} />);
    fireEvent.click(screen.getByRole('button'));
    expect(handleClick).toHaveBeenCalledTimes(1);
  });
});
```

- 테스트 파일 위치: 컴포넌트와 동일 디렉토리 (`Button.test.tsx`)
- 셀렉터 우선순위: `getByRole` > `getByTestId` > `getByText`

## RAG 평가 (RAGAS)

```python
# rag/tests/evaluation/test_rag_quality.py
def test_rag_answer_quality():
    results = evaluate_rag(test_cases)
    assert results["faithfulness"] >= 0.8
    assert results["answer_relevancy"] >= 0.7
```

| 메트릭 | 목표 | 설명 |
|--------|------|------|
| Faithfulness | ≥0.8 | 답변이 컨텍스트에 충실 |
| Answer Relevancy | ≥0.7 | 답변이 질문에 관련 |
| Context Precision | ≥0.7 | 검색 컨텍스트 정확도 |
| Context Recall | ≥0.7 | 필요 컨텍스트 검색 여부 |

## TDD 워크플로우

1. **RED** — 실패하는 테스트 먼저 작성 → `[test] add failing test for ...`
2. **GREEN** — 통과하는 최소 코드 작성 → `[feat] implement ...`
3. **REFACTOR** — 품질 개선 (테스트 계속 통과) → `[refactor] extract ...`

## 실행 명령어

```bash
# Python
pytest --cov=apps --cov-report=html
pytest --cov=apps --cov-fail-under=75
pytest -m "not slow"

# TypeScript
npm run test
npm run test:coverage
```

> pytest fixture/코드 생성 템플릿은 `pytest-suite` skill 참조
