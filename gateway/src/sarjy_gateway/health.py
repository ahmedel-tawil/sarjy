import logging
from typing import TYPE_CHECKING, Literal

from fastapi import APIRouter, Response
from pydantic import BaseModel

from sarjy_gateway.database import DatabaseUnavailableError


if TYPE_CHECKING:
    from sarjy_gateway.database import Database


logger = logging.getLogger(__name__)


class HealthResponse(BaseModel):
    status: Literal["ok"]


class ReadyResponse(BaseModel):
    status: Literal["ready", "unavailable"]
    reason: str | None = None


class HealthRouter:
    def __init__(self, database: Database) -> None:
        self._database = database

    def build(self) -> APIRouter:
        router = APIRouter()

        # Not /healthz: Cloud Run reserves some paths ending in "z".
        @router.get("/health", status_code=200, response_model=HealthResponse)
        async def health() -> HealthResponse:
            return HealthResponse(status="ok")

        # Proves the gateway can reach Postgres. Kept apart from /health, which says only
        # that the process is up: voice turns work without the database.
        @router.get("/ready", status_code=200, response_model=ReadyResponse)
        async def ready(response: Response) -> ReadyResponse:
            try:
                await self._database.ping()
            except DatabaseUnavailableError as error:
                logger.warning("not ready: %(reason)s", {"reason": str(error)})
                response.status_code = 503
                return ReadyResponse(status="unavailable", reason=str(error))
            return ReadyResponse(status="ready")

        return router
