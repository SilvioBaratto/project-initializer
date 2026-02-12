"""Application configuration using Pydantic Settings v2"""

from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field
from typing import List, Optional


class Settings(BaseSettings):
    """Application settings with environment variable support"""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore"
    )

    # Project Information
    project_name: str = "FastAPI Supabase Template"
    version: str = "1.0.0"

    # API Configuration
    api_v1_str: str = "/api/v1"

    # Database Configuration - Supabase PostgreSQL
    # Session Mode Pooler (port 5432) for persistent FastAPI backend
    # Format: postgresql://postgres.[PROJECT_REF]:[PASSWORD]@[POOLER_HOST]:5432/postgres?sslmode=require
    database_url: str = Field(
        alias="DATABASE_URL",
        description="Supabase Session Mode Pooler connection string (port 5432) with SSL"
    )

    # Direct Connection URL - for Alembic migrations only
    # Format: postgresql://postgres:[PASSWORD]@db.[PROJECT_REF].supabase.co:5432/postgres
    direct_database_url: str = Field(
        default="",
        alias="DIRECT_DATABASE_URL",
        description="Direct connection for Alembic migrations (bypass pooler)"
    )

    # Pool Configuration - Optimized for Supabase Session Mode Pooler
    # Session Pooler: persistent connections held open by backend pool
    # For 1000+ users: backend pool (20-30) << Supabase pool size (80-120)
    database_pool_size: int = Field(
        default=20,
        description="SQLAlchemy pool size (persistent connections)"
    )
    database_max_overflow: int = Field(
        default=10,
        description="Max overflow connections under burst load"
    )
    database_pool_timeout: int = Field(
        default=30,
        description="Timeout waiting for connection from pool"
    )
    database_pool_recycle: int = Field(
        default=300,
        description="Recycle connections every 5 minutes (prevent stale connections)"
    )
    database_pool_pre_ping: bool = Field(
        default=True,
        description="Verify connections are alive before use"
    )
    database_echo: bool = Field(
        default=False,
        description="Log all SQL queries (debug only)"
    )
    database_pool_reset_on_return: str = Field(
        default="rollback",
        description="Reset strategy when connection returned to pool"
    )

    # Cache Configuration
    cache_ttl_default: int = Field(default=300)
    cache_ttl_users: int = Field(default=600)
    cache_ttl_leagues: int = Field(default=1800)

    # CORS
    cors_origins: str = Field(
        default="http://localhost:4200,http://localhost:4300"
    )

    @property
    def cors_origins_list(self) -> List[str]:
        """Get CORS origins as a list"""
        if not self.cors_origins or self.cors_origins.strip() == "":
            return [
                "http://localhost:4200",
                "http://localhost:4300",
                "http://127.0.0.1:4200"
            ]
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]

    # Supabase Configuration
    supabase_url: str = Field(
        default="https://your-project.supabase.co",
        description="Supabase project URL"
    )
    supabase_publishable_key: str = Field(
        default="your-publishable-key",
        description="Supabase publishable (anon) key for client-side auth"
    )
    supabase_service_role_key: str = Field(
        default="",
        description="Supabase service role key (server-side only, bypasses RLS)"
    )

    @property
    def supabase_jwks_url(self) -> str:
        """JWKS endpoint for verifying Supabase JWTs"""
        return f"{self.supabase_url}/auth/v1/.well-known/jwks.json"

    # Security (optional for production)

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
        """Check if running in production"""
        return self.environment == "production"

    @property
    def is_development(self) -> bool:
        """Check if running in development"""
        return self.environment == "development" or self.debug

    @property
    def is_staging(self) -> bool:
        """Check if running in staging"""
        return self.environment == "staging"

    @property
    def is_production_like(self) -> bool:
        """Check if running in production or staging mode"""
        return self.environment in ("production", "staging")


# Create global settings instance
settings = Settings()
