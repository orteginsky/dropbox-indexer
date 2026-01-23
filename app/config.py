from pydantic_settings import BaseSettings
from functools import lru_cache


class Settings(BaseSettings):
    """Application configuration loaded from environment variables."""

    # Token Service (AccessTokenDropbox)
    token_service_url: str = "https://accesstokendropbox-223080314602.us-central1.run.app"
    api_secret_key: str = ""

    # GCP Configuration
    gcp_project_id: str = "nexus-legal-ops"
    pubsub_topic_name: str = "dropbox-crawl-tasks"
    gcp_region: str = "us-central1"

    # Database
    database_url: str = "postgresql://user:pass@localhost:5432/dropbox_index"

    # Application
    log_level: str = "INFO"

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


@lru_cache()
def get_settings() -> Settings:
    """Cached settings instance."""
    return Settings()
