"""Football Betting Intelligence - Main FastAPI Application."""
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from config.settings import settings
from backend.database.connection import init_db, close_db
from backend.api.routes import router as api_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager."""
    # Startup
    await init_db()
    yield
    # Shutdown
    await close_db()


app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    description="Professional football betting intelligence platform with statistical modeling, value betting detection, and risk management.",
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include API routes
app.include_router(api_router)

# Serve frontend static files (in production)
# app.mount("/", StaticFiles(directory="frontend/build", html=True), name="frontend")


@app.get("/")
async def root():
    """Root endpoint."""
    return {
        "name": settings.APP_NAME,
        "version": settings.APP_VERSION,
        "description": "Football Betting Intelligence Platform",
        "docs": "/docs",
        "api": settings.API_V1_PREFIX,
    }


@app.get("/api")
async def api_info():
    """API information."""
    return {
        "version": "v1",
        "prefix": settings.API_V1_PREFIX,
        "endpoints": {
            "health": "/health",
            "providers": "/providers",
            "competitions": "/competitions",
            "fixtures": "/fixtures",
            "sync": "/sync/*",
            "predictions": "/predictions/{fixture_id}",
            "value_bets": "/value-bets",
            "live": "/live/{fixture_id}",
            "backtest": "/backtest",
        },
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "backend.main:app",
        host=settings.HOST,
        port=settings.PORT,
        reload=settings.DEBUG,
    )