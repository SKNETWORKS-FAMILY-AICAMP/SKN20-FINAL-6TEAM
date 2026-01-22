from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from config.settings import settings

# Import routers
from apps.auth.router import router as auth_router
from apps.users.router import router as users_router
from apps.companies.router import router as companies_router
from apps.histories.router import router as histories_router
from apps.schedules.router import router as schedules_router

app = FastAPI(
    title="BizMate API",
    description="통합 창업/경영 상담 챗봇 백엔드 API",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc"
)

# CORS 설정
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 라우터 등록
app.include_router(auth_router)
app.include_router(users_router)
app.include_router(companies_router)
app.include_router(histories_router)
app.include_router(schedules_router)


@app.get("/")
async def root():
    return {
        "message": "Welcome to BizMate API",
        "docs": "/docs",
        "redoc": "/redoc"
    }


@app.get("/health")
async def health_check():
    return {"status": "healthy"}
