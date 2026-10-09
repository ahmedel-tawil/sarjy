import pytest
from sarjy_gateway.identity import new_user_id
from sarjy_gateway.limits import MAX_KEYS, SlidingWindow, TurnLimits, client_ip

from gateway.tests.fakes import ManualClock


def turn_limits(clock: ManualClock, *, per_user: int = 2, per_ip: int = 3) -> TurnLimits:
    return TurnLimits(
        per_user=SlidingWindow(per_user, 60, clock, max_keys=MAX_KEYS),
        per_ip=SlidingWindow(per_ip, 60, clock, max_keys=MAX_KEYS),
    )


def test_a_user_gets_their_turns_then_waits_for_the_window() -> None:
    clock = ManualClock()
    limits = turn_limits(clock)
    user = new_user_id()

    first = [limits.allow(user, "203.0.113.7") for _ in range(3)]
    clock.now = 59.0
    almost = limits.allow(user, "203.0.113.7")
    clock.now = 60.0
    after = limits.allow(user, "203.0.113.7")

    assert first == [True, True, False]
    assert (almost, after) == (False, True)


def test_a_new_cookie_does_not_escape_the_ip_limit() -> None:
    limits = turn_limits(ManualClock())

    allowed = [limits.allow(new_user_id(), "203.0.113.7") for _ in range(4)]

    assert allowed == [True, True, True, False]


def test_a_refused_turn_uses_up_neither_limit() -> None:
    limits = turn_limits(ManualClock())
    busy, quiet = new_user_id(), new_user_id()
    for _ in range(2):
        limits.allow(busy, "203.0.113.7")
    limits.allow(quiet, "203.0.113.7")

    refused_by_ip = limits.allow(quiet, "203.0.113.7")
    # From elsewhere the quiet user still has its second turn: the refusal didn't count.
    elsewhere = [limits.allow(quiet, "198.51.100.9") for _ in range(2)]

    assert refused_by_ip is False
    assert elsewhere == [True, False]


def test_keys_idle_for_a_whole_window_are_dropped_when_there_are_too_many() -> None:
    clock = ManualClock()
    window = SlidingWindow(5, 60, clock, max_keys=2)
    window.record("a")
    window.record("b")
    clock.now = 61.0

    window.record("c")

    assert len(window) == 1


@pytest.mark.parametrize(
    ("forwarded_for", "peer", "expected"),
    [
        ("203.0.113.7", "169.254.1.1", "203.0.113.7"),
        ("6.6.6.6, 203.0.113.7", "169.254.1.1", "203.0.113.7"),
        (None, "127.0.0.1", "127.0.0.1"),
        (None, None, "unknown"),
    ],
    ids=["cloud run", "a forged entry before cloud run's", "local, no proxy", "no address at all"],
)
def test_the_visitor_is_the_last_forwarded_address_or_the_peer(
    forwarded_for: str | None, peer: str | None, expected: str
) -> None:
    assert client_ip(forwarded_for, peer) == expected
