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

