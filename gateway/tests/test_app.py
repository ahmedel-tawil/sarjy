from typing import TYPE_CHECKING

from fastapi.testclient import TestClient
from sarjy_gateway.app import create_app
from sarjy_gateway.health import HealthResponse
from sarjy_gateway.settings import Settings


if TYPE_CHECKING:
    from pathlib import Path


def test_health_reports_ok() -> None:
    client = TestClient(create_app(Settings()))

    response = client.get("/health")

    assert response.status_code == 200
    assert HealthResponse.model_validate_json(response.text) == HealthResponse(status="ok")


def test_serves_the_built_frontend_without_hiding_the_api(tmp_path: Path) -> None:
    (tmp_path / "index.html").write_text("<title>Sarjy</title>")
    client = TestClient(create_app(Settings(frontend_dist=tmp_path)))

    page = client.get("/")
    health = client.get("/health")

    assert page.status_code == 200
    assert "<title>Sarjy</title>" in page.text
    assert health.status_code == 200
