from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict
from sqlalchemy import URL


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=Path(__file__).resolve().parents[2] / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    data_mode: Literal["SIMULATED", "PUBLIC", "HYBRID"] = "SIMULATED"

    postgres_host: str = "localhost"
    postgres_port: int = 5432
    postgres_db: str = "aquifero_vivo"
    postgres_user: str = "aquifero"
    postgres_password: str = "aquifero_local"
    cors_origins: list[str] = ["http://localhost:5173"]

    @property
    def database_url(self) -> URL:
        return URL.create(
            "postgresql+psycopg",
            username=self.postgres_user,
            password=self.postgres_password,
            host=self.postgres_host,
            port=self.postgres_port,
            database=self.postgres_db,
        )


@lru_cache
def get_settings() -> Settings:
    return Settings()
