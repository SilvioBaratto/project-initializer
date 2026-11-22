"""Application settings loaded from environment variables (Pydantic Settings v2).

There is no ``env_file`` here: ``app.infrastructure.config.load_configuration()``
copies the project ``.env`` into ``os.environ`` before the app starts, and in
Docker the variables arrive as real environment variables. Settings therefore
read ``os.environ`` only, and constructing them with an empty environment must
succeed so tools that import the module without a ``.env`` keep working.
"""

from importlib.metadata import version as installed_version
from typing import Annotated, Literal, Self, get_args

from pydantic import BeforeValidator, Field, model_validator
from pydantic_settings import SettingsConfigDict
from sqlalchemy.engine import make_url
from sqlalchemy.exc import ArgumentError

from app.infrastructure.auth_settings import AuthSettings

Environment = Literal["development", "test", "staging", "production"]
LogFormat = Literal["json", "text"]
SslMode = Literal["disable", "allow", "prefer", "require", "verify-ca", "verify-full"]


def _lowercase_text(value: object) -> object:
    return value.lower() if isinstance(value, str) else value


LogLevelName = Literal["debug", "info", "warning", "error", "critical"]
LOG_LEVEL_NAMES: tuple[str, ...] = get_args(LogLevelName)

# Operators habitually write LOG_LEVEL=INFO; accepting it avoids a startup
# failure over letter case while still rejecting unknown level names.
LogLevel = Annotated[LogLevelName, BeforeValidator(_lowercase_text)]

# Carries no credentials on purpose: a default that boots against a real
# database with a well-known password is worse than failing to connect.
DEFAULT_DATABASE_URL = "postgresql://localhost:5433/app_db"

WILDCARD_ORIGIN = "*"

# The ``[project] name`` of pyproject.toml, which is the key the installed
# metadata is stored under.
DISTRIBUTION_NAME = "api"

# The libpq modes that never fall back to a clear-text connection.
ENCRYPTED_SSL_MODES = frozenset({"require", "verify-ca", "verify-full"})
SSL_MODE_URL_PARAMETER = "sslmode"
# A file or in-memory database has no network hop to protect.
FILE_BACKENDS = frozenset({"sqlite"})
DATABASE_URL_VARIABLE = "DATABASE_URL"
MIGRATION_URL_VARIABLE = "DIRECT_DATABASE_URL"
_ENCRYPTING_MODE_NAMES = ", ".join(sorted(ENCRYPTED_SSL_MODES))
INSECURE_TRANSPORT_MESSAGE = (
    "{variable} is not TLS-protected: in staging and production set "
    f"DATABASE_SSL_MODE (or sslmode in the URL) to one of {_ENCRYPTING_MODE_NAMES}, "
    "or set DATABASE_ALLOW_INSECURE_TRANSPORT=true for a database on the same host "
    "or on a private network that offers no TLS"
)


def _is_transport_encrypted(
    url: str, configured_ssl_mode: str | None, variable: str
) -> bool:
    try:
        parsed = make_url(url)
    except ArgumentError:
        # SQLAlchemy's own message quotes the URL, credentials included.
        raise ValueError(f"{variable} is not a valid database URL") from None
    if parsed.get_backend_name() in FILE_BACKENDS:
        return True
    # The configured mode overrides the one in the URL, exactly as
    # build_connect_args and the async overlay apply it, so it decides here too.
    mode = configured_ssl_mode or parsed.query.get(SSL_MODE_URL_PARAMETER)
    # A repeated sslmode parameter comes back as a tuple, which is never in the set.
    return mode in ENCRYPTED_SSL_MODES


