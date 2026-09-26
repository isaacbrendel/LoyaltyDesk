from __future__ import annotations

from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_prefix="LOYALTYDESK_", extra="ignore")

    host: str = "0.0.0.0"
    port: int = 3847
    data_dir: Path = Path("./data/warehouse")
    trace_dir: Path = Path("./data/traces")
    llm_provider: str = "demo"  # demo | openai | anthropic
    openai_model: str = "gpt-4o-mini"
    anthropic_model: str = "claude-sonnet-4-20250514"
    max_tool_rows: int = 50
    session_ttl_minutes: int = 120


def get_settings() -> Settings:
    return Settings()
