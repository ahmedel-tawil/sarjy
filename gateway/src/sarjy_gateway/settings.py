from typing import Literal

from pydantic import DirectoryPath, Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Gateway configuration, read from environment variables once at startup."""

    # .env is for local development only; Cloud Run sets real environment variables.
    model_config = SettingsConfigDict(env_prefix="SARJY_", env_file=".env", extra="ignore", frozen=True)

    host: str = "127.0.0.1"
    # Cloud Run injects PORT without our prefix.
    port: int = Field(default=8080, validation_alias="PORT")
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR"] = "INFO"
    # Unset during local development, when Vite's dev server serves the frontend.
    frontend_dist: DirectoryPath | None = None
    # About a minute of speech in Safari's AAC, several minutes in Chrome's Opus.
    max_turn_audio_bytes: int = Field(default=1_000_000, gt=0)
    # The TTS service; unset when working on the frontend alone.
    tts_url: str | None = None
    # "id_token" on Cloud Run, where TTS is private (D-45); "none" for a local TTS.
    tts_auth: Literal["none", "id_token"] = "none"
    # From Secret Manager on Cloud Run, from the git-ignored .env locally. SecretStr keeps
    # it out of logs, reprs and error messages.
    groq_api_key: SecretStr | None = None
    stt_model: str = "whisper-large-v3-turbo"
