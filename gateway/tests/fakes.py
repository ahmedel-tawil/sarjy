import asyncio
from contextlib import asynccontextmanager
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from pydantic import BaseModel
from sarjy_gateway.catalogue import (
    CatalogueContext,
    City,
    Faq,
    ProductType,
    TicketDetails,
    Tour,
    TourDetails,
    TourQuery,
    TourSearch,
)
from sarjy_gateway.llm import ChatMessage, Finished, TextDelta, ToolSpec
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


# Each request plays the next scripted round of events; the last round repeats. By
# default there is one round of plain text.
class FakeChatModel:
    def __init__(
        self,
        deltas: Sequence[str] = ("Try the ", "Louvre."),
        error: Exception | None = None,
        rounds: Sequence[Sequence[ChatEvent]] | None = None,
    ) -> None:
        self.rounds = rounds if rounds is not None else [[TextDelta(delta) for delta in deltas]]
        self.error = error
        self.requests: list[list[ChatMessage]] = []
        self.offered_tools: list[list[str]] = []

    @asynccontextmanager
    async def stream(
        self, messages: Sequence[ChatMessage], tools: Sequence[ToolSpec]
    ) -> AsyncGenerator[AsyncIterator[ChatEvent]]:
        self.requests.append(list(messages))
        self.offered_tools.append([tool.name for tool in tools])
        if self.error is not None:
            raise self.error
        yield self._events(self.rounds[min(len(self.requests), len(self.rounds)) - 1])

    @staticmethod
    async def _events(events: Sequence[ChatEvent]) -> AsyncIterator[ChatEvent]:
        for event in events:
            yield event
        yield Finished("stop")


class WeatherArguments(BaseModel):
    city: str
    date: str


# Answers every call with `result`, or raises `error`, after `seconds` of real waiting.
class FakeWeatherTool:
    spec = ToolSpec("get_weather", "The forecast for a UAE city.", WeatherArguments.model_json_schema())

    def __init__(self, result: str = '{"temperature_c": 31}', error: Exception | None = None, seconds: float = 0) -> None:
        self.result = result
        self.error = error
        self.seconds = seconds
        self.calls: list[WeatherArguments] = []

    async def run(self, arguments: str) -> str:
        self.calls.append(WeatherArguments.model_validate_json(arguments))
        await asyncio.sleep(self.seconds)
        if self.error is not None:
            raise self.error
        return self.result


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


# Stands still until a test moves it.
class ManualClock:
    def __init__(self) -> None:
        self.now = 0.0

    def __call__(self) -> float:
        return self.now


# Each reading is 10 ms after the last, so marks are predictable.
class TickingClock:
    def __init__(self) -> None:
        self.now = 0.0

    def __call__(self) -> float:
        self.now += 0.01
        return self.now


FERRARI = Tour(
    name="Ferrari World Abu Dhabi Tickets",
    type="tour",
    slug="ferrari-world-abu-dhbai",
    city="Abu Dhabi",
    price="from AED 345",
    accessible=True,
    link="https://magicexperience.ae/tours/ferrari-world-abu-dhbai",
)


# Answers with fixed lean results, or raises `error`, and records what it was asked.
class FakeCatalogue:
    def __init__(self, error: Exception | None = None) -> None:
        self.error = error
        self.queries: list[TourQuery] = []
        self.lookups: list[tuple[ProductType, str]] = []

    async def context(self) -> CatalogueContext:
        if self.error is not None:
            raise self.error
        return CatalogueContext(
            operator="Magic Experience",
            website="https://magicexperience.ae",
            cities=[City(name="Abu Dhabi", tours=7), City(name="Dubai", tours=8)],
            categories=["safari", "theme parks"],
            faqs=[Faq(question="Can I cancel my booking?", answer="Up to 24 hours before.")],
        )

    async def search(self, query: TourQuery) -> TourSearch:
        self.queries.append(query)
        if self.error is not None:
            raise self.error
        return TourSearch(tours=[FERRARI], total=1)

    async def tour(self, product_type: ProductType, slug: str) -> TourDetails:
        self.lookups.append((product_type, slug))
        if self.error is not None:
            raise self.error
        ticket = TicketDetails(
            name="General Admission",
            prices=["adult: AED 345", "child: AED 345"],
            price="from AED 345",
            duration="8 hours",
            children=None,
            cancellation=None,
        )
        return TourDetails(
            name=FERRARI.name,
            type=FERRARI.type,
            slug=FERRARI.slug,
            city=FERRARI.city,
            price=FERRARI.price,
            accessible=FERRARI.accessible,
            link=FERRARI.link,
            summary="The world's largest indoor theme park.",
            duration=None,
            every_ticket=None,
            tickets=[ticket],
            restrictions=[],
            notes=[],
            requirements=[],
            languages=[],
        )
