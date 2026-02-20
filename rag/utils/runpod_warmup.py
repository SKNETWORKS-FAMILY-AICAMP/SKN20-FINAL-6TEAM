"""RunPod Serverless 콜드 스타트 방지를 위한 Warmup 모듈.

RAG 서비스 시작 시 및 주기적으로 RunPod 엔드포인트에 경량 요청을 보내
워커를 warm 상태로 유지합니다.
"""

import asyncio
import logging
import time

logger = logging.getLogger(__name__)


async def warmup_runpod() -> bool:
    """RunPod 엔드포인트에 경량 embed 요청을 보내 워커를 warm 상태로 유지합니다.

    Returns:
        성공 시 True, 실패 시 False (서비스 중단 없이 예외 처리)
    """
    from utils.config import get_settings

    settings = get_settings()
    if not settings.runpod_api_key or not settings.runpod_endpoint_id:
        logger.debug("[RunPod Warmup] API 키 또는 Endpoint ID 미설정, 스킵")
        return False

    api_url = f"https://api.runpod.ai/v2/{settings.runpod_endpoint_id}/runsync"
    payload = {"input": {"task": "embed", "texts": ["warmup"]}}
    headers = {
        "Authorization": f"Bearer {settings.runpod_api_key}",
        "Content-Type": "application/json",
    }

    start_time = time.monotonic()
    try:
        import httpx

        async with httpx.AsyncClient(timeout=120.0) as client:
            response = await client.post(api_url, json=payload, headers=headers)

        elapsed = time.monotonic() - start_time
        response.raise_for_status()

        if elapsed > 10.0:
            logger.warning(
                "[RunPod Warmup] 콜드 스타트 감지 — 응답 시간 %.1f초 (워커 초기화 중이었을 가능성)",
                elapsed,
            )
        else:
            logger.info("[RunPod Warmup] 성공 (%.1f초)", elapsed)

        return True

    except Exception as e:
        elapsed = time.monotonic() - start_time
        logger.warning("[RunPod Warmup] 실패 (%.1f초): %s", elapsed, e)
        return False


async def run_periodic_warmup(interval_seconds: int = 180) -> None:
    """주기적으로 RunPod warmup을 실행하는 백그라운드 태스크.

    Args:
        interval_seconds: warmup 실행 간격 (초). 기본값 180초 (3분).
                          RunPod 기본 idle timeout(5분)보다 짧게 설정.
    """
    logger.info("[RunPod Warmup] 주기적 warmup 시작 (간격: %d초)", interval_seconds)
    try:
        while True:
            await asyncio.sleep(interval_seconds)
            await warmup_runpod()
    except asyncio.CancelledError:
        logger.info("[RunPod Warmup] 주기적 warmup 종료")
        raise
