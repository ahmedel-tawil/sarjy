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
