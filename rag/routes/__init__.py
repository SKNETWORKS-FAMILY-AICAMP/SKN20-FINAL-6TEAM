"""RAG 서비스 라우트 모듈.

모든 라우터를 등록하여 main.py에서 일괄 include할 수 있도록 합니다.
"""

from routes.chat import router as chat_router
from routes.documents import router as documents_router
from routes.evaluate import router as evaluate_router
from routes.funding import router as funding_router
from routes.health import router as health_router
from routes.monitoring import router as monitoring_router
from routes.vectordb import router as vectordb_router

all_routers = [
    health_router,
    chat_router,
    documents_router,
    evaluate_router,
    funding_router,
    vectordb_router,
    monitoring_router,
]
