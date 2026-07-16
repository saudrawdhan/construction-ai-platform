from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict

# Endpoint and default model for each supported provider. Any OpenAI-compatible engine works;
# these presets let an operator select one with a single LLM_PROVIDER value. Explicit
# LLM_BASE_URL / LLM_MODEL settings always take precedence over the preset.
LLM_PRESETS: dict[str, tuple[str, str]] = {
    "gemini": ("https://generativelanguage.googleapis.com/v1beta/openai/", "gemini-2.5-flash"),
    "groq": ("https://api.groq.com/openai/v1/", "llama-3.3-70b-versatile"),
    "openai": ("https://api.openai.com/v1/", "gpt-4o-mini"),
    "local": ("http://host.docker.internal:11434/v1/", "qwen2.5:7b-instruct"),
}


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    app_name: str = "Construction Operations Intelligence Platform"
    environment: str = "development"
    debug: bool = True
    api_v1_prefix: str = "/api/v1"
    cors_origins: str = "http://localhost:5173,http://localhost:4173,http://127.0.0.1:5173"

    database_url: str = (
        "postgresql+asyncpg://construction:construction@localhost:5432/construction_ai"
    )
    redis_url: str = "redis://localhost:6379/0"

    # LLM engine behind the LLMClient abstraction. "mock" (default in tests) spends nothing;
    # "local" runs an open-weights model via Ollama on this machine; "gemini"/"groq"/"openai"
    # call a cloud endpoint. Base URL and model fall back to the provider preset when left blank.
    llm_provider: str = "gemini"
    llm_model: str = ""
    llm_base_url: str = ""
    llm_api_key: str = ""
    llm_request_timeout: float = 120.0
    llm_max_retries: int = 6
    llm_backoff_base: float = 1.0
    llm_backoff_cap: float = 30.0

    # embedding_provider: "hash" (deterministic, dependency-free) | "local" (real fastembed)
    embedding_provider: str = "local"
    embedding_model: str = "intfloat/multilingual-e5-large"
    embedding_dimensions: int = 1024
    fastembed_cache_dir: str = "/models"

    jwt_secret: str = "dev-secret-change-me-in-production-please-32bytes-min"
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 30

    # Auth cookie: the frontend authenticates via an httpOnly cookie (not JS-readable), which
    # closes the XSS token-theft vector. Set cookie_secure=true in production (HTTPS only).
    auth_cookie_name: str = "access_token"
    cookie_secure: bool = False
    cookie_samesite: str = "lax"

    def resolved_llm_endpoint(self) -> tuple[str, str]:
        """Return the (base_url, model) to use, applying the provider preset for any value not
        set explicitly. Explicit LLM_BASE_URL / LLM_MODEL always win."""
        preset = LLM_PRESETS.get(self.llm_provider, ("", ""))
        return (self.llm_base_url or preset[0], self.llm_model or preset[1])


@lru_cache
def get_settings() -> Settings:
    return Settings()
