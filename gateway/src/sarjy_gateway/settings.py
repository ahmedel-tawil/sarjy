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
    # Recent turns sent to the LLM as context; older ones only cost tokens and time (D-15).
    max_history_turns: int = Field(default=6, gt=0)
    # The TTS service; unset when working on the frontend alone.
    tts_url: str | None = None
    # "id_token" on Cloud Run, where TTS is private (D-45); "none" for a local TTS.
    tts_auth: Literal["none", "id_token"] = "none"
    # From Secret Manager on Cloud Run, from the git-ignored .env locally. SecretStr keeps
    # it out of logs, reprs and error messages.
    groq_api_key: SecretStr | None = None
    stt_model: str = "whisper-large-v3-turbo"
    # Any OpenAI-compatible provider; Groq by default (D-10). Its own key, so experiment 4
    # can point the LLM elsewhere while STT stays on Groq.
    llm_base_url: str = "https://api.groq.com/openai/v1"
    llm_api_key: SecretStr | None = None
    # Fastest first word and the shortest spoken replies in the first comparison (D-52).
    llm_model: str = "qwen/qwen3.8-27b"
    # Reasoning models think before answering, which delays the first spoken word; the
    # allowed values depend on the model (gpt-oss: low/medium/high, Qwen 3.8: none and up).
    llm_reasoning_effort: str | None = "none"
    llm_temperature: float = Field(default=0.5, ge=0.0, le=2.0)
    # Spoken replies are short; this caps cost and runaway answers.
    llm_max_tokens: int = Field(default=300, gt=0)
    # Which chat provider answers first: "groq" is the OpenAI-compatible provider above,
    # "claude" is Anthropic's. With both keys set, the other one is the fallback (D-63).
    llm_primary: Literal["groq", "claude"] = "groq"
    anthropic_api_key: SecretStr | None = None
    # The fastest Claude to a first word, which is what a voice turn waits for.
    claude_model: str = "claude-haiku-5-5"
    # Thinking is off for Claude, which it allows up to "high"; "low" keeps replies short.
    claude_effort: Literal["low", "medium", "high"] = "low"
    # SayTech's assistant API for Magic Experience; the subdomain picks the operator (D-56).
    saytech_base_url: str = "https://magicexperience.api.saytech.ae/api/v1/public/assistant"
    # SayTech answers in well under a second; a slower answer means a voice turn stalls.
    saytech_timeout_seconds: float = Field(default=3.0, gt=0)
    # How long a SayTech answer is reused without asking again; SayTech marks its answers
    # cacheable for 5 minutes (D-58).
    saytech_cache_seconds: float = Field(default=300.0, ge=0)
    # Open-Meteo: no key, free for non-commercial use (O-21).
    weather_url: str = "https://api.open-meteo.com/v1/forecast"
    weather_timeout_seconds: float = Field(default=3.0, gt=0)
