"""OpenAI 토큰 사용량 및 비용 추적 모듈.

LangChain 콜백 핸들러를 사용하여 모든 LLM 호출의 토큰 사용량을 추적하고,
요청 단위로 비용을 누적 계산합니다.
"""

import logging
from contextvars import ContextVar
from dataclasses import dataclass, field
from typing import Any

from langchain_core.callbacks import BaseCallbackHandler
from langchain_core.outputs import LLMResult

logger = logging.getLogger(__name__)

# 모델별 가격 (USD per 1M tokens)
MODEL_PRICING: dict[str, dict[str, float]] = {
    "gpt-4o-mini": {"input": 0.15, "output": 0.60},
    "gpt-4o": {"input": 2.50, "output": 10.00},
    "gpt-4o-mini-2024-07-18": {"input": 0.15, "output": 0.60},
    "gpt-4o-2024-08-06": {"input": 2.50, "output": 10.00},
}

# 기본 가격 (알 수 없는 모델용)
DEFAULT_PRICING: dict[str, float] = {"input": 0.15, "output": 0.60}


def calculate_cost(
    model: str,
    input_tokens: int,
    output_tokens: int,
) -> float:
    """토큰 사용량에 대한 비용을 계산합니다.

    Args:
        model: 모델 이름
        input_tokens: 입력 토큰 수
        output_tokens: 출력 토큰 수

    Returns:
        USD 비용
    """
    pricing = DEFAULT_PRICING
    for model_key, price in MODEL_PRICING.items():
        if model_key in model:
            pricing = price
            break

    input_cost = (input_tokens / 1_000_000) * pricing["input"]
    output_cost = (output_tokens / 1_000_000) * pricing["output"]
    return input_cost + output_cost


@dataclass
class ComponentUsage:
    """컴포넌트별 토큰 사용량."""

    name: str
    call_count: int = 0
    input_tokens: int = 0
    output_tokens: int = 0
    total_tokens: int = 0
    cost: float = 0.0


@dataclass
class RequestUsage:
    """요청 단위 토큰 사용량 누적기."""

    components: dict[str, ComponentUsage] = field(default_factory=dict)

    def add(
        self,
        component_name: str,
        model: str,
        input_tokens: int,
        output_tokens: int,
        total_tokens: int,
    ) -> None:
        """컴포넌트별 토큰 사용량을 누적합니다."""
        if component_name not in self.components:
            self.components[component_name] = ComponentUsage(name=component_name)

        comp = self.components[component_name]
        comp.call_count += 1
        comp.input_tokens += input_tokens
        comp.output_tokens += output_tokens
        comp.total_tokens += total_tokens
        comp.cost += calculate_cost(model, input_tokens, output_tokens)

    def get_totals(self) -> dict[str, Any]:
        """총합을 반환합니다."""
        total_input = sum(c.input_tokens for c in self.components.values())
        total_output = sum(c.output_tokens for c in self.components.values())
        total_tokens = sum(c.total_tokens for c in self.components.values())
        total_cost = sum(c.cost for c in self.components.values())

        return {
            "input_tokens": total_input,
            "output_tokens": total_output,
            "total_tokens": total_tokens,
            "cost": total_cost,
            "components": {
                name: {
                    "call_count": comp.call_count,
                    "input_tokens": comp.input_tokens,
                    "output_tokens": comp.output_tokens,
                    "total_tokens": comp.total_tokens,
                    "cost": comp.cost,
                }
                for name, comp in self.components.items()
            },
        }


# 요청 스코프 컨텍스트 변수
_current_request_usage: ContextVar[RequestUsage | None] = ContextVar(
    "_current_request_usage", default=None
)


class TokenUsageCallbackHandler(BaseCallbackHandler):
    """LLM 호출의 토큰 사용량을 추적하는 콜백 핸들러.

    Args:
        component_name: 컴포넌트 이름 (예: "분류", "생성", "평가")
    """

    def __init__(self, component_name: str):
        self.component_name = component_name

    def on_llm_end(self, response: LLMResult, **kwargs: Any) -> None:
        """LLM 응답 완료 시 토큰 사용량을 추출하고 로깅합니다."""
        if not response.llm_output:
            return

        token_usage = response.llm_output.get("token_usage")
        if not token_usage:
            return

        input_tokens = token_usage.get("prompt_tokens", 0)
        output_tokens = token_usage.get("completion_tokens", 0)
        total_tokens = token_usage.get("total_tokens", 0)
        model = response.llm_output.get("model_name", "unknown")

        cost = calculate_cost(model, input_tokens, output_tokens)

        # 컴포넌트별 로그 출력
        logger.info(
            "[토큰/%s] 입력=%s / 출력=%s / 합계=%s / 비용=$%.6f",
            self.component_name,
            f"{input_tokens:,}",
            f"{output_tokens:,}",
            f"{total_tokens:,}",
            cost,
        )

        # 요청 스코프 누적기에 추가
        request_usage = _current_request_usage.get()
        if request_usage is not None:
            request_usage.add(
                component_name=self.component_name,
                model=model,
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                total_tokens=total_tokens,
            )


class RequestTokenTracker:
    """요청 단위 토큰 사용량 추적 컨텍스트 매니저.

    sync/async 겸용으로 사용할 수 있습니다.

    Example:
        async with RequestTokenTracker() as tracker:
            response = await router.aprocess(query)
            usage = tracker.get_usage()
    """

    def __init__(self):
        self._token = None
        self._usage = RequestUsage()

    def __enter__(self):
        self._token = _current_request_usage.set(self._usage)
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self._log_totals()
        if self._token is not None:
            _current_request_usage.reset(self._token)
        return False

    async def __aenter__(self):
        self._token = _current_request_usage.set(self._usage)
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        self._log_totals()
        if self._token is not None:
            _current_request_usage.reset(self._token)
        return False

    def _log_totals(self) -> None:
        """요청 총합을 로깅합니다."""
        totals = self._usage.get_totals()
        if totals["total_tokens"] > 0:
            logger.info(
                "[토큰/요청총합] 입력=%s / 출력=%s / 합계=%s / 비용=$%.6f",
                f"{totals['input_tokens']:,}",
                f"{totals['output_tokens']:,}",
                f"{totals['total_tokens']:,}",
                totals["cost"],
            )

    def get_usage(self) -> dict[str, Any]:
        """누적 사용량 데이터를 반환합니다."""
        return self._usage.get_totals()
