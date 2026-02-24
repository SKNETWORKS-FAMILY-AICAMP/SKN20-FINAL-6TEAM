"""민감 정보 마스킹 유틸리티 모듈 (Backend용).

로그에서 개인정보를 자동으로 마스킹하는 기능을 제공합니다.
"""

import logging
import re
from typing import Any


# 민감 정보 패턴 및 마스킹 치환
SENSITIVE_PATTERNS: dict[str, tuple[str, str]] = {
    # 이메일 주소
    "email": (
        r"[\w.+-]+@[\w.-]+\.[a-zA-Z]{2,}",
        "***@***.***",
    ),
    # 휴대폰 번호 (한국)
    "phone": (
        r"01[0-9]-?[0-9]{3,4}-?[0-9]{4}",
        "010-****-****",
    ),
    # 주민등록번호
    "resident_id": (
        r"\d{6}-?[1-4]\d{6}",
        "******-*******",
    ),
    # 사업자등록번호
    "business_no": (
        r"\d{3}-?\d{2}-?\d{5}",
        "***-**-*****",
    ),
    # 신용카드 번호 (16자리)
    "credit_card": (
        r"\d{4}-?\d{4}-?\d{4}-?\d{4}",
        "****-****-****-****",
    ),
    # 계좌번호 (하이픈 포함 형식만: 3자리-6자리-숫자 또는 2자리-숫자-숫자)
    # 오탐 방지: 앞뒤에 숫자/하이픈이 없는 경우만 매칭
    "bank_account": (
        r"(?<![0-9\-])\d{3,4}-\d{4,8}-\d{2,4}(?![0-9\-])",
        "***-******-***",
    ),
}

# 매 호출마다 재컴파일 방지를 위한 사전 컴파일 패턴 리스트
_COMPILED_PATTERNS: list[tuple[re.Pattern, str]] = [
    (re.compile(pattern), replacement)
    for pattern, replacement in SENSITIVE_PATTERNS.values()
]


def mask_sensitive_data(text: str) -> str:
    """텍스트에서 민감 정보를 마스킹합니다.

    Args:
        text: 마스킹할 텍스트

    Returns:
        민감 정보가 마스킹된 텍스트
    """
    if not isinstance(text, str):
        return text

    result = text
    for compiled_pattern, replacement in _COMPILED_PATTERNS:
        result = compiled_pattern.sub(replacement, result)

    return result


def mask_dict_values(data: dict[str, Any]) -> dict[str, Any]:
    """딕셔너리의 모든 문자열 값에서 민감 정보를 마스킹합니다."""
    result = {}
    for key, value in data.items():
        if isinstance(value, str):
            result[key] = mask_sensitive_data(value)
        elif isinstance(value, dict):
            result[key] = mask_dict_values(value)
        elif isinstance(value, list):
            result[key] = [
                mask_sensitive_data(v) if isinstance(v, str) else v
                for v in value
            ]
        else:
            result[key] = value
    return result


class SensitiveDataFilter(logging.Filter):
    """로그에서 민감 정보를 마스킹하는 필터.

    루트 로거에 추가하여 모든 로그 메시지에서 민감 정보를 자동으로 마스킹합니다.
    """

    def filter(self, record: logging.LogRecord) -> bool:
        if isinstance(record.msg, str):
            record.msg = mask_sensitive_data(record.msg)

        if record.args:
            if isinstance(record.args, dict):
                record.args = mask_dict_values(record.args)
            elif isinstance(record.args, tuple):
                record.args = tuple(
                    mask_sensitive_data(arg) if isinstance(arg, str) else arg
                    for arg in record.args
                )

        return True
