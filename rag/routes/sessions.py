"""Active Redis session query API for history panel."""

import logging

from fastapi import APIRouter, Query

from routes._session_memory import get_active_sessions_for_user

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api", tags=["Sessions"])


@router.get("/sessions/active")
async def get_active_sessions(
    user_id: int = Query(..., description="사용자 ID"),
):
    """Redis에서 활성 세션 목록을 조회합니다.

    Backend에서 내부 호출하여 히스토리 패널에 Redis 활성 세션을 포함합니다.
    """
    sessions = await get_active_sessions_for_user(user_id)

    result = []
    for session_data in sessions:
        turns = session_data.get("turns", [])
        if not turns:
            continue

        session_id = session_data.get("session_id", "")
        created_at = session_data.get("created_at")
        updated_at = session_data.get("updated_at")

        # Build title from first question
        first_question = turns[0].get("question", "")
        title = first_question[:30] + ("..." if len(first_question) > 30 else "")

        result.append({
            "session_id": session_id,
            "title": title or "활성 상담",
            "message_count": len(turns),
            "first_create_date": created_at,
            "last_create_date": updated_at,
            "turns": turns,
        })

    return result
