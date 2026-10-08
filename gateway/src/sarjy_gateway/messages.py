from typing import Annotated, Literal

from pydantic import BaseModel, Field, RootModel


# The voice WebSocket carries audio as binary frames and control messages as JSON text
# frames. frontend/src/lib/protocol.ts mirrors these models; change both together.


class TurnEnd(BaseModel):
    type: Literal["turn_end"]


class SetVoice(BaseModel):
    type: Literal["set_voice"]
    voice: str


class ClientMessage(RootModel[Annotated[TurnEnd | SetVoice, Field(discriminator="type")]]):
    pass


type ErrorCode = Literal[
    "invalid_message",
    "no_audio",
    "turn_too_long",
    "unknown_voice",
    "no_speech",
    "rate_limited",
    "stt_failed",
    "llm_failed",
    "tts_failed",
]


class ServerError(BaseModel):
    type: Literal["error"] = "error"
    code: ErrorCode
    turn_id: str | None = None


class Transcript(BaseModel):
    type: Literal["transcript"] = "transcript"
    turn_id: str
    text: str


class Reply(BaseModel):
    type: Literal["reply"] = "reply"
    turn_id: str
    text: str


# Sent just before the binary WAV frame of the same turn.
class AudioFollows(BaseModel):
    type: Literal["audio"] = "audio"
    turn_id: str


# Server timings for one turn, in milliseconds since `audio_received` on the gateway's
# clock; the browser adds its own two marks on its own clock (D-04).
class TurnMarks(BaseModel):
    type: Literal["marks"] = "marks"
    turn_id: str
    marks: dict[str, float]
