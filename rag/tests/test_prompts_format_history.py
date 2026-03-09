"""format_history_for_prompt() 엣지 케이스 테스트."""

from utils.prompts import format_history_for_prompt


class TestFormatHistoryForPrompt:
    """format_history_for_prompt 함수 테스트."""

    def test_none_returns_empty(self):
        """None 입력 시 빈 문자열 반환."""
        assert format_history_for_prompt(None) == ""

    def test_empty_list_returns_empty(self):
        """빈 리스트 입력 시 빈 문자열 반환."""
        assert format_history_for_prompt([]) == ""

    def test_single_turn_formatting(self):
        """단일 턴 포맷팅 확인 (사용자/상담사 라벨)."""
        history = [
            {"role": "user", "content": "창업 절차가 궁금합니다"},
            {"role": "assistant", "content": "사업자등록부터 시작합니다"},
        ]
        result = format_history_for_prompt(history)
        assert "사용자" in result
        assert "상담사" in result
        assert "창업 절차" in result
        assert "사업자등록" in result

    def test_max_turns_truncation(self):
        """max_turns=1 시 최근 1턴(2메시지)만 포함."""
        history = [
            {"role": "user", "content": "첫번째 질문"},
            {"role": "assistant", "content": "첫번째 답변"},
            {"role": "user", "content": "두번째 질문"},
            {"role": "assistant", "content": "두번째 답변"},
            {"role": "user", "content": "세번째 질문"},
            {"role": "assistant", "content": "세번째 답변"},
        ]
        result = format_history_for_prompt(history, max_turns=1)
        assert "세번째 질문" in result
        assert "세번째 답변" in result
        assert "첫번째 질문" not in result

    def test_max_chars_truncation(self):
        """max_chars 초과 시 '...' 잘림."""
        long_content = "가" * 500
        history = [
            {"role": "user", "content": long_content},
        ]
        result = format_history_for_prompt(history, max_chars=50)
        assert "..." in result
        # 원본 500자가 50자로 잘려야 함
        assert long_content not in result

    def test_unknown_role_label(self):
        """user 외 role은 모두 '상담사' 라벨."""
        history = [
            {"role": "system", "content": "시스템 메시지"},
            {"role": "unknown", "content": "알 수 없는 역할"},
        ]
        result = format_history_for_prompt(history)
        # user가 아니면 모두 "상담사"
        assert "사용자" not in result
        assert "상담사" in result

    def test_missing_content_key(self):
        """content 키가 없는 메시지 처리."""
        history = [
            {"role": "user"},
            {"role": "assistant", "content": "정상 답변"},
        ]
        # content가 없어도 에러 없이 처리
        result = format_history_for_prompt(history)
        assert "정상 답변" in result
