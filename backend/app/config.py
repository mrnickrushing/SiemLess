from typing import Optional
from pydantic_settings import BaseSettings, SettingsConfigDict


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

    # Database
    DATABASE_URL: str = "postgresql+asyncpg://siemless:siemless@localhost:5432/siemless"

    # Redis
    REDIS_URL: str = "redis://localhost:6379/0"

    # Security
    SECRET_KEY: str = "changeme-super-secret-key-for-production"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30

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
    MAX_PAGE_SIZE: int = 1000

    # Correlation engine
    CORRELATION_ENABLED: bool = True
    CORRELATION_WINDOW_CLEANUP_INTERVAL: int = 60  # seconds


settings = Settings()
