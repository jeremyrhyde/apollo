"""Application configuration loaded from the environment or `.env`.

Field names are uppercase to match environment variables — setting `PORT=9000`
overrides the default. Add every new knob here (and to `.env.example`) rather
than reading `os.environ` at the call site.

Domain configuration (exercises, self-care types, colors, timezone) lives in
the YAML files under CONFIG_DIR, not here; these are deployment settings.
"""

from __future__ import annotations

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Runtime settings for the Apollo server."""

    HOST: str = "0.0.0.0"
    PORT: int = 8001
    LOG_LEVEL: str = "info"
    WEB_DIR: str = "./frontend/dist"
    DB_PATH: str = "./apollo.db"
    CONFIG_DIR: str = "./config"

    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", extra="ignore"
    )
