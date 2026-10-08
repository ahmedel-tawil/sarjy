from typing import Literal

from pydantic import BaseModel


# The voice WebSocket carries audio as binary frames and control messages as JSON text
# frames. frontend/src/lib/protocol.ts mirrors these models; change both together.


class TurnEnd(BaseModel):
    type: Literal["turn_end"]


class ServerError(BaseModel):
    type: Literal["error"] = "error"
    code: Literal["invalid_message", "no_audio", "turn_too_long"]
