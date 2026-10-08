from typing import Literal

from pydantic import DirectoryPath, Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Gateway configuration, read from environment variables once at startup."""

    model_config = SettingsConfigDict(env_prefix="SARJY_", frozen=True)

    host: str = "127.0.0.1"
    # Cloud Run injects PORT without our prefix.
    port: int = Field(default=8080, validation_alias="PORT")
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR"] = "INFO"
    # Unset during local development, when Vite's dev server serves the frontend.
    frontend_dist: DirectoryPath | None = None
