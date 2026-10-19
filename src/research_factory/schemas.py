from __future__ import annotations

from pydantic import BaseModel, Field, field_validator


ALLOWED_MODELS = {"openai", "deepseek", "gemini"}
ALLOWED_SCOPES = {"github", "web", "reddit", "google"}


class ProjectCreate(BaseModel):
    name: str = Field(min_length=2, max_length=200)
    idea: str = Field(min_length=20, max_length=20000)
    models: list[str] = Field(min_length=1)
    scopes: list[str] = Field(default_factory=lambda: ["github", "web"])
    google_research_input: str = Field(default="", max_length=200000)

    @field_validator("models")
    @classmethod
    def validate_models(cls, value: list[str]) -> list[str]:
        clean = list(dict.fromkeys(item.lower() for item in value))
        unknown = set(clean) - ALLOWED_MODELS
        if unknown:
            raise ValueError(f"Nieobsługiwane modele: {', '.join(sorted(unknown))}")
        return clean

    @field_validator("scopes")
    @classmethod
    def validate_scopes(cls, value: list[str]) -> list[str]:
        clean = list(dict.fromkeys(item.lower() for item in value))
        unknown = set(clean) - ALLOWED_SCOPES
        if unknown:
            raise ValueError(f"Nieobsługiwane zakresy: {', '.join(sorted(unknown))}")
        return clean
