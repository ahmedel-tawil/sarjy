from typing import TYPE_CHECKING

from fastapi.testclient import TestClient
from sarjy_gateway.app import create_app
from sarjy_gateway.database import DatabaseUnavailableError
from sarjy_gateway.health import HealthResponse, ReadyResponse
from sarjy_gateway.identity import COOKIE_NAME, user_id_from
from sarjy_gateway.llm import MissingChatModel
from sarjy_gateway.services import Services
from sarjy_gateway.settings import Settings
from sarjy_gateway.stt import MissingSpeechToText
from sarjy_gateway.tts import MissingTextToSpeech, TextToSpeech, Voices

from gateway.tests.fakes import FakeCatalogue, FakeConversationStore, FakeDatabase, FakeTextToSpeech, FakeWeather


if TYPE_CHECKING:
    from pathlib import Path


def services_with(tts: TextToSpeech, database: FakeDatabase | None = None) -> Services:
    return Services(
        stt=MissingSpeechToText(),
        llm=MissingChatModel(),
        tts=tts,
        catalogue=FakeCatalogue(),
        weather=FakeWeather(),
        database=database or FakeDatabase(),
        conversations=FakeConversationStore(),
        http_client=None,
        anthropic_client=None,
        database_pool=None,
    )


def test_health_reports_ok() -> None:
    client = TestClient(create_app(Settings(), services_with(MissingTextToSpeech())))

    response = client.get("/health")

    assert response.status_code == 200
    assert HealthResponse.model_validate_json(response.text) == HealthResponse(status="ok")


def test_serves_the_built_frontend_without_hiding_the_api(tmp_path: Path) -> None:
    (tmp_path / "index.html").write_text("<title>Sarjy</title>")
    client = TestClient(create_app(Settings(frontend_dist=tmp_path), services_with(MissingTextToSpeech())))

    page = client.get("/")
    health = client.get("/health")

    assert page.status_code == 200
    assert "<title>Sarjy</title>" in page.text
    assert health.status_code == 200


def test_voices_come_from_the_tts_service() -> None:
    response = TestClient(create_app(Settings(), services_with(FakeTextToSpeech()))).get("/voices")

    assert Voices.model_validate_json(response.text) == Voices(voices=["af_heart", "am_adam"], default="af_heart")


def test_voices_answer_503_when_tts_cannot_be_reached() -> None:
    response = TestClient(create_app(Settings(), services_with(MissingTextToSpeech()))).get("/voices")

    assert response.status_code == 503


def test_ready_when_the_database_answers() -> None:
    response = TestClient(create_app(Settings(), services_with(MissingTextToSpeech()))).get("/ready")

    assert response.status_code == 200
    assert ReadyResponse.model_validate_json(response.text) == ReadyResponse(status="ready")


def test_not_ready_says_why_while_health_stays_ok() -> None:
    database = FakeDatabase(error=DatabaseUnavailableError("database unreachable: PoolTimeout"))
    client = TestClient(create_app(Settings(), services_with(MissingTextToSpeech(), database)))

    ready = client.get("/ready")
    health = client.get("/health")

    assert ready.status_code == 503
    assert ReadyResponse.model_validate_json(ready.text).reason == "database unreachable: PoolTimeout"
    assert health.status_code == 200


def test_a_first_visit_gets_a_lasting_private_identity_cookie() -> None:
    response = TestClient(create_app(Settings(), services_with(MissingTextToSpeech()))).get("/health")

    cookie = response.headers["set-cookie"]
    name, value = cookie.split(";")[0].split("=")
    assert name == COOKIE_NAME
    assert user_id_from(value) is not None
    assert all(part in cookie for part in ("HttpOnly", "Secure", "SameSite=lax", "Max-Age=34560000", "Path=/"))


def client_with_cookie(cookie: str) -> TestClient:
    return TestClient(create_app(Settings(), services_with(MissingTextToSpeech())), cookies={COOKIE_NAME: cookie})


def test_a_valid_identity_cookie_is_kept_and_a_garbled_one_replaced() -> None:
    kept = client_with_cookie("0199c3a4-0000-7000-8000-00000000abcd").get("/health")
    replaced = client_with_cookie("garbled").get("/health")

    assert "set-cookie" not in kept.headers
    assert replaced.headers["set-cookie"].startswith(f"{COOKIE_NAME}=")
