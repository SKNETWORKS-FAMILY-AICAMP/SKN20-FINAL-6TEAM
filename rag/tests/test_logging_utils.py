"""로깅 유틸리티 테스트."""

import logging
import pytest

from utils.logging_utils import (
    mask_sensitive_data,
    mask_dict_values,
    SensitiveDataFilter,
    SENSITIVE_PATTERNS,
)


class TestMaskSensitiveData:
    """mask_sensitive_data 함수 테스트."""

    def test_mask_email(self):
        """이메일 마스킹."""
        text = "연락처: test@example.com"
        result = mask_sensitive_data(text)

        assert "test@example.com" not in result
        assert "***@***.***" in result

    def test_mask_multiple_emails(self):
        """복수 이메일 마스킹."""
        text = "발신자: sender@gmail.com, 수신자: receiver@naver.com"
        result = mask_sensitive_data(text)

        assert "sender@gmail.com" not in result
        assert "receiver@naver.com" not in result
        assert result.count("***@***.***") == 2

    def test_mask_phone_with_dash(self):
        """하이픈 포함 전화번호 마스킹."""
        text = "휴대폰: 010-1234-5678"
        result = mask_sensitive_data(text)

        assert "010-1234-5678" not in result
        assert "010-****-****" in result

    def test_mask_phone_without_dash(self):
        """하이픈 없는 전화번호 마스킹."""
        text = "연락처: 01012345678"
        result = mask_sensitive_data(text)

        assert "01012345678" not in result
        assert "010-****-****" in result

    def test_mask_resident_id_with_dash(self):
        """주민등록번호 마스킹 (하이픈 포함)."""
        text = "주민번호: 900101-1234567"
        result = mask_sensitive_data(text)

        assert "900101-1234567" not in result
        assert "******-*******" in result

    def test_mask_resident_id_without_dash(self):
        """주민등록번호 마스킹 (하이픈 없음).

        Note: 하이픈 없는 주민번호는 전화번호 패턴과 겹칠 수 있음.
        하이픈 있는 형식을 권장.
        """
        text = "주민번호: 9001012234567"
        result = mask_sensitive_data(text)

        # 하이픈 없는 경우 다른 패턴과 겹칠 수 있으므로
        # 원본이 마스킹되었는지만 확인
        assert "9001012234567" not in result

    def test_mask_business_number(self):
        """사업자등록번호 마스킹."""
        text = "사업자번호: 123-45-67890"
        result = mask_sensitive_data(text)

        assert "123-45-67890" not in result
        assert "***-**-*****" in result

    def test_mask_business_number_no_dash(self):
        """사업자등록번호 마스킹 (하이픈 없음)."""
        text = "사업자번호: 1234567890"
        result = mask_sensitive_data(text)

        assert "1234567890" not in result

    def test_mask_credit_card(self):
        """신용카드 번호 마스킹."""
        text = "카드번호: 1234-5678-9012-3456"
        result = mask_sensitive_data(text)

        assert "1234-5678-9012-3456" not in result
        assert "****-****-****-****" in result

    def test_preserve_normal_text(self):
        """일반 텍스트 보존."""
        text = "안녕하세요. 창업 상담을 원합니다."
        result = mask_sensitive_data(text)

        assert result == text

    def test_mixed_sensitive_data(self):
        """복합 민감 정보 마스킹."""
        text = "이메일: user@test.com, 전화: 010-1111-2222, 사업자: 111-22-33333"
        result = mask_sensitive_data(text)

        assert "user@test.com" not in result
        assert "010-1111-2222" not in result
        assert "111-22-33333" not in result

    def test_non_string_input(self):
        """문자열 아닌 입력."""
        result = mask_sensitive_data(12345)
        assert result == 12345

        result = mask_sensitive_data(None)
        assert result is None


class TestMaskDictValues:
    """mask_dict_values 함수 테스트."""

    def test_mask_simple_dict(self):
        """단순 딕셔너리 마스킹."""
        data = {
            "email": "test@example.com",
            "name": "홍길동",
        }
        result = mask_dict_values(data)

        assert result["email"] == "***@***.***"
        assert result["name"] == "홍길동"

    def test_mask_nested_dict(self):
        """중첩 딕셔너리 마스킹."""
        data = {
            "user": {
                "email": "user@test.com",
                "phone": "010-1234-5678",
            },
            "status": "active",
        }
        result = mask_dict_values(data)

        assert result["user"]["email"] == "***@***.***"
        assert result["user"]["phone"] == "010-****-****"
        assert result["status"] == "active"

    def test_mask_list_in_dict(self):
        """리스트 포함 딕셔너리 마스킹."""
        data = {
            "contacts": ["user1@test.com", "user2@test.com"],
            "count": 2,
        }
        result = mask_dict_values(data)

        assert result["contacts"][0] == "***@***.***"
        assert result["contacts"][1] == "***@***.***"
        assert result["count"] == 2

    def test_original_not_modified(self):
        """원본 딕셔너리 변경 안 함."""
        data = {"email": "test@example.com"}
        result = mask_dict_values(data)

        assert data["email"] == "test@example.com"
        assert result["email"] == "***@***.***"


class TestSensitiveDataFilter:
    """SensitiveDataFilter 테스트."""

    @pytest.fixture
    def logger_with_filter(self):
        """필터가 적용된 로거."""
        logger = logging.getLogger("test_sensitive")
        logger.setLevel(logging.DEBUG)
        logger.addFilter(SensitiveDataFilter())

        # 테스트용 핸들러
        handler = logging.StreamHandler()
        handler.setLevel(logging.DEBUG)
        logger.addHandler(handler)

        return logger

    def test_filter_string_message(self, logger_with_filter, caplog):
        """문자열 메시지 마스킹."""
        with caplog.at_level(logging.INFO, logger="test_sensitive"):
            logger_with_filter.info("사용자 이메일: test@example.com")

        # 로그에 마스킹된 이메일이 있어야 함
        assert "test@example.com" not in caplog.text

    def test_filter_format_args(self, logger_with_filter, caplog):
        """포맷 인자 마스킹."""
        with caplog.at_level(logging.INFO, logger="test_sensitive"):
            logger_with_filter.info("전화번호: %s", "010-1234-5678")

        assert "010-1234-5678" not in caplog.text

    def test_filter_returns_true(self):
        """필터가 항상 True 반환."""
        filter = SensitiveDataFilter()
        record = logging.LogRecord(
            name="test",
            level=logging.INFO,
            pathname="",
            lineno=0,
            msg="테스트 메시지",
            args=(),
            exc_info=None,
        )

        assert filter.filter(record) is True


class TestSensitivePatterns:
    """민감 정보 패턴 검증."""

    def test_all_patterns_defined(self):
        """필수 패턴 정의 확인."""
        expected_keys = {"email", "phone", "resident_id", "business_no", "credit_card", "bank_account"}
        assert set(SENSITIVE_PATTERNS.keys()) == expected_keys

    def test_pattern_structure(self):
        """패턴 구조 검증."""
        for key, value in SENSITIVE_PATTERNS.items():
            assert isinstance(value, tuple)
            assert len(value) == 2
            pattern, replacement = value
            assert isinstance(pattern, str)
            assert isinstance(replacement, str)
