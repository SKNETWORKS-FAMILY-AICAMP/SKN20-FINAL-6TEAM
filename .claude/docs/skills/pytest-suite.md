# Pytest Suite 생성 스킬

## 목적

Python 모듈에 대한 포괄적인 pytest 테스트 스위트를 생성합니다.

## 사용 시나리오

- 새 Python 모듈 개발 시 테스트 먼저 작성 (TDD)
- 기존 모듈에 테스트 추가 필요 시
- 테스트 커버리지 향상 필요 시

## 호출 방법

```
/pytest-suite
```

## 입력 파라미터

1. **대상 모듈 경로**
   - 예: `backend/apps/users/service.py`

2. **테스트 유형**
   - `unit`: 단위 테스트만
   - `integration`: 통합 테스트만
   - `both`: 둘 다 (기본값)

3. **커버리지 목표**
   - 기본: 80%

## 생성되는 파일

```
{service}/tests/
├── conftest.py            # 공통 fixture (없으면 생성)
├── unit/
│   └── test_{module}.py   # 단위 테스트
└── integration/
    └── test_{module}_integration.py  # 통합 테스트
```

## 테스트 구조

### conftest.py
```python
@pytest.fixture
def db_session():
    """테스트용 DB 세션"""
    ...

@pytest.fixture
def sample_user(db_session):
    """샘플 사용자"""
    ...
```

### 테스트 클래스
```python
class TestUserService:
    @pytest.fixture
    def service(self, db_session):
        return UserService(db_session)

    def test_create_user_with_valid_data(self, service):
        ...

    def test_create_user_with_duplicate_email_raises_error(self, service):
        ...
```

## 테스트 명명 규칙

```
test_{method}_{scenario}_{expected_result}

예시:
- test_create_user_with_valid_data_returns_user
- test_get_user_with_nonexistent_id_returns_none
```

## 완료 후 작업

```bash
# 테스트 실행
pytest {test_file} -v

# 커버리지 확인
pytest {test_file} --cov={module} --cov-report=term-missing
```

## 관련 명령어

- `/test-backend`: Backend 테스트 실행
- `/test-rag`: RAG 테스트 실행
