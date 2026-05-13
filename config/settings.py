"""Pydantic-settings based configuration for environment variables and secrets."""

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables and .env file."""

    budget: int = 200
    num_teams: int = 10
    sleeper_draft_id: str = ''
    sleeper_league_id: str = ''
    sleeper_user_id: str = ''
    sleeper_username: str = ''
    strategy_type: str = 'value'
    database_url: str = 'sqlite:///./pigskin.db'
    data_source: str = 'fantasypros'
    data_path: str = 'data/sheets'
    refresh_interval: int = 30
    min_projected_points: float = 0.0
    api_key: str = Field(default='', validation_alias='PIGSKIN_API_KEY')  # Set via PIGSKIN_API_KEY env var or .env
    docs_enabled: bool = Field(default=False, validation_alias='PIGSKIN_DOCS_ENABLED')  # Set PIGSKIN_DOCS_ENABLED=true to expose /docs

    model_config = SettingsConfigDict(
        env_file='.env',
        env_file_encoding='utf-8',
        extra='ignore',
        populate_by_name=True,
    )


from functools import lru_cache


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Return a Settings instance, reading from .env file and environment variables."""
    return Settings()
