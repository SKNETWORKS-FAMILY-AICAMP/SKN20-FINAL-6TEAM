"""Stage 3 노이즈 제거 및 필수 법령 테스트 데이터.

필터링된 VectorDB에서 무관한 법률이 제거되었는지,
필수 법령이 올바르게 포함되어 있는지 검증하기 위한 테스트 케이스입니다.
"""

# Part A: 노이즈 테스트 — 도메인 쿼리 결과에 나타나면 안 되는 법률
NOISE_TEST_CASES: list[dict] = [
    {
        "query": "근로계약서 작성 시 필수 기재사항은 무엇인가요?",
        "domain": "law_common",
        "noise_keywords": ["군사기밀", "수산업", "원자력", "광업", "선박"],
        "description": "근로계약 쿼리에 군사/수산/원자력 법률이 나오면 안됨",
    },
    {
        "query": "법인세 신고 시 주의사항은?",
        "domain": "law_common",
        "noise_keywords": ["군사기밀", "수산업", "원자력", "항공법", "광업"],
        "description": "세무 쿼리에 군사/수산/원자력 법률이 나오면 안됨",
    },
    {
        "query": "창업 지원사업 신청 자격은?",
        "domain": "law_common",
        "noise_keywords": ["군사기밀", "수산업", "원자력", "광업", "선박"],
        "description": "창업 쿼리에 군사/수산/원자력 법률이 나오면 안됨",
    },
    {
        "query": "퇴직금 계산 방법은?",
        "domain": "law_common",
        "noise_keywords": ["군사기밀", "수산업", "원자력", "항공법", "광업"],
        "description": "노무 쿼리에 군사/수산/원자력 법률이 나오면 안됨",
    },
    {
        "query": "부가가치세 환급 조건을 알려주세요",
        "domain": "law_common",
        "noise_keywords": ["군사기밀", "수산업", "원자력", "선박", "광업"],
        "description": "세무 쿼리에 군사/수산/원자력 법률이 나오면 안됨",
    },
    {
        "query": "소기업 창업 절차와 인허가",
        "domain": "law_common",
        "noise_keywords": ["군사기밀", "수산업", "원자력", "광업", "선박"],
        "description": "창업 쿼리에 무관한 법률이 나오면 안됨",
    },
    {
        "query": "근로시간 규정 위반 시 벌칙",
        "domain": "law_common",
        "noise_keywords": ["군사기밀", "수산업", "원자력", "선박", "광업"],
        "description": "노무 쿼리에 무관한 법률이 나오면 안됨",
    },
    {
        "query": "중소기업 세액공제 종류",
        "domain": "law_common",
        "noise_keywords": ["군사기밀", "수산업", "원자력", "항공법", "광업"],
        "description": "세무 쿼리에 무관한 법률이 나오면 안됨",
    },
    {
        "query": "4대보험 가입 의무 대상은?",
        "domain": "law_common",
        "noise_keywords": ["군사기밀", "수산업", "원자력", "선박", "광업"],
        "description": "노무 쿼리에 무관한 법률이 나오면 안됨",
    },
    {
        "query": "정부 보조금 부정수급 시 제재는?",
        "domain": "law_common",
        "noise_keywords": ["군사기밀", "수산업", "원자력", "광업", "선박"],
        "description": "보조금 쿼리에 무관한 법률이 나오면 안됨",
    },
]

# Part B: 필수 법령 테스트 — 관련 쿼리에 반드시 포함되어야 할 법령
ESSENTIAL_LAW_TEST_CASES: list[dict] = [
    {
        "query": "근로계약서 작성 시 필수 기재사항은?",
        "domain": "law_common",
        "essential_keywords": ["근로기준법"],
        "description": "근로계약 쿼리에 근로기준법이 포함되어야 함",
    },
    {
        "query": "퇴직금 계산 기준은?",
        "domain": "law_common",
        "essential_keywords": ["근로자퇴직급여"],
        "description": "퇴직금 쿼리에 근로자퇴직급여보장법이 포함되어야 함",
    },
    {
        "query": "법인세 세율과 과세표준은?",
        "domain": "law_common",
        "essential_keywords": ["법인세법"],
        "description": "법인세 쿼리에 법인세법이 포함되어야 함",
    },
    {
        "query": "종합소득세 신고 대상과 세율은?",
        "domain": "law_common",
        "essential_keywords": ["소득세법"],
        "description": "소득세 쿼리에 소득세법이 포함되어야 함",
    },
    {
        "query": "부가가치세 신고 기한과 세율은?",
        "domain": "law_common",
        "essential_keywords": ["부가가치세법"],
        "description": "부가세 쿼리에 부가가치세법이 포함되어야 함",
    },
    {
        "query": "중소기업 기준과 지원 정책은?",
        "domain": "law_common",
        "essential_keywords": ["중소기업"],
        "description": "중소기업 쿼리에 중소기업 관련법이 포함되어야 함",
    },
    {
        "query": "최저임금 위반 시 제재는?",
        "domain": "law_common",
        "essential_keywords": ["최저임금법"],
        "description": "최저임금 쿼리에 최저임금법이 포함되어야 함",
    },
    {
        "query": "상법상 주식회사 설립 요건은?",
        "domain": "law_common",
        "essential_keywords": ["상법"],
        "description": "회사 설립 쿼리에 상법이 포함되어야 함",
    },
    {
        "query": "계약 해제와 손해배상 요건은?",
        "domain": "law_common",
        "essential_keywords": ["민법"],
        "description": "계약 쿼리에 민법이 포함되어야 함",
    },
    {
        "query": "남녀고용평등과 육아휴직 기준은?",
        "domain": "law_common",
        "essential_keywords": ["남녀고용평등"],
        "description": "고용평등 쿼리에 남녀고용평등법이 포함되어야 함",
    },
]
