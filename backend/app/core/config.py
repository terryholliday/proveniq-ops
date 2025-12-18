"""
PROVENIQ Ops - Core Configuration
Centralized settings with Pydantic validation
"""

from functools import lru_cache
from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings with environment variable binding."""
    
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
    )
    
    # Application
    app_name: str = "PROVENIQ Ops"
    app_env: Literal["development", "staging", "production"] = "development"
    debug: bool = True
    
    # Database
    database_url: str = "postgresql+asyncpg://localhost:5432/proveniq_ops"
    
    # External System URLs (mocked in development)
    ledger_api_url: str = "http://localhost:8000/mocks/ledger"
    claimsiq_api_url: str = "http://localhost:8000/mocks/claimsiq"
    capital_api_url: str = "http://localhost:8000/mocks/capital"
    
    @property
    def is_development(self) -> bool:
        return self.app_env == "development"


@lru_cache
def get_settings() -> Settings:
    """Cached settings instance."""
    return Settings()
