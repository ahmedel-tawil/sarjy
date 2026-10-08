from typing import Annotated, Literal, Self

from pydantic import BaseModel, Field, FiniteFloat, RootModel, model_validator


# The voice WebSocket carries audio as binary frames and control messages as JSON text
# frames. frontend/src/lib/protocol.ts mirrors these models; change both together.


class TurnEnd(BaseModel):
    type: Literal["turn_end"]


# Drops the audio sent so far: the browser heard no speech in it, and Whisper would have
# turned the silence into words such as "Thank you." (D-55).
class TurnCancel(BaseModel):
    type: Literal["turn_cancel"]


class SetVoice(BaseModel):
    type: Literal["set_voice"]
    voice: str


# The browser's two marks for one turn, in milliseconds from `performance.now()` on its
# own clock, sent once Sarjy's audio starts playing (D-04).
class BrowserMarks(BaseModel):
    type: Literal["browser_marks"]
    turn_id: Annotated[str, Field(pattern=r"^[0-9a-f]{32}$")]
    speech_end: FiniteFloat
    playback_start: FiniteFloat

    @model_validator(mode="after")
    def playback_follows_speech(self) -> Self:
        if self.playback_start < self.speech_end:
            msg = "playback_start is before speech_end"
            raise ValueError(msg)
        return self

    @property
    def ttfa_ms(self) -> float:
        return round(self.playback_start - self.speech_end, 1)


class ClientMessage(RootModel[Annotated[TurnEnd | TurnCancel | SetVoice | BrowserMarks, Field(discriminator="type")]]):
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
