from pydantic_settings import BaseSettings
from functools import lru_cache
from typing import Optional


class AppSettings(BaseSettings):
    """Application settings loaded from environment variables."""
    
    openai_api_key: Optional[str] = None
    openai_base_url: Optional[str] = None
    openai_default_model: str = "gpt-4o-mini"
    anthropic_default_model: str = "claude-sonnet-4-5-20250929"  # Valid: claude-sonnet-4-5-20250929, claude-haiku-4-5-20251001, claude-opus-4-5-20251101
    deepseek_default_model: str = "deepseek-chat"
    gemini_default_model: str = "gemini-pro"
    http_proxy: Optional[str] = None  # For HTTP proxy support
    https_proxy: Optional[str] = None  # For HTTPS proxy support
    env: str = "dev"
    database_url: str = "postgresql+psycopg2://route_llm:route_llm@localhost:5432/route_llm"
    redis_url: str = "redis://localhost:6379/0"
    storage_dir: str = "storage"  # Directory for storing uploaded files
    public_base_url: str = "http://localhost:8000"  # Base URL for public file access
    
    # Key pool and retry settings
    key_rpm_window_seconds: int = 60  # RPM window duration
    key_cooldown_seconds_on_429: int = 30  # Cooldown after rate limit error
    key_cooldown_seconds_on_network_error: int = 15  # Cooldown after network/transient error
    key_error_decay_minutes: int = 10  # Minutes before error_count_recent decays
    
    # Sync endpoint retry settings
    sync_llm_max_retries: int = 2  # Number of provider attempts for /v1/llm/chat
    sync_llm_max_retry_wait_seconds: int = 1  # Max wait time in sync endpoint (should be minimal)
    
    # Worker/async retry settings
    worker_max_attempts: int = 5  # Max attempts per Run (across requeues)
    worker_base_backoff_seconds: int = 5  # Base delay for exponential backoff
    worker_max_backoff_seconds: int = 60  # Maximum backoff delay
    
    # Auth settings
    auth_jwt_secret_key: str = "CHANGE_ME_IN_ENV"
    auth_jwt_algorithm: str = "HS256"
    default_admin_email: str = "admin@example.com"
    default_admin_password: str = "Admin123!"
    
    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = False


@lru_cache()
def get_settings() -> AppSettings:
    """
    Get a singleton instance of AppSettings.
    Uses LRU cache to ensure we only create one instance.
    """
    return AppSettings()

