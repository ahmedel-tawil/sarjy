from typing import TYPE_CHECKING, Literal


if TYPE_CHECKING:
    from collections.abc import Callable


# The gateway's marks, in turn order (AGENTS.md, D-04). Renaming one means updating
# docs/LATENCY.md too.
type ServerMark = Literal["audio_received", "stt_done", "llm_first_token", "first_sentence_ready", "tts_first_byte"]


# Milliseconds since a turn's first mark, on a monotonic clock that never jumps.
class Timeline:
    def __init__(self, clock: Callable[[], float]) -> None:
        self._clock = clock
        self._start: float | None = None
        self._marks: dict[str, float] = {}

    # `at` is an earlier clock reading, for a moment only known to matter later: the
    # first word of a model round counts as `llm_first_token` only if that round turns
    # out to be the spoken answer rather than a tool call.
    def mark(self, name: ServerMark, at: float | None = None) -> None:
        now = self._clock() if at is None else at
        if self._start is None:
            self._start = now
        self._marks[name] = round((now - self._start) * 1000, 1)

    def has(self, name: ServerMark) -> bool:
        return name in self._marks

    @property
    def marks(self) -> dict[str, float]:
        return dict(self._marks)
