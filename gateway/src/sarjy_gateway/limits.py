from collections import deque
from typing import TYPE_CHECKING


if TYPE_CHECKING:
    from collections.abc import Callable

    from sarjy_gateway.identity import UserId


# A bot that changes its cookie on every turn leaves keys behind that never come back;
# past this many, keys with no turn inside the window are dropped.
MAX_KEYS = 10_000


# Counts each key's turns over the last `window_seconds`, in this process only: with at
# most two gateway instances, a visitor whose tabs land on both gets at most twice the
# limit (D-72).
class SlidingWindow:
    def __init__(self, limit: int, window_seconds: float, clock: Callable[[], float], *, max_keys: int) -> None:
        self._limit = limit
        self._window_seconds = window_seconds
        self._clock = clock
        self._max_keys = max_keys
        self._turns: dict[str, deque[float]] = {}

    def __len__(self) -> int:
        return len(self._turns)

    def has_room(self, key: str) -> bool:
        turns = self._turns.get(key)
        if turns is None:
            return True
        cutoff = self._clock() - self._window_seconds
        while turns and turns[0] <= cutoff:
            turns.popleft()
        return len(turns) < self._limit

    def record(self, key: str) -> None:
        if key not in self._turns and len(self._turns) >= self._max_keys:
            self._forget_idle_keys()
        self._turns.setdefault(key, deque()).append(self._clock())

    def _forget_idle_keys(self) -> None:
        cutoff = self._clock() - self._window_seconds
        self._turns = {key: turns for key, turns in self._turns.items() if turns and turns[-1] > cutoff}


# New turns are limited per user and per IP, so a bot can't escape the user limit by
# clearing its cookie (D-21, D-72).
class TurnLimits:
    def __init__(self, per_user: SlidingWindow, per_ip: SlidingWindow) -> None:
        self._per_user = per_user
        self._per_ip = per_ip

    # Counts the turn only when both have room, so a refused turn uses up neither limit.
    def allow(self, user_id: UserId, ip: str) -> bool:
        user = str(user_id)
        if not (self._per_user.has_room(user) and self._per_ip.has_room(ip)):
            return False
        self._per_user.record(user)
        self._per_ip.record(ip)
        return True


# Cloud Run's front end appends the address it received the request from, so the last
# entry of X-Forwarded-For is the visitor; earlier entries come from the client and can be
# forged. Locally there is no proxy, and the socket's peer is the visitor (D-72).
def client_ip(forwarded_for: str | None, peer: str | None) -> str:
    if forwarded_for:
        return forwarded_for.rsplit(",", 1)[-1].strip()
    return peer or "unknown"
