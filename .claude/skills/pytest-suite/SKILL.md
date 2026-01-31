---
name: pytest-suite
description: "Python 모듈의 pytest 테스트 스위트를 생성합니다. TDD 패턴을 따르는 테스트 코드를 작성합니다."
---

# Pytest Suite Generator Skill

Python 모듈에 대한 포괄적인 pytest 테스트 스위트를 생성합니다.

## 사용 시점

- 새 Python 모듈 개발 시 테스트 먼저 작성 (TDD)
- 기존 모듈에 테스트 추가 필요 시
- 테스트 커버리지 향상 필요 시

## 입력 정보

1. **대상 모듈 경로** (예: `backend/apps/users/service.py`)
2. **테스트 유형** (unit/integration/both)
3. **커버리지 목표** (기본: 80%)

## 생성 파일

```
{service_root}/tests/
├── conftest.py            # 공통 fixture (없으면 생성)
├── unit/
│   └── test_{module}.py   # 단위 테스트
└── integration/
    └── test_{module}_integration.py  # 통합 테스트 (선택)
```

## 워크플로우

### Step 1: 대상 모듈 분석

모듈을 읽고 다음을 파악:
- 클래스/함수 목록
- 공개 메서드 시그니처
- 의존성 (주입 가능한 것들)
- 예외 발생 가능 지점

### Step 2: conftest.py 확인/생성

```python
# {service}/tests/conftest.py
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session
from unittest.mock import Mock

# 테스트 DB 세션
@pytest.fixture
def db_session():
    """인메모리 SQLite 테스트 세션"""
    engine = create_engine("sqlite:///:memory:")
    Session = sessionmaker(bind=engine)
    session = Session()
    yield session
    session.close()

# Mock 객체 factory
@pytest.fixture
def mock_factory():
    """Mock 객체 생성 헬퍼"""
    def _create_mock(**attrs):
        mock = Mock()
        for key, value in attrs.items():
            setattr(mock, key, value)
        return mock
    return _create_mock
```

### Step 3: 테스트 클래스 구조 생성

```python
# {service}/tests/unit/test_{module}.py
import pytest
from unittest.mock import Mock, patch, AsyncMock
from {module_path} import {ClassName}

class Test{ClassName}:
    """
    {ClassName} 단위 테스트

    테스트 대상: {모듈 설명}
    """

    # ==================== Fixtures ====================

    @pytest.fixture
    def instance(self, db_session):
        """테스트 인스턴스 생성"""
        return {ClassName}(db_session)

    @pytest.fixture
    def sample_data(self):
        """샘플 테스트 데이터"""
        return {
            # 샘플 데이터
        }

    # ==================== 정상 케이스 ====================

    def test_{method}_with_valid_input_returns_expected(
        self, instance, sample_data
    ):
        """정상 입력 시 예상 결과 반환"""
        # Arrange
        input_data = sample_data

        # Act
        result = instance.{method}(input_data)

        # Assert
        assert result is not None
        # 구체적인 검증 추가

    # ==================== 예외 케이스 ====================

    def test_{method}_with_invalid_input_raises_error(self, instance):
        """잘못된 입력 시 에러 발생"""
        # Arrange
        invalid_input = None

        # Act & Assert
        with pytest.raises(ValueError, match="expected error message"):
            instance.{method}(invalid_input)

    # ==================== 엣지 케이스 ====================

    def test_{method}_with_empty_input_handles_gracefully(self, instance):
        """빈 입력 처리"""
        # Arrange
        empty_input = {}

        # Act
        result = instance.{method}(empty_input)

        # Assert
        assert result == []  # 또는 적절한 기본값

    # ==================== Mock 테스트 ====================

    @patch("{module_path}.external_service")
    def test_{method}_calls_external_service(
        self, mock_external, instance
    ):
        """외부 서비스 호출 검증"""
        # Arrange
        mock_external.return_value = {"data": "value"}

        # Act
        instance.{method}()

        # Assert
        mock_external.assert_called_once()
```

### Step 4: 비동기 테스트 (필요시)

```python
# 비동기 함수 테스트
class TestAsync{ClassName}:

    @pytest.mark.asyncio
    async def test_async_{method}_returns_result(self, instance):
        """비동기 메서드 테스트"""
        # Arrange
        input_data = {"key": "value"}

        # Act
        result = await instance.{method}(input_data)

        # Assert
        assert result is not None

    @pytest.mark.asyncio
    @patch("{module_path}.async_dependency", new_callable=AsyncMock)
    async def test_async_{method}_with_mock(
        self, mock_dep, instance
    ):
        """비동기 의존성 모킹"""
        # Arrange
        mock_dep.return_value = {"mocked": True}

        # Act
        result = await instance.{method}()

        # Assert
        mock_dep.assert_awaited_once()
```

### Step 5: 통합 테스트 (선택)

```python
# {service}/tests/integration/test_{module}_integration.py
import pytest
from fastapi.testclient import TestClient
from main import app

class Test{Module}Integration:
    """
    {Module} 통합 테스트

    실제 DB 및 외부 서비스와의 통합 테스트
    """

    @pytest.fixture
    def client(self):
        return TestClient(app)

    @pytest.fixture
    def auth_headers(self, client):
        """인증 헤더 생성"""
        # 테스트 사용자 로그인
        response = client.post("/auth/login", json={
            "email": "test@example.com",
            "password": "testpass"
        })
        token = response.json()["access_token"]
        return {"Authorization": f"Bearer {token}"}

    def test_api_endpoint_returns_data(
        self, client, auth_headers
    ):
        """API 엔드포인트 통합 테스트"""
        response = client.get(
            "/api/v1/{resource}",
            headers=auth_headers
        )

        assert response.status_code == 200
        assert "data" in response.json()
```

## 테스트 명명 규칙

```
test_{method}_{scenario}_{expected_result}

예시:
- test_create_user_with_valid_data_returns_user
- test_create_user_with_duplicate_email_raises_error
- test_get_user_with_nonexistent_id_returns_none
```

## 실행 명령어

```bash
# 생성된 테스트 실행
pytest {test_file_path} -v

# 커버리지 확인
pytest {test_file_path} --cov={module_path} --cov-report=term-missing

# 특정 테스트만
pytest {test_file_path}::TestClassName::test_method_name
```

## 완료 체크리스트

- [ ] conftest.py 확인/생성
- [ ] 단위 테스트 생성
- [ ] 통합 테스트 생성 (선택)
- [ ] 테스트 실행 성공
- [ ] 커버리지 목표 달성
- [ ] CI 파이프라인 통과
