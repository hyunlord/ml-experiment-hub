"""Configuration settings for ML Experiment Hub backend."""

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Application settings."""

    DATABASE_URL: str = "sqlite+aiosqlite:///./ml_experiments.db"
    CORS_ORIGINS: list[str] = ["http://localhost:5173"]
    LOG_LEVEL: str = "INFO"
    EXPERIMENT_DIR: str = "./experiments"
    PROJECTS_DIR: str = "./projects"
    CHECKPOINT_BASE_DIR: str = "./checkpoints"
    LOG_DIR: str = "./logs"
    DATA_DIR: str = "./data"
    CONFIG_DIR: str = ""  # temp config YAML dir; empty = system tempdir
    VENVS_DIR: str = "/data/venvs"  # per-project Python venv storage

    class Config:
        """Pydantic configuration."""

        env_file = ".env"
        env_file_encoding = "utf-8"
        extra = "ignore"  # Allow extra env vars (e.g. CHECKPOINT_DIR from .env)


settings = Settings()
