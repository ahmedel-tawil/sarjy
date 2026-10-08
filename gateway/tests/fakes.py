from contextlib import asynccontextmanager
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from sarjy_gateway.llm import ChatMessage, Finished, TextDelta
from sarjy_gateway.tts import Voices


if TYPE_CHECKING:
    from collections.abc import AsyncGenerator, AsyncIterator, Sequence

    from sarjy_gateway.llm import ChatEvent


class FakeSpeechToText:
    def __init__(self, transcript: str = "What can we do in Abu Dhabi?", error: Exception | None = None) -> None:
        self.transcript = transcript
        self.error = error
        self.clips: list[bytes] = []

    async def transcribe(self, audio: bytes) -> str:
        self.clips.append(audio)
        if self.error is not None:
            raise self.error
        return self.transcript


class FakeChatModel:
    def __init__(self, deltas: Sequence[str] = ("Try the ", "Louvre."), error: Exception | None = None) -> None:
        self.deltas = deltas
        self.error = error
        self.requests: list[list[ChatMessage]] = []

    @asynccontextmanager
    async def stream(self, messages: Sequence[ChatMessage]) -> AsyncGenerator[AsyncIterator[ChatEvent]]:
        self.requests.append(list(messages))
        if self.error is not None:
            raise self.error
        yield self._events()

    async def _events(self) -> AsyncIterator[ChatEvent]:
        for delta in self.deltas:
            yield TextDelta(delta)
        yield Finished("stop")


@dataclass(frozen=True)
class SpeechRequest:
    text: str
    voice: str | None


class FakeTextToSpeech:
    def __init__(self, error: Exception | None = None) -> None:
        self.error = error
        self.requests: list[SpeechRequest] = []

    async def voices(self) -> Voices:
        if self.error is not None:
            raise self.error
        return Voices(voices=["af_heart", "am_adam"], default="af_heart")

    async def synthesize(self, text: str, voice: str | None) -> bytes:
        self.requests.append(SpeechRequest(text, voice))
        if self.error is not None:
            raise self.error
        return b"RIFF" + text.encode()


@dataclass
class RecordingListener:
    events: list[str] = field(default_factory=list[str])

    async def transcript(self, turn_id: str, text: str) -> None:
        self.events.append(f"transcript {text}")
        assert turn_id

    async def reply(self, turn_id: str, text: str) -> None:
        self.events.append(f"reply {text}")
        assert turn_id

    async def audio(self, turn_id: str, wav: bytes) -> None:
        self.events.append(f"audio {len(wav)} bytes")
        assert turn_id


# Each reading is 10 ms after the last, so marks are predictable.
class TickingClock:
    def __init__(self) -> None:
        self.now = 0.0

    def __call__(self) -> float:
        self.now += 0.01
        return self.now
