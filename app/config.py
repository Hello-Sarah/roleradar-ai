from functools import lru_cache
from ipaddress import ip_network

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "RoleRadar AI"
    environment: str = "development"
    database_url: str = "sqlite:///./roleradar.db"
    openai_api_key: str | None = None
    openai_base_url: str | None = None
    openai_model: str = "gpt-4.1-mini"
    ai_explanations_enabled: bool = True
    # Public routes must opt in explicitly; a production environment inherits this safe default.
    public_demo_enabled: bool = False
    demo_max_characters: int = Field(default=20_000, ge=40, le=100_000)
    demo_requests_per_minute: int = Field(default=12, ge=1, le=1_000)
    demo_daily_model_call_budget: int = Field(default=100, ge=0, le=100_000)
    demo_provider_timeout_seconds: float = Field(default=10.0, gt=0, le=60)
    portfolio_origins: list[str] = Field(
        default_factory=lambda: ["http://localhost:5173", "http://localhost:3000"]
    )
    trusted_proxy_cidrs: list[str] = Field(default_factory=list)
    api_base_url: str = "http://localhost:8000"
    log_level: str = "INFO"
    cv_library_path: str = "./data/cv_library"
    generated_cv_path: str = "./data/generated_cvs"
    cors_origins: list[str] = Field(default_factory=lambda: ["http://localhost:8501"])

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

    @field_validator("trusted_proxy_cidrs")
    @classmethod
    def canonicalize_trusted_proxy_cidrs(cls, cidrs: list[str]) -> list[str]:
        try:
            return [str(ip_network(cidr, strict=False)) for cidr in cidrs]
        except ValueError as exc:
            raise ValueError("trusted_proxy_cidrs must contain valid CIDR networks") from exc


@lru_cache
def get_settings() -> Settings:
    return Settings()
