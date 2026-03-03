"""
Application configuration loaded from environment variables.

Uses pydantic-settings to validate and type-check all env vars at startup.
Missing required vars without defaults will cause an immediate startup failure
with a clear error message.
"""

from __future__ import annotations

from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

_DEFAULT_SECRETS = {
    "change-me-in-production-min-32-chars",
    "change-me-too-different-from-secret-key",
    "change-me-too-different-again",
}


class Settings(BaseSettings):
    """Central configuration sourced from environment / .env file."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore",
    )

    # ── Database ────────────────────────────────────────────────────────
    DATABASE_URL: str = "postgresql+asyncpg://postgres:password@postgres:5432/ofmaint"

    # ── Redis ───────────────────────────────────────────────────────────
    REDIS_URL: str = "redis://redis:6379/0"

    # ── JWT / Auth secrets ──────────────────────────────────────────────
    SECRET_KEY: str = "change-me-in-production-min-32-chars"
    WS_SECRET_KEY: str = "change-me-too-different-from-secret-key"
    MFA_SECRET_KEY: str = "change-me-too-different-again"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 15
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7

    # ── S3 / MinIO ──────────────────────────────────────────────────────
    AWS_ACCESS_KEY_ID: str = "minioadmin"
    AWS_SECRET_ACCESS_KEY: str = "minioadmin"
    AWS_ENDPOINT_URL: str | None = None  # Set for MinIO; omit for real S3
    S3_BUCKET: str = "ofmaint-uploads"
    S3_PRESIGN_TTL: int = 900  # 15 minutes

    # ── Firebase ────────────────────────────────────────────────────────
    FIREBASE_SERVICE_ACCOUNT_JSON: str = ""
    FIREBASE_VAPID_KEY: str = ""

    # ── Email (SendGrid) ────────────────────────────────────────────────
    SENDGRID_API_KEY: str = ""
    EMAIL_FROM: str = "noreply@yourorg.com"

    # ── Frontend / CORS ───────────────────────────────────────────────────
    FRONTEND_URL: str = "http://localhost:5173"
    CORS_ORIGINS: str = ""  # comma-separated extra origins, e.g. "https://workorders.nfmconsulting.com,http://34.174.244.219"

    @property
    def allowed_origins(self) -> list[str]:
        """Return deduplicated list of CORS origins."""
        origins = [self.FRONTEND_URL]
        if self.CORS_ORIGINS:
            origins.extend(o.strip() for o in self.CORS_ORIGINS.split(",") if o.strip())
        return list(dict.fromkeys(origins))

    # ── Observability ───────────────────────────────────────────────────
    SENTRY_DSN: str = ""
    OTEL_EXPORTER_OTLP_ENDPOINT: str = ""

    # ── Application ─────────────────────────────────────────────────────
    ENVIRONMENT: str = "development"
    LOG_LEVEL: str = "INFO"
    ALLOW_SELF_REGISTRATION: bool = False

    @model_validator(mode="after")
    def _validate_secrets(self) -> "Settings":
        """Reject placeholder secrets in non-development environments."""
        if self.ENVIRONMENT != "development":
            for name in ("SECRET_KEY", "WS_SECRET_KEY", "MFA_SECRET_KEY"):
                value = getattr(self, name)
                if value in _DEFAULT_SECRETS:
                    raise ValueError(
                        f"{name} is still set to a placeholder default. "
                        f"Set a strong, unique secret for non-development environments."
                    )
            # Ensure all three keys are distinct
            keys = {self.SECRET_KEY, self.WS_SECRET_KEY, self.MFA_SECRET_KEY}
            if len(keys) < 3:
                raise ValueError(
                    "SECRET_KEY, WS_SECRET_KEY, and MFA_SECRET_KEY must all be different."
                )
        return self

    @property
    def is_production(self) -> bool:
        return self.ENVIRONMENT == "production"

    @property
    def is_development(self) -> bool:
        return self.ENVIRONMENT == "development"


settings = Settings()
