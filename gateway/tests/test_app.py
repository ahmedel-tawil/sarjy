from typing import TYPE_CHECKING

from fastapi.testclient import TestClient
from sarjy_gateway.app import create_app
from sarjy_gateway.health import HealthResponse
from sarjy_gateway.settings import Settings
from sarjy_gateway.tts import MissingTextToSpeech, Voices


if TYPE_CHECKING:
    from pathlib import Path


def test_health_reports_ok() -> None:
    client = TestClient(create_app(Settings(), MissingTextToSpeech()))

    response = client.get("/health")

    assert response.status_code == 200
    assert HealthResponse.model_validate_json(response.text) == HealthResponse(status="ok")


def test_serves_the_built_frontend_without_hiding_the_api(tmp_path: Path) -> None:
    (tmp_path / "index.html").write_text("<title>Sarjy</title>")
    client = TestClient(create_app(Settings(frontend_dist=tmp_path), MissingTextToSpeech()))

    page = client.get("/")
    health = client.get("/health")

    assert page.status_code == 200
    assert "<title>Sarjy</title>" in page.text
    assert health.status_code == 200


def test_voices_come_from_the_tts_service() -> None:
    class ListingTextToSpeech(MissingTextToSpeech):
        async def voices(self) -> Voices:
            return Voices(voices=["af_heart", "am_adam"], default="af_heart")

    response = TestClient(create_app(Settings(), ListingTextToSpeech())).get("/voices")

    assert Voices.model_validate_json(response.text) == Voices(voices=["af_heart", "am_adam"], default="af_heart")


def test_voices_answer_503_when_tts_cannot_be_reached() -> None:
    response = TestClient(create_app(Settings(), MissingTextToSpeech())).get("/voices")

    assert response.status_code == 503
