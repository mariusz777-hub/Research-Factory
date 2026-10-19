from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path

from pydantic import BaseModel, Field


class Settings(BaseModel):
    database_url: str = "postgresql+psycopg://research:research@localhost:5432/research_factory"
    artifact_root: Path = Path("./data")
    question_library: Path = Path("./config/question_templates.yaml")
    log_level: str = "INFO"

    openai_api_key: str = ""
    openai_base_url: str = "https://api.openai.com/v1"
    openai_model: str = "gpt-4.1-mini"

    deepseek_api_key: str = ""
    deepseek_base_url: str = "https://api.deepseek.com"
    deepseek_model: str = "deepseek-chat"

    gemini_api_key: str = ""
    gemini_base_url: str = "https://generativelanguage.googleapis.com/v1beta"
    gemini_model: str = "gemini-2.5-flash"

    github_token: str = ""
    reddit_token: str = ""
    reddit_user_agent: str = "ResearchFactory/1.1"
    tavily_api_key: str = ""

    # Adapter do istniejącego scrapera Google użytkownika. Wartość może wskazywać
    # moduł Pythona (np. "my_scraper:search") albo plik
    # (np. "C:/projekty/google_scraper.py:search").
    google_scraper_target: str = ""

    worker_poll_seconds: float = Field(default=1.0, ge=0.1, le=30)
    job_lease_seconds: int = Field(default=300, ge=30, le=3600)
    job_max_attempts: int = Field(default=4, ge=1, le=20)
    retry_base_seconds: int = Field(default=5, ge=1, le=300)
    retry_max_seconds: int = Field(default=300, ge=5, le=3600)
    model_timeout_seconds: float = Field(default=180, ge=5, le=900)
    model_min_interval_seconds: float = Field(default=1.5, ge=0, le=60)
    research_timeout_seconds: float = Field(default=30, ge=5, le=180)
    github_result_limit: int = Field(default=10, ge=1, le=50)
    reddit_result_limit: int = Field(default=10, ge=1, le=50)
    google_result_limit: int = Field(default=10, ge=1, le=50)
    web_result_limit: int = Field(default=10, ge=1, le=50)
    synthesis_max_chars: int = Field(default=90000, ge=10000, le=300000)
    project_model_call_limit: int = Field(default=500, ge=1, le=100000)
    project_token_limit: int = Field(default=500000, ge=1000, le=100000000)

    @classmethod
    def from_env(cls, env_file: str | Path = ".env") -> "Settings":
        values: dict[str, str] = {}
        path = Path(env_file)
        if path.is_file():
            for raw_line in path.read_text(encoding="utf-8").splitlines():
                line = raw_line.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                key, value = line.split("=", 1)
                values[key.strip().lower()] = value.strip().strip('"').strip("'")
        for field_name in cls.model_fields:
            env_value = os.getenv(field_name.upper())
            if env_value is not None:
                values[field_name] = env_value
        return cls.model_validate(values)


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings.from_env()
