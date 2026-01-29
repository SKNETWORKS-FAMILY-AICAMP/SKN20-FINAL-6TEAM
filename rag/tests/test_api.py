"""API 엔드포인트 테스트."""

import pytest
from fastapi.testclient import TestClient


class TestHealthEndpoint:
    """헬스체크 엔드포인트 테스트."""

    @pytest.fixture
    def client(self):
        """테스트 클라이언트."""
        # 환경 변수 설정 후 앱 import
        import os
        os.environ.setdefault("OPENAI_API_KEY", "sk-test-key")

        from main import app
        return TestClient(app)

    def test_health_check(self, client):
        """헬스체크 응답 확인."""
        response = client.get("/health")
        assert response.status_code == 200

        data = response.json()
        assert "status" in data
        assert "version" in data


class TestConfigEndpoint:
    """설정 조회 엔드포인트 테스트."""

    @pytest.fixture
    def client(self):
        """테스트 클라이언트."""
        import os
        os.environ.setdefault("OPENAI_API_KEY", "sk-test-key")

        from main import app
        return TestClient(app)

    def test_config_endpoint(self, client):
        """설정 조회 응답 확인."""
        response = client.get("/api/config")
        assert response.status_code == 200

        data = response.json()
        assert "openai_model" in data
        assert "retrieval_k" in data
        assert "enable_query_rewrite" in data

        # API 키는 노출되지 않아야 함
        assert "openai_api_key" not in data


class TestMetricsEndpoint:
    """메트릭 엔드포인트 테스트."""

    @pytest.fixture
    def client(self):
        """테스트 클라이언트."""
        import os
        os.environ.setdefault("OPENAI_API_KEY", "sk-test-key")

        from main import app
        return TestClient(app)

    def test_metrics_endpoint(self, client):
        """메트릭 조회 응답 확인."""
        response = client.get("/api/metrics")
        assert response.status_code == 200

        data = response.json()
        assert "request_count" in data
        assert "hit_rate" in data or "avg_duration" in data

    def test_endpoint_metrics(self, client):
        """엔드포인트별 메트릭 조회."""
        response = client.get("/api/metrics/endpoints")
        assert response.status_code == 200

        data = response.json()
        assert isinstance(data, dict)


class TestCacheEndpoint:
    """캐시 엔드포인트 테스트."""

    @pytest.fixture
    def client(self):
        """테스트 클라이언트."""
        import os
        os.environ.setdefault("OPENAI_API_KEY", "sk-test-key")

        from main import app
        return TestClient(app)

    def test_cache_stats(self, client):
        """캐시 통계 조회."""
        response = client.get("/api/cache/stats")
        assert response.status_code == 200

        data = response.json()
        # 에러가 없거나 통계 정보가 있어야 함
        assert "error" in data or "size" in data or "hits" in data

    def test_cache_clear(self, client):
        """캐시 삭제."""
        response = client.post("/api/cache/clear")
        assert response.status_code == 200

        data = response.json()
        assert "cleared" in data or "message" in data
