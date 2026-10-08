from dataclasses import dataclass
from typing import TYPE_CHECKING, Protocol

import httpx2
from pydantic import BaseModel, ValidationError


if TYPE_CHECKING:
    from pydantic import SecretStr


GROQ_TRANSCRIPTIONS_URL = "https://api.groq.com/openai/v1/audio/transcriptions"
# Spelling guidance for names Whisper would otherwise mishear (Groq allows 224 tokens).
VOCABULARY_PROMPT = (
    "Sarjy, Magic Experience, Dubai, Abu Dhabi, Sharjah, Ras Al Khaimah, Fujairah, AED, "
    "dirhams, desert safari, dune bashing, dhow cruise, Burj Khalifa."
)


class Transcription(BaseModel):
    text: str


@dataclass(frozen=True)
class Container:
    file_name: str
    mime_type: str


class SpeechToTextError(RuntimeError):
    pass


class RateLimitedError(SpeechToTextError):
    pass


class SpeechToText(Protocol):
    async def transcribe(self, audio: bytes) -> str: ...


class GroqSpeechToText:
    def __init__(self, client: httpx2.AsyncClient, api_key: SecretStr, model: str) -> None:
        self._client = client
        self._api_key = api_key
        self._model = model

    async def transcribe(self, audio: bytes) -> str:
        container = container_of(audio)
        try:
            response = await self._client.post(
                GROQ_TRANSCRIPTIONS_URL,
                headers={"Authorization": f"Bearer {self._api_key.get_secret_value()}"},
                data={
                    "model": self._model,
                    "language": "en",
                    "response_format": "json",
                    "temperature": "0",
                    "prompt": VOCABULARY_PROMPT,
                },
                files={"file": (container.file_name, audio, container.mime_type)},
            )
        except httpx2.HTTPError as error:
            message = f"Groq transcription request failed: {type(error).__name__}"
            raise SpeechToTextError(message) from error
        if response.status_code == httpx2.codes.TOO_MANY_REQUESTS:
            message = "Groq rate limit reached"
            raise RateLimitedError(message)
        if response.is_error:
            message = f"Groq transcription failed with HTTP {response.status_code}"
            raise SpeechToTextError(message)
        try:
            return Transcription.model_validate_json(response.content).text.strip()
        except ValidationError as error:
            message = "Groq answered with something other than a transcription"
            raise SpeechToTextError(message) from error


class MissingSpeechToText:
    async def transcribe(self, audio: bytes) -> str:
        message = f"SARJY_GROQ_API_KEY is not set; cannot transcribe {len(audio)} bytes"
        raise SpeechToTextError(message)


# Browsers record different containers (WebM in Chrome, MP4 in Safari); each starts with
# a fixed signature, and Groq needs the matching file extension.
def container_of(audio: bytes) -> Container:
    if audio.startswith(b"\x1a\x45\xdf\xa3"):
        return Container("turn.webm", "audio/webm")
    if audio[4:8] == b"ftyp":
        return Container("turn.mp4", "audio/mp4")
    if audio.startswith(b"RIFF") and audio[8:12] == b"WAVE":
        return Container("turn.wav", "audio/wav")
    if audio.startswith(b"OggS"):
        return Container("turn.ogg", "audio/ogg")
    message = "audio is not WebM, MP4, WAV or Ogg"
    raise SpeechToTextError(message)
