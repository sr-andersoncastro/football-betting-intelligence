"""Application configuration settings."""
from typing import List, Optional
from pydantic_settings import BaseSettings
from pydantic import Field


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    # Application
    APP_NAME: str = "Football Betting Intelligence"
    APP_VERSION: str = "0.1.0"
    DEBUG: bool = True
    ENVIRONMENT: str = "development"

    # API
    API_V1_PREFIX: str = "/api/v1"
    HOST: str = "0.0.0.0"
    PORT: int = 8000

    # Database
    DATABASE_URL: str = Field(
        default="postgresql+asyncpg://postgres:postgres@localhost:5432/football_betting",
        description="PostgreSQL connection URL"
    )
    DATABASE_POOL_SIZE: int = 10
    DATABASE_MAX_OVERFLOW: int = 20

    # Redis
    REDIS_URL: str = Field(
        default="redis://localhost:6379/0",
        description="Redis connection URL"
    )

    # API-Football
    API_FOOTBALL_KEY: Optional[str] = Field(
        default=None,
        description="API-Football API key"
    )
    API_FOOTBALL_BASE_URL: str = "https://v3.football.api-sports.io"
    API_FOOTBALL_RATE_LIMIT: int = 100  # requests per day on free plan

    # football-data.org
    FOOTBALL_DATA_KEY: Optional[str] = Field(
        default=None,
        description="football-data.org API key"
    )
    FOOTBALL_DATA_BASE_URL: str = "https://api.football-data.org/v4"

    # The Odds API
    ODDS_API_KEY: Optional[str] = Field(
        default=None,
        description="The Odds API key"
    )
    ODDS_API_BASE_URL: str = "https://api.the-odds-api.com/v4"

    # Sync Configuration
    SYNC_INTERVAL_MINUTES: int = 60
    SYNC_HISTORICAL_DAYS: int = 30
    SYNC_UPCOMING_DAYS: int = 7

    # Competitions to track (IDs from API-Football)
    COMPETITIONS: List[int] = Field(
        default_factory=lambda: [
            71,   # Brasileirão Série A
            72,   # Brasileirão Série B
            39,   # Premier League
            140,  # La Liga
            78,   # Bundesliga
            135,  # Serie A (Italy)
            61,   # Ligue 1
            2,    # Champions League
            3,    # Europa League
        ]
    )

    # Model Configuration
    MIN_MATCHES_FOR_MODEL: int = 10
    DEFAULT_ELO_K_FACTOR: float = 20.0
    DEFAULT_HOME_ADVANTAGE: float = 0.3
    POISSON_MAX_GOALS: int = 10
    DIXON_COLES_RHO: float = 0.1

    # Value Betting
    MIN_EDGE_PERCENT: float = 2.0
    MIN_EV_PERCENT: float = 5.0
    MAX_KELLY_FRACTION: float = 0.25
    CONFIDENCE_THRESHOLD: float = 0.6

    # Risk Management
    MAX_EXPOSURE_PER_MATCH: float = 0.05
    MAX_DAILY_EXPOSURE: float = 0.20
    MAX_DRAWDOWN_PERCENT: float = 15.0

    # CORS
    CORS_ORIGINS: List[str] = Field(
        default_factory=lambda: [
            "http://localhost:3000",
            "http://localhost:8080",
            "http://127.0.0.1:3000",
            "http://127.0.0.1:8080",
        ]
    )

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = True


settings = Settings()