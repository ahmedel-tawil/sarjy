from fastapi import FastAPI
from fastapi.testclient import TestClient
import pytest
from sarjy_gateway.messages import ServerError
from sarjy_gateway.voice import VoiceRouter


TURN_END = '{"type": "turn_end"}'


def voice_client(max_turn_audio_bytes: int = 1_000) -> TestClient:
    app = FastAPI()
    app.include_router(VoiceRouter(max_turn_audio_bytes).build())
    return TestClient(app)


def test_a_turns_chunks_come_back_as_one_clip() -> None:
    with voice_client().websocket_connect("/ws") as socket:
        socket.send_bytes(b"first ")
        socket.send_bytes(b"second")
        socket.send_text(TURN_END)

        assert socket.receive_bytes() == b"first second"


def test_each_turn_starts_empty() -> None:
    with voice_client().websocket_connect("/ws") as socket:
        socket.send_bytes(b"turn one")
        socket.send_text(TURN_END)
        socket.receive_bytes()
        socket.send_bytes(b"turn two")
        socket.send_text(TURN_END)

        assert socket.receive_bytes() == b"turn two"


@pytest.mark.parametrize(
    ("audio", "control", "expected_code"),
    [
        (b"", TURN_END, "no_audio"),
        (b"x" * 11, TURN_END, "turn_too_long"),
        (b"some audio", '{"type": "dance"}', "invalid_message"),
    ],
    ids=["turn end without audio", "audio over the limit", "unknown control message"],
)
def test_problems_are_reported_as_errors(audio: bytes, control: str, expected_code: str) -> None:
    with voice_client(max_turn_audio_bytes=10).websocket_connect("/ws") as socket:
        if audio:
            socket.send_bytes(audio)
        socket.send_text(control)

        assert ServerError.model_validate_json(socket.receive_text()).code == expected_code


def test_a_turn_after_one_that_was_too_long_works() -> None:
    with voice_client(max_turn_audio_bytes=10).websocket_connect("/ws") as socket:
        socket.send_bytes(b"x" * 11)
        socket.send_text(TURN_END)
        socket.receive_text()
        socket.send_bytes(b"short")
        socket.send_text(TURN_END)

        assert socket.receive_bytes() == b"short"
