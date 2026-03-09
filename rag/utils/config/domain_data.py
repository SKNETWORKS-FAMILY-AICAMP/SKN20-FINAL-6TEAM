"""도메인 상수 데이터."""

# 도메인 → 한글 라벨 매핑 (라우터, 응답 등에서 사용)
DOMAIN_LABELS: dict[str, str] = {
    "startup_funding": "창업/지원",
    "finance_tax": "재무/세무",
    "hr_labor": "인사/노무",
    "law_common": "법률",
    "document": "문서",
    "chitchat": "일상대화",
}

# code 테이블 code 값 → 내부 domain_key 매핑
AGENT_CODE_TO_DOMAIN: dict[str, str] = {
    "A0000002": "startup_funding",
    "A0000003": "finance_tax",
    "A0000004": "hr_labor",
    "A0000007": "law_common",
}

# 역방향 매핑
DOMAIN_TO_AGENT_CODE: dict[str, str] = {v: k for k, v in AGENT_CODE_TO_DOMAIN.items()}
