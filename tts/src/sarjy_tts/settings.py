from pathlib import Path
from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """TTS configuration, read from environment variables once at startup."""

    model_config = SettingsConfigDict(env_prefix="SARJY_", frozen=True)

    host: str = "127.0.0.1"
    # Cloud Run injects PORT without our prefix.
    port: int = Field(default=8080, validation_alias="PORT")
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR"] = "INFO"
    models_dir: Path = Path("tts/models")
    model_file: str = "model.onnx"
    # Unset means every core; Cloud Run sizes are measured in M1.10.
    threads: int | None = Field(default=None, gt=0)
    default_voice: str = "af_heart"
    # Roughly a long paragraph; a turn's reply should never need more.
    max_text_chars: int = Field(default=1_000, gt=0)