class Settings(AuthSettings):
    """Typed, validated application configuration.

    Values come from environment variables named after the fields,
    case-insensitively. ``database_url`` is read from ``DATABASE_URL`` and
    ``database_migration_url`` from ``DIRECT_DATABASE_URL``. Unknown variables
    are ignored so the shared environment can carry other tools' settings.

    Attributes:
        environment: Deployment stage; drives the ``is_*`` properties.
        debug: Enables framework debug behaviour. Refused outside development,
            because it makes the framework return tracebacks to clients.
        log_level: Minimum severity that is emitted, lower case.
        log_format: ``json`` for machine-parsed logs, ``text`` for a terminal.
        cors_origins: Comma-separated browser origins allowed to call the API.
            The wildcard ``*`` is refused in staging and production.
        api_docs_enabled: Explicit switch for the interactive API docs; when
            None the docs follow the environment (see ``docs_enabled``).
        database_url: Connection URL the application uses at runtime.
        database_migration_url: Direct, non-pooled URL for schema migrations;
            when None migrations use ``database_url``.
        database_ssl_mode: libpq-style TLS mode; None leaves it to the URL.
            When set it overrides the ``sslmode`` of the URL.
        database_allow_insecure_transport: Opt-out of the TLS requirement that
            staging and production enforce on the database connection. Meant for
            a database on the same host or on a private network that offers no
            TLS, such as the bundled docker-compose ``db`` service.
        database_pool_size: Connections kept open in the pool.
        database_max_overflow: Extra connections allowed beyond the pool size.
        database_pool_timeout: Seconds to wait for a free pooled connection.
        database_pool_recycle: Seconds after which a connection is replaced.
        database_pool_pre_ping: Test each connection before handing it out.
        database_echo: Log every SQL statement. Refused outside development:
            SQLAlchemy writes those lines outside the structured formatter, and
            they carry bound parameter values.
        database_connect_timeout: Seconds allowed to open a new connection.
        database_breaker_failure_threshold: Consecutive connectivity failures
            that open the database circuit breaker.
        database_breaker_reset_timeout: Seconds the breaker stays open before
            it lets a probe call through.
        rate_limit_requests: Requests allowed per client within the window.
        rate_limit_window: Length of the rate-limit window in seconds.
    """

    # hide_input_in_errors keeps a rejected value out of the startup error, which
    # would otherwise print the raw environment, secrets included, to the logs.
    model_config = SettingsConfigDict(
        case_sensitive=False,
        extra="ignore",
        validate_by_name=True,
        validate_by_alias=True,
        hide_input_in_errors=True,
    )

    project_name: str = "FastAPI Template"
    api_v1_str: str = "/api/v1"

    environment: Environment = "development"
    debug: bool = False
    log_level: LogLevel = "info"
    log_format: LogFormat = "json"
    cors_origins: str = "http://localhost:4200"
    api_docs_enabled: bool | None = None

    database_url: str = Field(default=DEFAULT_DATABASE_URL, alias="DATABASE_URL")
    database_migration_url: str | None = Field(
        default=None, alias="DIRECT_DATABASE_URL"
    )
    database_ssl_mode: SslMode | None = None
    database_allow_insecure_transport: bool = False

    database_pool_size: int = Field(default=5, ge=1, le=100)
    database_max_overflow: int = Field(default=10, ge=0, le=100)
    database_pool_timeout: int = Field(default=30, ge=1, le=300)
    database_pool_recycle: int = Field(default=3600, ge=30, le=86400)
    database_pool_pre_ping: bool = True
    database_echo: bool = False
    database_connect_timeout: int = Field(default=10, ge=1, le=120)

    database_breaker_failure_threshold: int = Field(default=5, ge=1, le=100)
    database_breaker_reset_timeout: float = Field(default=30.0, gt=0, le=600)

    rate_limit_requests: int = Field(default=100, ge=1, le=100_000)
    rate_limit_window: int = Field(default=60, ge=1, le=3600)

    @model_validator(mode="after")
    def _enforce_environment_policy(self) -> Self:
        self._refuse_development_only_flags()
        self._refuse_wildcard_cors_when_deployed()
        self._refuse_unencrypted_database_when_deployed()
        self.validate_auth_secrets(production_like=self.is_production_like)
        return self

    def _refuse_development_only_flags(self) -> None:
        if self.is_development:
            return
        if self.debug:
            raise ValueError("DEBUG may only be enabled when ENVIRONMENT=development")
        if self.database_echo:
            raise ValueError(
                "DATABASE_ECHO may only be enabled when ENVIRONMENT=development"
            )

    def _refuse_wildcard_cors_when_deployed(self) -> None:
        if self.is_production_like and WILDCARD_ORIGIN in self.cors_origins_list:
            raise ValueError(
                "CORS_ORIGINS must list explicit origins in staging and production"
            )

    def _refuse_unencrypted_database_when_deployed(self) -> None:
        if not self.is_production_like or self.database_allow_insecure_transport:
            return
        for variable, url in self._database_urls():
            if not _is_transport_encrypted(url, self.database_ssl_mode, variable):
                # The message names the setting only: the URL holds credentials.
                raise ValueError(INSECURE_TRANSPORT_MESSAGE.format(variable=variable))

    def _database_urls(self) -> list[tuple[str, str]]:
        urls = [(DATABASE_URL_VARIABLE, self.database_url)]
        if self.database_migration_url:
            urls.append((MIGRATION_URL_VARIABLE, self.database_migration_url))
        return urls

    @property
    def version(self) -> str:
        """The application version, as declared in ``pyproject.toml``.

        Read from the installed project's metadata, which ``pip install`` fills
        from ``[project] version``. A property and not a field, so no environment
        variable can override it.

        Raises:
            importlib.metadata.PackageNotFoundError: The project is not installed;
                run ``pip install ".[dev]"`` from the ``api`` directory.
        """
        return installed_version(DISTRIBUTION_NAME)

    @property
    def is_production(self) -> bool:
        """Whether the deployment stage is production."""
        return self.environment == "production"

    @property
    def is_staging(self) -> bool:
        """Whether the deployment stage is staging."""
        return self.environment == "staging"

    @property
    def is_production_like(self) -> bool:
        """Whether the stage is staging or production, where hardening applies."""
        return self.is_production or self.is_staging

    @property
    def is_development(self) -> bool:
        """Whether the stage is development.

        Decided by ``environment`` alone, so no other flag can switch on
        development-only conveniences in a deployed environment.
        """
        return self.environment == "development"

    @property
    def is_local(self) -> bool:
        """Whether the stage is a developer machine or a test run."""
        return self.environment in ("development", "test")

    @property
    def docs_enabled(self) -> bool:
        """Whether to serve the interactive API docs and the OpenAPI schema.

        ``api_docs_enabled`` wins when set; otherwise the docs are served in
        every stage except production.
        """
        if self.api_docs_enabled is not None:
            return self.api_docs_enabled
        return not self.is_production

    @property
    def cors_origins_list(self) -> list[str]:
        """The allowed CORS origins as a list; empty when none are configured."""
        return [
            origin.strip() for origin in self.cors_origins.split(",") if origin.strip()
        ]

    @property
    def migration_database_url(self) -> str:
        """The URL schema migrations connect with.

        Returns:
            The direct migration URL when configured, otherwise ``database_url``.
        """
        return self.database_migration_url or self.database_url


settings = Settings()
