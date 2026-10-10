from pydantic import ValidationError
import pytest
from sarjy_gateway.settings import Settings


def test_port_comes_from_cloud_runs_port_variable(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("PORT", "9000")

    assert Settings().port == 9000


@pytest.mark.parametrize(
    ("variable", "value"),
    [("SARJY_LOG_LEVEL", "LOUD"), ("SARJY_FRONTEND_DIST", "/no/such/folder")],
    ids=["unknown log level", "missing frontend folder"],
)
def test_invalid_setting_fails_at_startup(monkeypatch: pytest.MonkeyPatch, variable: str, value: str) -> None:
    monkeypatch.setenv(variable, value)

    with pytest.raises(ValidationError):
        Settings()


# A .env copied from .env.example leaves the names it doesn't fill empty.
def test_an_empty_setting_keeps_its_default(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SARJY_TTS_AUTH", "")
    monkeypatch.setenv("SARJY_PIPELINE_MODE", "")

    settings = Settings()

    assert (settings.tts_auth, settings.pipeline_mode) == ("none", "sentence")
