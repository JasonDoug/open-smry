"""
Application Configuration (Pydantic Settings).
Supports Cloud LLMs (Claude, GPT, Gemini), OpenRouter, and Local AI (Ollama, LM Studio, llama.cpp, vLLM).
"""
from functools import lru_cache
from typing import Optional
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=(".env", "../.env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_name: str = "Summary AI — Agentic Reading, Summarizing & Research API"
    app_version: str = "1.0.0"
    host: str = "0.0.0.0"
    port: int = 8000
    database_url: str = "sqlite:///./.data/summary_ai.db"

    # Cloud LLM Provider Keys
    anthropic_api_key: Optional[str] = None
    openai_api_key: Optional[str] = None
    gemini_api_key: Optional[str] = None

    # Default Cloud Models
    default_claude_model: str = "claude-3-7-sonnet-latest"
    default_gpt_model: str = "gpt-4o"
    default_gemini_model: str = "gemini-2.5-pro"

    # OpenRouter Support (https://openrouter.ai/api/v1)
    openrouter_api_key: Optional[str] = None
    openrouter_base_url: str = "https://openrouter.ai/api/v1"
    openrouter_default_model: str = "openrouter/free"
    openrouter_free_router: str = "openrouter/free"
    openrouter_site_url: str = "https://github.com/JasonDoug/open-smry"
    openrouter_app_title: str = "Summary AI"

    # Local AI Support (Ollama, LM Studio, llama.cpp, vLLM)
    ollama_base_url: str = "http://localhost:11434"
    ollama_default_model: str = "llama3.2"
    ollama_embedding_model: str = "nomic-embed-text"
    local_openai_base_url: Optional[str] = None
    local_openai_api_key: str = "local-no-key-required"


@lru_cache
def get_settings() -> Settings:
    return Settings()
