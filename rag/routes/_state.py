"""라우트 모듈이 공유하는 전역 인스턴스.

main.py의 lifespan에서 초기화되며, 각 라우트 모듈에서 import하여 사용합니다.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from agents import ActionExecutor, MainRouter
    from vectorstores.chroma import ChromaVectorStore

router_agent: MainRouter | None = None
executor: ActionExecutor | None = None
vector_store: ChromaVectorStore | None = None
