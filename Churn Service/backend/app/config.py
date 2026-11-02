"""Service configuration, read from environment variables (prefix ``CHURN_SERVICE_``)."""

from __future__ import annotations

import secrets
from functools import lru_cache
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

BACKEND_ROOT = Path(__file__).resolve().parents[1]
PROJECT_ROOT = BACKEND_ROOT.parent


class ServiceSettings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="CHURN_SERVICE_", env_file=BACKEND_ROOT / ".env", extra="ignore")

    data_dir: Path = BACKEND_ROOT / "data"
    secret_key: str | None = None  # generated and persisted in data_dir when not set
    token_ttl_minutes: int = 60 * 12
    max_upload_mb: int = 300
    cors_origins: list[str] = ["http://localhost:5173", "http://127.0.0.1:5173"]
    frontend_dist: Path = PROJECT_ROOT / "frontend" / "dist"
    job_workers: int = 2
    min_history_weeks: int = 52
    demo_customers: int = Field(10000, gt=100)

    @property
    def database_url(self) -> str:
        return f"sqlite:///{(self.data_dir / 'service.db').as_posix()}"

    @property
    def orgs_dir(self) -> Path:
        return self.data_dir / "orgs"

    def resolved_secret(self) -> str:
        if self.secret_key:
            return self.secret_key
        path = self.data_dir / "secret.key"
        if not path.exists():
            self.data_dir.mkdir(parents=True, exist_ok=True)
            path.write_text(secrets.token_urlsafe(48), encoding="utf-8")
        return path.read_text(encoding="utf-8").strip()


@lru_cache
def get_settings() -> ServiceSettings:
    return ServiceSettings()
