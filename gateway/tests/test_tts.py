import asyncio

import httpx2
from pydantic import BaseModel
import pytest
from sarjy_gateway.tts import (
    TOKEN_REUSE_SECONDS,
    HttpTextToSpeech,
    MetadataIdToken,
    NoToken,
    TextToSpeechError,
    Voices,
)


TTS_URL = "https://tts.example"


class SynthesisBody(BaseModel):
    text: str
    voice: str


def fake_google(seen: list[httpx2.Request], tts_answer: httpx2.Response) -> httpx2.AsyncClient:
    def handler(request: httpx2.Request) -> httpx2.Response:
        seen.append(request)
        if request.url.host == "metadata.google.internal":
            return httpx2.Response(200, text="signed-token")
        return tts_answer

    return httpx2.AsyncClient(transport=httpx2.MockTransport(handler))


def test_synthesize_sends_text_and_voice_with_the_services_identity_token() -> None:
    seen: list[httpx2.Request] = []
    client = fake_google(seen, httpx2.Response(200, content=b"RIFF-wav-bytes"))
    tts = HttpTextToSpeech(client, TTS_URL, MetadataIdToken(client, TTS_URL, lambda: 0.0))

    audio = asyncio.run(tts.synthesize("Hello", "af_heart"))

    assert audio == b"RIFF-wav-bytes"
    metadata, synthesis = seen
    assert metadata.headers["Metadata-Flavor"] == "Google"
    assert metadata.url.params["audience"] == TTS_URL
    assert str(synthesis.url) == f"{TTS_URL}/synthesize"
    assert synthesis.headers["Authorization"] == "Bearer signed-token"
    assert SynthesisBody.model_validate_json(synthesis.content) == SynthesisBody(text="Hello", voice="af_heart")


def test_voices_are_read_from_the_tts_service() -> None:
    answer = httpx2.Response(200, json={"voices": ["af_heart", "am_adam"], "default": "af_heart"})
    tts = HttpTextToSpeech(fake_google([], answer), TTS_URL, NoToken())

    assert asyncio.run(tts.voices()) == Voices(voices=["af_heart", "am_adam"], default="af_heart")


def test_the_identity_token_is_reused_until_it_is_close_to_expiry() -> None:
    seen: list[httpx2.Request] = []
    now = [0.0]

    def clock() -> float:
        return now[0]

    tokens = MetadataIdToken(fake_google(seen, httpx2.Response(204)), TTS_URL, clock)

    asyncio.run(tokens.token())
    now[0] = TOKEN_REUSE_SECONDS - 1
    asyncio.run(tokens.token())
    fetches_before_expiry = len(seen)
    now[0] = TOKEN_REUSE_SECONDS + 1
    asyncio.run(tokens.token())

    assert fetches_before_expiry == 1
    assert len(seen) == 2


@pytest.mark.parametrize(
    "answer",
    [httpx2.Response(500, text="model crashed"), httpx2.Response(403, text="forbidden")],
    ids=["tts error", "token refused"],
)
def test_failed_calls_raise_text_to_speech_error(answer: httpx2.Response) -> None:
    tts = HttpTextToSpeech(fake_google([], answer), TTS_URL, NoToken())

    with pytest.raises(TextToSpeechError, match="POST /synthesize failed"):
        asyncio.run(tts.synthesize("Hello", "af_heart"))


def test_a_voice_list_that_is_not_json_raises_text_to_speech_error() -> None:
    answer = httpx2.Response(200, text="<html>Congratulations | Cloud Run</html>")
    tts = HttpTextToSpeech(fake_google([], answer), TTS_URL, NoToken())

    with pytest.raises(TextToSpeechError, match="something other than a voice list"):
        asyncio.run(tts.voices())


def test_an_unreachable_service_raises_text_to_speech_error() -> None:
    def refuse(request: httpx2.Request) -> httpx2.Response:
        message = "connection refused"
        raise httpx2.ConnectError(message, request=request)

    tts = HttpTextToSpeech(httpx2.AsyncClient(transport=httpx2.MockTransport(refuse)), TTS_URL, NoToken())

    with pytest.raises(TextToSpeechError, match="GET /voices failed"):
        asyncio.run(tts.voices())
