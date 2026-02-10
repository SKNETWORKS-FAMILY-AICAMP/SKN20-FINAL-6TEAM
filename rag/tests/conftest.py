"""pytest 설정 및 공통 fixture."""

import os
import sys
from pathlib import Path

import pytest

# 프로젝트 루트를 sys.path에 추가
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

# 테스트용 환경 변수 설정
os.environ.setdefault("OPENAI_API_KEY", "sk-test-key-for-testing")


@pytest.fixture
def sample_query():
    """샘플 쿼리."""
    return "창업할 때 세금 신고는 어떻게 하나요?"


@pytest.fixture
def sample_documents():
    """샘플 문서 리스트."""
    from langchain_core.documents import Document

    return [
        Document(
            page_content="사업자등록 후 부가가치세 신고를 해야 합니다. 일반과세자는 1년에 2번, 간이과세자는 1년에 1번 신고합니다.",
            metadata={"title": "부가세 신고 안내", "source": "국세청"},
        ),
        Document(
            page_content="법인세는 사업연도 종료일로부터 3개월 이내에 신고해야 합니다. 개인사업자는 종합소득세를 신고합니다.",
            metadata={"title": "법인세 안내", "source": "국세청"},
        ),
        Document(
            page_content="창업 초기에는 세무사 상담을 받는 것이 좋습니다. 세금 신고 기한을 놓치면 가산세가 부과됩니다.",
            metadata={"title": "창업 세무 가이드", "source": "창업진흥원"},
        ),
    ]


@pytest.fixture
def mock_settings():
    """테스트용 설정."""
    from utils.config import Settings

    return Settings(
        openai_api_key="sk-test-key",
        openai_model="gpt-4o-mini",
        openai_temperature=0.3,
        retrieval_k=3,
        retrieval_k_common=2,
        enable_response_cache=True,
        enable_rate_limit=True,
        cache_ttl=60,
    )
