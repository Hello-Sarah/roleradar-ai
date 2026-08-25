from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "RoleRadar AI"
    environment: str = "development"
    database_url: str = "sqlite:///./roleradar.db"
    openai_api_key: str | None = None
    openai_base_url: str | None = None
    openai_model: str = "gpt-4.1-mini"
    ai_explanations_enabled: bool = True
    api_base_url: str = "http://localhost:8000"
    log_level: str = "INFO"
    cv_library_path: str = "./data/cv_library"
    generated_cv_path: str = "./data/generated_cvs"
    cors_origins: list[str] = Field(default_factory=lambda: ["http://localhost:8501"])

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")


@lru_cache
def get_settings() -> Settings:
    return Settings()
