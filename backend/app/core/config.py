from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict

ROOT = Path(__file__).resolve().parents[3]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=ROOT / ".env", extra="ignore")
    cloudflare_account_id: str = ""
    cloudflare_api_token: SecretStr = SecretStr("")
    cloudflare_model: str = "@cf/zai-org/glm-4.7-flash"
    cloudflare_internal_model: str = "@cf/google/gemma-4-26b-a4b-it"
    cloudflare_vision_model: str = "@cf/google/gemma-4-26b-a4b-it"
    cloudflare_cross_model: str = "@cf/google/gemma-4-26b-a4b-it"
    database_url: SecretStr = SecretStr(
        "postgresql+psycopg://expense:expense_local@127.0.0.1:5432/expense_audit"
    )
    storage_dir: Path = ROOT / "data"
    daily_neuron_budget: float = 8000
    budget_scope: Literal["application", "account"] = "application"
    max_file_mb: int = 20
    max_document_pages: int = 10
    max_completion_tokens: int = 7000
    audit_completion_tokens: int = 12000
    api_timeout_seconds: int = 180


@lru_cache
def get_settings() -> Settings:
    return Settings()
