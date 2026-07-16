"""Application configuration using Pydantic Settings v2"""

from typing import List

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings with environment variable support"""

    model_config = SettingsConfigDict( env_file_encoding="utf-8", case_sensitive=False, extra="ignore"
    )

    # Project Information
    project_name: str = "FastAPI Entra Template"
    version: str = "1.0.0"

    # API Configuration
    api_v1_str: str = "/api/v1"

    # Database Configuration - Local Docker PostgreSQL
    database_url: str = Field(
        alias="DATABASE_URL",
        description="Local Docker PostgreSQL connection string",
    )

    # Pool Configuration
    database_pool_size: int = Field(default=20)
    database_max_overflow: int = Field(default=10)
    database_pool_timeout: int = Field(default=30)
    database_pool_recycle: int = Field(default=300)
    database_pool_pre_ping: bool = Field(default=True)
    database_echo: bool = Field(default=False)
    database_pool_reset_on_return: str = Field(default="rollback")

    # Cache Configuration
    cache_ttl_default: int = Field(default=300)
    cache_ttl_users: int = Field(default=600)

    # CORS
    cors_origins: str = Field(default="http://localhost:4200,http://localhost:4300")

    @property
    def cors_origins_list(self) -> List[str]:
        """Get CORS origins as a list"""
        if not self.cors_origins or self.cors_origins.strip() == "":
            return [
                "http://localhost:4200",
                "http://localhost:4300",
                "http://127.0.0.1:4200",
            ]
        return [
            origin.strip() for origin in self.cors_origins.split(",") if origin.strip()
        ]

    # Microsoft Entra ID Configuration
    entra_tenant_id: str = Field(
        default="", alias="ENTRA_TENANT_ID", description="Entra tenant GUID"
    )
    entra_api_client_id: str = Field(
        default="",
        alias="ENTRA_API_CLIENT_ID",
        description="API app registration client ID",
    )
    entra_api_audience: str = Field(
        default="",
        alias="ENTRA_API_AUDIENCE",
        description="Expected audience (GUID or api://<client-id>)",
    )
    entra_api_scope: str = Field(
        default="",
        alias="ENTRA_API_SCOPE",
        description="Required scope (e.g. api://<client-id>/access_as_user)",
    )
    entra_spa_client_id: str = Field(
        default="",
        alias="ENTRA_SPA_CLIENT_ID",
        description="SPA app registration client ID",
    )

    @property
    def entra_jwks_url(self) -> str:
        """JWKS endpoint for verifying Entra v2 JWTs"""
        return f"https://login.microsoftonline.com/{self.entra_tenant_id}/discovery/v2.0/keys"

    @property
    def entra_issuer(self) -> str:
        """Expected issuer for Entra v2 tokens"""
        return f"https://login.microsoftonline.com/{self.entra_tenant_id}/v2.0"

    # Rate Limiting
    rate_limit_requests: int = Field(default=100)
    rate_limit_window: int = Field(default=60)

    # Logging
    log_level: str = Field(default="INFO")
    log_format: str = Field(default="json")

    # Monitoring
    enable_metrics: bool = Field(default=True)
    metrics_path: str = Field(default="/metrics")

    # Performance
    connection_timeout: int = Field(default=10)
    read_timeout: int = Field(default=30)

    # Environment detection helpers
    debug: bool = Field(default=True)
    environment: str = Field(default="development")

    @property
    def is_production(self) -> bool:
        return self.environment == "production"

    @property
    def is_development(self) -> bool:
        return self.environment == "development" or self.debug

    @property
    def is_staging(self) -> bool:
        return self.environment == "staging"

    @property
    def is_production_like(self) -> bool:
        return self.environment in ("production", "staging")


# Create global settings instance
settings = Settings()
