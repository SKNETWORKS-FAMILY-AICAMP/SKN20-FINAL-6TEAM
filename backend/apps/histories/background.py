"""상담 이력 백그라운드 태스크."""

import logging

import httpx

from config.database import SessionLocal
from config.settings import settings

logger = logging.getLogger(__name__)


async def run_ragas_background(
    history_id: int,
    question: str,
    answer: str,
    contexts: list[str],
) -> None:
    """백그라운드에서 RAGAS 평가를 수행하고 DB를 업데이트합니다.

    Args:
        history_id: 업데이트할 상담 이력 ID
        question: 사용자 질문
        answer: 생성된 답변
        contexts: 검색된 컨텍스트 목록
    """
    evaluate_url = f"{settings.RAG_SERVICE_URL}/api/evaluate"
    try:
        async with httpx.AsyncClient(timeout=120.0) as client:
            resp = await client.post(
                evaluate_url,
                json={"question": question, "answer": answer, "contexts": contexts},
            )
            resp.raise_for_status()
            ragas_data: dict = resp.json()
    except Exception as e:
        logger.warning("[RAGAS 백그라운드] RAG 서비스 호출 실패 (history_id=%d): %s", history_id, e)
        return

    if not ragas_data:
        return

    db = SessionLocal()
    try:
        from apps.histories.service import HistoryService

        service = HistoryService(db)
        service.update_evaluation_data(history_id, ragas_data)
        logger.info(
            "[RAGAS 백그라운드] history_id=%d 업데이트 완료: %s",
            history_id,
            {k: f"{v:.3f}" for k, v in ragas_data.items() if v is not None},
        )
    except Exception as e:
        logger.error("[RAGAS 백그라운드] DB 업데이트 실패 (history_id=%d): %s", history_id, e)
    finally:
        db.close()
