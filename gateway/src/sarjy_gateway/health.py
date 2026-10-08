from typing import Literal

from fastapi import APIRouter
from pydantic import BaseModel


class HealthResponse(BaseModel):
    status: Literal["ok"]


class HealthRouter:
    def build(self) -> APIRouter:
        router = APIRouter()

        # Not /healthz: Cloud Run reserves some paths ending in "z".
        @router.get("/health", status_code=200, response_model=HealthResponse)
        async def health() -> HealthResponse:
            return HealthResponse(status="ok")

        return router
