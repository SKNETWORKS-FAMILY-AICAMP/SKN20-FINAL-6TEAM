from utils.multiturn_context import build_active_directives_section


def test_active_directives_empty_history():
    assert build_active_directives_section([]) == ""


def test_active_directives_picks_latest_overrides():
    history = [
        {"role": "user", "content": "예산은 500만원으로 해줘"},
        {"role": "assistant", "content": "알겠습니다."},
        {"role": "user", "content": "아니, 예산은 300만원으로 줄이고 표로 정리해줘"},
        {"role": "assistant", "content": "네."},
        {"role": "user", "content": "대출 상품은 제외해줘"},
    ]

    section = build_active_directives_section(history)
    assert "300만원" in section
    assert "표" in section
    assert "제외" in section


def test_none_history():
    """None 입력 시 빈 문자열 반환."""
    assert build_active_directives_section(None) == ""


def test_no_matching_patterns():
    """어떤 패턴도 매칭되지 않으면 빈 문자열 반환."""
    history = [
        {"role": "user", "content": "안녕하세요"},
        {"role": "assistant", "content": "무엇을 도와드릴까요?"},
    ]
    assert build_active_directives_section(history) == ""


def test_scope_constraint():
    """지역(서울) 범위 제약 감지."""
    history = [
        {"role": "user", "content": "서울에서 창업 지원금 알려줘"},
    ]
    section = build_active_directives_section(history)
    assert "서울" in section
    assert "Scope" in section


def test_exclusion_constraint():
    """제외 조건 감지."""
    history = [
        {"role": "user", "content": "대출 상품은 제외하고 알려줘"},
    ]
    section = build_active_directives_section(history)
    assert "제외" in section
    assert "Exclusions" in section


def test_max_turns_window():
    """윈도우 밖 메시지는 무시."""
    # max_turns=1 → 최근 2메시지만 사용
    history = [
        {"role": "user", "content": "서울 지역으로 한정해줘"},
        {"role": "assistant", "content": "네."},
        {"role": "user", "content": "안녕하세요"},
        {"role": "assistant", "content": "무엇을 도와드릴까요?"},
    ]
    # max_turns=1이면 최근 2메시지("안녕하세요", "무엇을 도와드릴까요?")만 참조
    section = build_active_directives_section(history, max_turns=1)
    assert "서울" not in section

