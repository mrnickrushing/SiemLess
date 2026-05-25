import sys
from typing import Optional

from pydantic import field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

_DEFAULT_SECRET_KEYS = {
    "changeme-super-secret-key-for-production",
    "change-me-in-production-use-openssl-rand-hex-32",
    "changeme",
    "secret",
}

_DEFAULT_PASSWORDS = {
    "admin",
    "password",
    "changeme",
    "siemless",
}


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # Application
    APP_NAME: str = "SiemLess"
    APP_VERSION: str = "1.0.0"
    DEBUG: bool = False

    # Database — Railway provides postgresql:// or postgres://, we normalise below
    DATABASE_URL: str = "postgresql+asyncpg://siemless:siemless@localhost:5432/siemless"

    # Redis
    REDIS_URL: str = "redis://localhost:6379/0"

    # Security
    SECRET_KEY: str = "changeme-super-secret-key-for-production"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 480  # 8 hours

    # Admin credentials
    ADMIN_USERNAME: str = "admin"
    ADMIN_PASSWORD: str = "changeme"

    # CORS — comma-separated list of allowed origins, or * for dev
    CORS_ORIGINS: str = "*"

    # Port — Railway injects $PORT
    PORT: int = 8000

    # Syslog server
    SYSLOG_HOST: str = "0.0.0.0"
    SYSLOG_PORT: int = 514
    SYSLOG_ENABLED: bool = True

    # Threat intel API keys (optional)
    THREAT_INTEL_VIRUSTOTAL_KEY: Optional[str] = None
    THREAT_INTEL_ABUSEIPDB_KEY: Optional[str] = None

    # SMTP settings for email alerts
    SMTP_HOST: Optional[str] = None
    SMTP_PORT: int = 587
    SMTP_USER: Optional[str] = None
    SMTP_PASS: Optional[str] = None
    SMTP_TLS: bool = True
    ALERT_EMAIL: Optional[str] = None

    # Slack alerts
    SLACK_WEBHOOK_URL: Optional[str] = None

    # Generic webhook
    ALERT_WEBHOOK_URL: Optional[str] = None

    # GeoIP database path
    GEOIP_DB_PATH: Optional[str] = "/data/GeoLite2-City.mmdb"

    # Pagination defaults
    DEFAULT_PAGE_SIZE: int = 50
    MAX_PAGE_SIZE: int = 500

    # Correlation engine
    CORRELATION_ENABLED: bool = True
    CORRELATION_WINDOW_CLEANUP_INTERVAL: int = 60

    @field_validator("DATABASE_URL", mode="before")
    @classmethod
    def normalise_db_url(cls, v: str) -> str:
        """Convert postgres:// or postgresql:// to postgresql+asyncpg://."""
        if v.startswith("postgres://"):
            v = "postgresql+asyncpg://" + v[len("postgres://"):]
        elif v.startswith("postgresql://"):
            v = "postgresql+asyncpg://" + v[len("postgresql://"):]
        return v

    @model_validator(mode="after")
    def enforce_production_secrets(self) -> "Settings":
        if self.DEBUG:
            return self
        errors = []
        if self.SECRET_KEY.lower() in _DEFAULT_SECRET_KEYS:
            errors.append(
                "SECRET_KEY is set to a known default. "
                "Generate one with: openssl rand -hex 32"
            )
        if self.ADMIN_PASSWORD.lower() in _DEFAULT_PASSWORDS:
            errors.append(
                "ADMIN_PASSWORD is set to a known default. "
                "Set a strong password via the ADMIN_PASSWORD environment variable."
            )
        if errors:
            msg = "\n".join(f"  - {e}" for e in errors)
            print(
                f"\n[SiemLess] FATAL: Insecure configuration detected:\n{msg}\n"
                "Set DEBUG=true to bypass this check in development.\n",
                file=sys.stderr,
            )
            sys.exit(1)
        return self

    @property
    def cors_origins_list(self) -> list[str]:
        if self.CORS_ORIGINS.strip() == "*":
            return ["*"]
        return [o.strip() for o in self.CORS_ORIGINS.split(",") if o.strip()]


settings = Settings()
