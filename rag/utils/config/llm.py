"""LLM 인스턴스 팩토리."""

from utils.config.settings import get_settings


def create_llm(
    label: str,
    temperature: float | None = None,
    request_timeout: float | None = None,
    max_tokens: int | None = None,
) -> "ChatOpenAI":
    """ChatOpenAI 인스턴스를 생성합니다.

    Args:
        label: 토큰 트래킹 레이블 (예: "생성", "평가")
        temperature: None이면 settings.openai_temperature 사용
        request_timeout: None이면 설정하지 않음
        max_tokens: None이면 설정하지 않음

    Returns:
        ChatOpenAI 인스턴스
    """
    from langchain_openai import ChatOpenAI
    from utils.token_tracker import TokenUsageCallbackHandler

    settings = get_settings()
    kwargs: dict = {
        "model": settings.openai_model,
        "api_key": settings.openai_api_key,
        "temperature": temperature if temperature is not None else settings.openai_temperature,
        "callbacks": [TokenUsageCallbackHandler(label)],
    }
    if request_timeout is not None:
        kwargs["request_timeout"] = request_timeout
    if max_tokens is not None:
        kwargs["max_tokens"] = max_tokens
    return ChatOpenAI(**kwargs)
