from typing import TYPE_CHECKING, Protocol

import httpx2
from pydantic import BaseModel


if TYPE_CHECKING:
    from collections.abc import Callable


# The metadata server only exists on Google Cloud; it signs tokens for this service's
# own identity, so no key is stored anywhere (D-45).
METADATA_IDENTITY_URL = "http://metadata.google.internal/computeMetadata/v1/instance/service-accounts/default/identity"
# Google ID tokens live for an hour; renewing well before that avoids edge-of-expiry calls.
TOKEN_REUSE_SECONDS = 50 * 60
# Synthesis is seconds of CPU work, and a TTS cold start adds model loading on top.
REQUEST_TIMEOUT_SECONDS = 30.0


class Voices(BaseModel):
    voices: list[str]
    default: str


class TextToSpeechError(RuntimeError):
    pass


class TextToSpeech(Protocol):
    async def voices(self) -> Voices: ...

    async def synthesize(self, text: str, voice: str) -> bytes: ...

    async def aclose(self) -> None: ...


class TokenSource(Protocol):
    async def token(self) -> str | None: ...


class NoToken:
    async def token(self) -> None:
        return None


class MetadataIdToken:
    def __init__(self, client: httpx2.AsyncClient, audience: str, clock: Callable[[], float]) -> None:
        self._client = client
        self._audience = audience
        self._clock = clock
        self._token: str | None = None
        self._expires_at = 0.0

    async def token(self) -> str:
        if self._token is not None and self._clock() < self._expires_at:
            return self._token
        response = await self._client.get(
            METADATA_IDENTITY_URL, params={"audience": self._audience}, headers={"Metadata-Flavor": "Google"}
        )
        response.raise_for_status()
        self._token = response.text
        self._expires_at = self._clock() + TOKEN_REUSE_SECONDS
        return self._token


class HttpTextToSpeech:
    def __init__(self, client: httpx2.AsyncClient, base_url: str, tokens: TokenSource) -> None:
        self._client = client
        self._base_url = base_url.rstrip("/")
        self._tokens = tokens

    async def voices(self) -> Voices:
        response = await self._request("GET", "/voices")
        return Voices.model_validate_json(response.content)

    async def synthesize(self, text: str, voice: str) -> bytes:
        response = await self._request("POST", "/synthesize", json={"text": text, "voice": voice})
        return response.content

    async def aclose(self) -> None:
        await self._client.aclose()

    async def _request(self, method: str, path: str, json: dict[str, str] | None = None) -> httpx2.Response:
        try:
            token = await self._tokens.token()
            headers = {} if token is None else {"Authorization": f"Bearer {token}"}
            response = await self._client.request(method, f"{self._base_url}{path}", json=json, headers=headers)
            response.raise_for_status()
        except httpx2.HTTPError as error:
            message = f"TTS {method} {path} failed: {error}"
            raise TextToSpeechError(message) from error
        return response


class MissingTextToSpeech:
    async def voices(self) -> Voices:
        message = "SARJY_TTS_URL is not set"
        raise TextToSpeechError(message)

    async def synthesize(self, text: str, voice: str) -> bytes:
        message = f"SARJY_TTS_URL is not set; cannot speak {len(text)} characters as {voice}"
        raise TextToSpeechError(message)

    async def aclose(self) -> None:
        return None
