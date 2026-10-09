from dataclasses import dataclass
import time
from typing import TYPE_CHECKING

import anthropic
import httpx2

from sarjy_gateway.catalogue import Catalogue, SayTechCatalogue
from sarjy_gateway.catalogue_cache import CachedCatalogue
from sarjy_gateway.claude import ClaudeChatModel
from sarjy_gateway.llm import (
    ChatModel,
    FallbackChatModel,
    GenerationOptions,
    MissingChatModel,
    OpenAiCompatibleChatModel,
)
from sarjy_gateway.stt import GroqSpeechToText, MissingSpeechToText, SpeechToText
from sarjy_gateway.tts import (
    REQUEST_TIMEOUT_SECONDS,
    HttpTextToSpeech,
    MetadataIdToken,
    MissingTextToSpeech,
    NoToken,
    TextToSpeech,
)
from sarjy_gateway.weather import OpenMeteoWeather, Weather


if TYPE_CHECKING:
    from sarjy_gateway.settings import Settings


# The providers a turn needs, sharing one HTTP client (one connection pool) that the app
# closes at shutdown. Anthropic's SDK keeps its own client, closed alongside it. Tests pass
# fakes and no clients.
@dataclass(frozen=True)
class Services:
    stt: SpeechToText
    llm: ChatModel
    tts: TextToSpeech
    catalogue: Catalogue
    weather: Weather
    http_client: httpx2.AsyncClient | None
    anthropic_client: anthropic.AsyncAnthropic | None


def build_services(settings: Settings) -> Services:
    client = httpx2.AsyncClient(timeout=REQUEST_TIMEOUT_SECONDS)
    claude_client = build_anthropic_client(settings)
    return Services(
        stt=build_speech_to_text(settings, client),
        llm=build_chat_model(settings, client, claude_client),
        tts=build_text_to_speech(settings, client),
        catalogue=build_catalogue(settings, client),
        weather=OpenMeteoWeather(client, settings.weather_url, settings.weather_timeout_seconds),
        http_client=client,
        anthropic_client=claude_client,
    )


# A missing key or URL gives a stand-in that fails each call with a clear message, so the
# gateway still starts, for example when working on the frontend alone.
def build_speech_to_text(settings: Settings, client: httpx2.AsyncClient) -> SpeechToText:
    if settings.groq_api_key is None:
        return MissingSpeechToText()
    return GroqSpeechToText(client, settings.groq_api_key, settings.stt_model)


# Retries are off: on a failure the fallback provider answers at once, which beats
# retrying the same one while the traveller waits.
def build_anthropic_client(settings: Settings) -> anthropic.AsyncAnthropic | None:
    if settings.anthropic_api_key is None:
        return None
    return anthropic.AsyncAnthropic(
        api_key=settings.anthropic_api_key.get_secret_value(), timeout=REQUEST_TIMEOUT_SECONDS, max_retries=0
    )


# Each provider whose key is set takes part; the first in `llm_primary`'s order answers,
# the other steps in when it fails before answering (D-63).
def build_chat_model(
    settings: Settings, client: httpx2.AsyncClient, claude_client: anthropic.AsyncAnthropic | None
) -> ChatModel:
    providers: dict[str, ChatModel] = {}
    if settings.llm_api_key is not None:
        options = GenerationOptions(
            settings.llm_model, settings.llm_temperature, settings.llm_max_tokens, settings.llm_reasoning_effort
        )
        providers["groq"] = OpenAiCompatibleChatModel(client, settings.llm_base_url, settings.llm_api_key, options)
    if claude_client is not None:
        providers["claude"] = ClaudeChatModel(
            claude_client, settings.claude_model, settings.claude_effort, settings.llm_max_tokens
        )
    other = "claude" if settings.llm_primary == "groq" else "groq"
    first, second = providers.get(settings.llm_primary), providers.get(other)
    if first is not None and second is not None:
        return FallbackChatModel(first, second, settings.llm_primary, other)
    return first or second or MissingChatModel()


def build_text_to_speech(settings: Settings, client: httpx2.AsyncClient) -> TextToSpeech:
    if settings.tts_url is None:
        return MissingTextToSpeech()
    tokens = MetadataIdToken(client, settings.tts_url, time.monotonic) if settings.tts_auth == "id_token" else NoToken()
    return HttpTextToSpeech(client, settings.tts_url, tokens)


# SayTech's assistant API is public, so there is no key to be missing.
def build_catalogue(settings: Settings, client: httpx2.AsyncClient) -> Catalogue:
    saytech = SayTechCatalogue(client, settings.saytech_base_url, settings.saytech_timeout_seconds)
    return CachedCatalogue(saytech, time.monotonic, settings.saytech_cache_seconds)
