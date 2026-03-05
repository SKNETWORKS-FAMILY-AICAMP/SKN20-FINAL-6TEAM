from utils.multiturn_context import (
    _find_latest_user_constraint,
    _recent_messages,
    _truncate,
    build_active_directives_section,
)
import re


# ================================================================
# _truncate
# ================================================================


def test_truncate_short_string():
    assert _truncate("hello", 10) == "hello"


def test_truncate_exact_length():
    assert _truncate("12345", 5) == "12345"


def test_truncate_long_string():
    result = _truncate("abcdefghij", 5)
    assert result == "abcde..."


# ================================================================
# _recent_messages
# ================================================================


def test_recent_empty():
    assert _recent_messages([], 3) == []


def test_recent_none():
    assert _recent_messages(None, 3) == []


def test_recent_within_limit():
    msgs = [{"role": "user", "content": "q1"}, {"role": "assistant", "content": "a1"}]
    assert _recent_messages(msgs, 3) == msgs


def test_recent_exceeds_limit():
    msgs = [{"role": "user", "content": f"q{i}"} for i in range(10)]
    result = _recent_messages(msgs, 2)
    assert len(result) == 4


# ================================================================
# _find_latest_user_constraint
# ================================================================


def test_find_matching_user_message():
    history = [{"role": "user", "content": "예산 5천만원 이내로 알려줘"}]
    pattern = re.compile(r"(예산|만원)")
    result = _find_latest_user_constraint(history, pattern, 350)
    assert "예산 5천만원" in result


def test_find_returns_latest_match():
    history = [
        {"role": "user", "content": "예산 1억으로 해줘"},
        {"role": "assistant", "content": "네"},
        {"role": "user", "content": "예산 5천만원으로 변경해줘"},
    ]
    pattern = re.compile(r"예산")
    result = _find_latest_user_constraint(history, pattern, 350)
    assert "5천만원" in result


def test_find_skips_assistant():
    history = [{"role": "assistant", "content": "예산은 1억입니다"}]
    pattern = re.compile(r"예산")
    assert _find_latest_user_constraint(history, pattern, 350) is None


def test_find_no_match():
    history = [{"role": "user", "content": "사업자등록 방법 알려줘"}]
    pattern = re.compile(r"예산")
    assert _find_latest_user_constraint(history, pattern, 350) is None


def test_find_truncates_long():
    history = [{"role": "user", "content": "예산 " + "가" * 400}]
    pattern = re.compile(r"예산")
    result = _find_latest_user_constraint(history, pattern, 100)
    assert result.endswith("...")


# ================================================================
# build_active_directives_section
# ================================================================


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
    history = [
        {"role": "user", "content": "서울 지역으로 한정해줘"},
        {"role": "assistant", "content": "네."},
        {"role": "user", "content": "안녕하세요"},
        {"role": "assistant", "content": "무엇을 도와드릴까요?"},
    ]
    section = build_active_directives_section(history, max_turns=1)
    assert "서울" not in section


def test_output_format_detected():
    history = [{"role": "user", "content": "표로 정리해주세요"}]
    section = build_active_directives_section(history)
    assert "Output format" in section


def test_priority_detected():
    history = [{"role": "user", "content": "반드시 최신 법령 기준으로 답변해줘"}]
    section = build_active_directives_section(history)
    assert "Priority" in section


def test_all_four_directives():
    history = [
        {"role": "user", "content": "서울 지역 지원사업을 표로 정리하되, IT는 제외하고 반드시 최신 기준으로"},
    ]
    section = build_active_directives_section(history)
    assert "Scope/constraint" in section
    assert "Output format" in section
    assert "Exclusions" in section
    assert "Priority" in section


def test_header_format():
    history = [{"role": "user", "content": "반드시 정확한 정보만"}]
    section = build_active_directives_section(history)
    assert "## Active User Directives" in section
    assert "latest overrides older constraints" in section


def test_max_chars_applied():
    history = [{"role": "user", "content": "예산 " + "가" * 500}]
    section = build_active_directives_section(history, max_chars=50)
    assert "..." in section


def test_checklist_format():
    history = [{"role": "user", "content": "체크리스트로 만들어줘"}]
    section = build_active_directives_section(history)
    assert "Output format" in section


def test_step_by_step():
    history = [{"role": "user", "content": "단계별로 설명해줘"}]
    section = build_active_directives_section(history)
    assert "Output format" in section


def test_region_busan():
    history = [{"role": "user", "content": "부산 지역 지원사업 알려줘"}]
    section = build_active_directives_section(history)
    assert "Scope/constraint" in section


def test_exclusion_patterns_variety():
    """다양한 제외 패턴."""
    for text in ["빼고 알려줘", "없이 설명해", "금지 사항 말고"]:
        history = [{"role": "user", "content": text}]
        section = build_active_directives_section(history)
        assert "Exclusions" in section, f"Failed for: {text}"


def test_old_scope_pushed_out_by_many_turns():
    """많은 턴이 추가되면 초기 scope가 범위 밖으로 밀림."""
    history = [
        {"role": "user", "content": "예산 5천만원 이내"},
        {"role": "assistant", "content": "네"},
    ]
    for i in range(7):
        history.append({"role": "user", "content": f"질문 {i}"})
        history.append({"role": "assistant", "content": f"답변 {i}"})

    section = build_active_directives_section(history, max_turns=3)
    assert "Scope" not in section

