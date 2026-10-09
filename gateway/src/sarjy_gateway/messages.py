from datetime import datetime
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


# Deletes every fact Sarjy saved for this browser's user, after the page asked them to
# confirm.
class ForgetMe(BaseModel):
    type: Literal["forget_me"]


class SetVoice(BaseModel):
    type: Literal["set_voice"]
    voice: str


# Speaks again the reply of an earlier turn of this user's (D-92).
class Replay(BaseModel):
    type: Literal["replay"]
    turn_id: Annotated[str, Field(pattern=r"^[0-9a-f]{32}$")]


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


class ClientMessage(
    RootModel[
        Annotated[TurnEnd | TurnCancel | SetVoice | BrowserMarks | ForgetMe | Replay, Field(discriminator="type")]
    ]
):
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
    "forget_failed",
    "too_many_turns",
    "visit_limit",
    "replay_failed",
]


class ServerError(BaseModel):
    type: Literal["error"] = "error"
    code: ErrorCode
    turn_id: str | None = None


class Transcript(BaseModel):
    type: Literal["transcript"] = "transcript"
    turn_id: str
    text: str


# What Sarjy is doing while a tool runs, one per tool call, in order (D-94).
class Activity(BaseModel):
    type: Literal["activity"] = "activity"
    turn_id: str
    text: str


# A tour the reply names, with its page on the Magic Experience website (D-90).
class TourLink(BaseModel):
    name: str
    url: str


class Reply(BaseModel):
    type: Literal["reply"] = "reply"
    turn_id: str
    text: str
    links: list[TourLink] = []


class RememberedFact(BaseModel):
    key: str
    value: str


# Everything Sarjy remembers about the user, sent in full when the visit starts and after
# every change, so the page never has to merge updates.
class Memory(BaseModel):
    type: Literal["memory"] = "memory"
    facts: list[RememberedFact]


class EarlierTurn(BaseModel):
    turn_id: str
    transcript: str
    reply: str


class EarlierVisit(BaseModel):
    started_at: datetime
    turns: list[EarlierTurn]


# The user's last few visits with a question, newest first, sent after the memory list
# when a visit starts (D-92).
class History(BaseModel):
    type: Literal["history"] = "history"
    visits: list[EarlierVisit]


# The last clip of a replay has been sent.
class ReplayDone(BaseModel):
    type: Literal["replay_done"] = "replay_done"
    turn_id: str


# Sent just before each binary WAV frame of the turn, with the words that frame speaks:
# the whole reply, or one sentence when streaming (D-76), so the page can show them as
# they are spoken.
class AudioFollows(BaseModel):
    type: Literal["audio"] = "audio"
    turn_id: str
    text: str


# Server timings for one turn, in milliseconds since `audio_received` on the gateway's
# clock; the browser adds its own two marks on its own clock (D-04).
class TurnMarks(BaseModel):
    type: Literal["marks"] = "marks"
    turn_id: str
    marks: dict[str, float]
