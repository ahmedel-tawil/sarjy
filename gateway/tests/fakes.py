import asyncio
from contextlib import asynccontextmanager
from dataclasses import dataclass, field
from datetime import UTC, datetime
import itertools
from typing import TYPE_CHECKING
import uuid

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
from sarjy_gateway.conversation_store import SessionId, StoredUser, TurnId
from sarjy_gateway.llm import ChatMessage, Finished, TextDelta, ToolSpec
from sarjy_gateway.memory import Fact
from sarjy_gateway.messages import TourLink
from sarjy_gateway.tts import Voices
from sarjy_gateway.weather import DayForecast, Hour


if TYPE_CHECKING:
    from collections.abc import AsyncGenerator, AsyncIterator, Mapping, Sequence
    from datetime import date

    from sarjy_gateway.conversation_store import StoredTurn
    from sarjy_gateway.identity import UserId
    from sarjy_gateway.llm import ChatEvent
    from sarjy_gateway.weather import Place


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
        self.voice_lists = 0

    async def voices(self) -> Voices:
        self.voice_lists += 1
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
    links: list[TourLink] = field(default_factory=list[TourLink])

    async def transcript(self, turn_id: str, text: str) -> None:
        self.events.append(f"transcript {text}")
        assert turn_id

    async def reply(self, turn_id: str, text: str, links: list[TourLink]) -> None:
        self.events.append(f"reply {text}")
        self.links += links
        assert turn_id

    async def audio(self, turn_id: str, text: str, wav: bytes) -> None:
        self.events.append(f"audio {len(wav)} bytes: {text}")
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


# Answers every forecast with a hot, clear day, or raises `error`, and records requests.
class FakeWeather:
    def __init__(self, error: Exception | None = None) -> None:
        self.error = error
        self.requests: list[tuple[str, date]] = []

    async def forecast(self, place: Place, day: date) -> DayForecast:
        self.requests.append((place.name, day))
        if self.error is not None:
            raise self.error
        return DayForecast(
            city=place.name,
            date=day.isoformat(),
            conditions="clear sky",
            high_c=38.3,
            low_c=30.9,
            chance_of_rain_percent=0,
            hours=[Hour(time="15:00", temperature_c=35.4), Hour(time="18:00", temperature_c=33.3)],
        )


FIXED_PROMPT = "You are Sarjy. Today is Friday 9 October 2026."


# Records the facts each turn's prompt was built with.
class FakePrompt:
    def __init__(self) -> None:
        self.facts_seen: list[dict[str, str]] = []

    async def build(self, facts: Mapping[str, str]) -> str:
        self.facts_seen.append(dict(facts))
        return FIXED_PROMPT


# Answers a ping, or raises `error` as an unreachable database would.
class FakeDatabase:
    def __init__(self, error: Exception | None = None) -> None:
        self.error = error

    async def ping(self) -> None:
        if self.error is not None:
            raise self.error


SOME_MOMENT = datetime(2026, 10, 9, 12, 0, tzinfo=UTC)


# Keeps sessions and turns in memory, or raises `error` as an unreachable database would.
class FakeConversationStore:
    def __init__(self, error: Exception | None = None) -> None:
        self.error = error
        self.sessions: list[tuple[UserId, SessionId]] = []
        self.saved: dict[SessionId, list[StoredTurn]] = {}
        self.stored_marks: dict[TurnId, dict[str, float]] = {}

    async def start_session(self, user_id: UserId) -> SessionId:
        if self.error is not None:
            raise self.error
        session_id = SessionId(uuid.uuid7())
        self.sessions.append((user_id, session_id))
        return session_id

    async def save_turn(self, session_id: SessionId, turn: StoredTurn) -> None:
        if self.error is not None:
            raise self.error
        self.saved.setdefault(session_id, []).append(turn)

    async def user(self, user_id: UserId) -> StoredUser | None:
        if self.error is not None:
            raise self.error
        if all(known != user_id for known, _ in self.sessions):
            return None
        return StoredUser(id=user_id, created_at=SOME_MOMENT, last_seen_at=SOME_MOMENT)

    async def turns(self, session_id: SessionId) -> list[StoredTurn]:
        if self.error is not None:
            raise self.error
        return self.saved.get(session_id, [])

    # Like Postgres: marks only for a turn of this session, and the first value kept.
    async def save_marks(self, session_id: SessionId, turn_id: TurnId, marks: Mapping[str, float]) -> None:
        if self.error is not None:
            raise self.error
        if any(turn.id == turn_id for turn in self.saved.get(session_id, [])):
            self.stored_marks[turn_id] = dict(marks) | self.stored_marks.get(turn_id, {})

    async def marks(self, turn_id: TurnId) -> dict[str, float]:
        if self.error is not None:
            raise self.error
        return self.stored_marks.get(turn_id, {})


# Keeps facts per user in memory, or raises `error` as an unreachable database would.
class FakeFactStore:
    def __init__(self, facts: dict[UserId, dict[str, str]] | None = None, error: Exception | None = None) -> None:
        self.saved = facts if facts is not None else {}
        self.error = error

    async def facts(self, user_id: UserId) -> list[Fact]:
        if self.error is not None:
            raise self.error
        return list(itertools.starmap(Fact, sorted(self.saved.get(user_id, {}).items())))

    async def remember(self, user_id: UserId, fact: Fact) -> None:
        if self.error is not None:
            raise self.error
        self.saved.setdefault(user_id, {})[fact.key] = fact.value

    async def forget(self, user_id: UserId, key: str) -> bool:
        if self.error is not None:
            raise self.error
        return self.saved.get(user_id, {}).pop(key, None) is not None

    async def forget_all(self, user_id: UserId) -> None:
        if self.error is not None:
            raise self.error
        self.saved.pop(user_id, None)


# Keeps every list of facts the memory tools pushed to the page.
@dataclass
class RecordingMemoryListener:
    pushes: list[dict[str, str]] = field(default_factory=list[dict[str, str]])

    async def memory(self, facts: Mapping[str, str]) -> None:
        self.pushes.append(dict(facts))


# Answers with a fixed raw SayTech response and records what was asked (M3.9).
class FakeRawCatalogue:
    def __init__(self, answer: str = '{"results": [], "total": 0, "unused": "kept"}') -> None:
        self.answer = answer
        self.queries: list[TourQuery] = []
        self.lookups: list[tuple[ProductType, str]] = []

    async def raw_search(self, query: TourQuery) -> str:
        self.queries.append(query)
        return self.answer

    async def raw_tour(self, product_type: ProductType, slug: str) -> str:
        self.lookups.append((product_type, slug))
        return self.answer
