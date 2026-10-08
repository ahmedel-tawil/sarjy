from dataclasses import dataclass
import io
from typing import TYPE_CHECKING
import wave

from fastapi.testclient import TestClient
import numpy as np
import pytest
from sarjy_tts.api import VoicesResponse
from sarjy_tts.app import create_app
from sarjy_tts.health import HealthResponse
from sarjy_tts.settings import Settings


if TYPE_CHECKING:
    from numpy.typing import NDArray


@dataclass(frozen=True)
class SynthesisCall:
    text: str
    voice: str
    speed: float


@dataclass(frozen=True)
class Harness:
    client: TestClient
    calls: list[SynthesisCall]


def make_harness() -> Harness:
    calls: list[SynthesisCall] = []

    class FakeSynthesizer:
        @property
        def voice_names(self) -> list[str]:
            return ["af_heart", "am_adam"]

        def synthesize(self, text: str, voice: str, speed: float = 1.0) -> NDArray[np.float32]:
            calls.append(SynthesisCall(text, voice, speed))
            return np.zeros(2_400, dtype=np.float32)

    settings = Settings(default_voice="af_heart", max_text_chars=20)
    return Harness(TestClient(create_app(FakeSynthesizer(), settings)), calls)


def test_synthesize_returns_a_24_khz_mono_16_bit_wav() -> None:
    harness = make_harness()

    response = harness.client.post("/synthesize", json={"text": "Hello", "voice": "am_adam", "speed": 1.1})

    assert response.status_code == 200
    assert response.headers["content-type"] == "audio/wav"
    with wave.open(io.BytesIO(response.content), "rb") as audio:
        assert (audio.getframerate(), audio.getnchannels(), audio.getsampwidth()) == (24_000, 1, 2)
        assert audio.getnframes() == 2_400
    assert harness.calls == [SynthesisCall("Hello", "am_adam", 1.1)]


def test_the_default_voice_is_used_when_none_is_given() -> None:
    harness = make_harness()

    harness.client.post("/synthesize", json={"text": "Hello"})

    assert harness.calls[0].voice == "af_heart"


@pytest.mark.parametrize(
    "body",
    [
        {"text": ""},
        {"text": "x" * 21},
        {"text": "Hello", "voice": "nobody"},
        {"text": "Hello", "speed": 3.0},
    ],
    ids=["empty text", "text over the limit", "unknown voice", "speed out of range"],
)
def test_bad_requests_are_refused_without_synthesizing(body: dict[str, str | float]) -> None:
    harness = make_harness()

    response = harness.client.post("/synthesize", json=body)

    assert response.status_code == 422
    assert harness.calls == []


def test_voices_lists_the_voices_and_the_default() -> None:
    response = make_harness().client.get("/voices")

    assert VoicesResponse.model_validate_json(response.text) == VoicesResponse(
        voices=["af_heart", "am_adam"], default="af_heart"
    )


def test_health_reports_ok() -> None:
    response = make_harness().client.get("/health")

    assert HealthResponse.model_validate_json(response.text) == HealthResponse(status="ok")
