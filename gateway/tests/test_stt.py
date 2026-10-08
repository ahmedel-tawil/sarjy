import asyncio

import httpx2
from pydantic import SecretStr
import pytest
from sarjy_gateway.stt import (
    GROQ_TRANSCRIPTIONS_URL,
    Container,
    GroqSpeechToText,
    RateLimitedError,
    SpeechToTextError,
    container_of,
)


API_KEY = "test-groq-key"
WEBM_CLIP = b"\x1a\x45\xdf\xa3" + b"opus frames"


def groq_answering(answer: httpx2.Response, seen: list[httpx2.Request]) -> GroqSpeechToText:
    def handler(request: httpx2.Request) -> httpx2.Response:
        seen.append(request)
        return answer

    client = httpx2.AsyncClient(transport=httpx2.MockTransport(handler))
    return GroqSpeechToText(client, SecretStr(API_KEY), "whisper-large-v3-turbo")


def test_uploads_the_clip_with_model_language_and_key() -> None:
    seen: list[httpx2.Request] = []
    stt = groq_answering(httpx2.Response(200, json={"text": " Hello Sarjy. "}), seen)

    text = asyncio.run(stt.transcribe(WEBM_CLIP))

    assert text == "Hello Sarjy."
    (request,) = seen
    assert str(request.url) == GROQ_TRANSCRIPTIONS_URL
    assert request.headers["Authorization"] == f"Bearer {API_KEY}"
    body = request.read()
    assert b'name="model"\r\n\r\nwhisper-large-v3-turbo' in body
    assert b'name="language"\r\n\r\nen' in body
    assert b'filename="turn.webm"' in body
    assert WEBM_CLIP in body


def test_rate_limits_are_reported_as_their_own_error() -> None:
    stt = groq_answering(httpx2.Response(429, json={"error": "slow down"}), [])

    with pytest.raises(RateLimitedError):
        asyncio.run(stt.transcribe(WEBM_CLIP))


@pytest.mark.parametrize(
    "answer",
    [httpx2.Response(500, text="boom"), httpx2.Response(200, text="<html>not json</html>")],
    ids=["server error", "not a transcription"],
)
def test_failures_raise_errors_that_never_contain_the_key(answer: httpx2.Response) -> None:
    stt = groq_answering(answer, [])

    with pytest.raises(SpeechToTextError) as raised:
        asyncio.run(stt.transcribe(WEBM_CLIP))

    assert API_KEY not in str(raised.value)
    assert not isinstance(raised.value, RateLimitedError)


def test_an_unreachable_groq_raises_speech_to_text_error() -> None:
    def refuse(request: httpx2.Request) -> httpx2.Response:
        message = "connection refused"
        raise httpx2.ConnectError(message, request=request)

    client = httpx2.AsyncClient(transport=httpx2.MockTransport(refuse))
    stt = GroqSpeechToText(client, SecretStr(API_KEY), "whisper-large-v3-turbo")

    with pytest.raises(SpeechToTextError, match="ConnectError"):
        asyncio.run(stt.transcribe(WEBM_CLIP))


@pytest.mark.parametrize(
    ("audio", "expected"),
    [
        (WEBM_CLIP, Container("turn.webm", "audio/webm")),
        (b"\x00\x00\x00\x20ftypM4A " + b"aac frames", Container("turn.mp4", "audio/mp4")),
        (b"RIFF\x24\x00\x00\x00WAVEfmt ", Container("turn.wav", "audio/wav")),
        (b"OggS\x00\x02", Container("turn.ogg", "audio/ogg")),
    ],
    ids=["chrome webm", "safari mp4", "wav", "ogg"],
)
def test_recognises_the_container_from_its_first_bytes(audio: bytes, expected: Container) -> None:
    assert container_of(audio) == expected


def test_refuses_audio_it_cannot_recognise() -> None:
    with pytest.raises(SpeechToTextError, match="not WebM, MP4, WAV or Ogg"):
        container_of(b"plain text, not audio")
