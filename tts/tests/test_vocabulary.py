import logging
from typing import TYPE_CHECKING

from sarjy_tts.vocabulary import Vocabulary


if TYPE_CHECKING:
    from pathlib import Path

    import pytest


def test_reads_the_vocabulary_from_a_tokenizer_file(tmp_path: Path) -> None:
    tokenizer = tmp_path / "tokenizer.json"
    tokenizer.write_text('{"version": "1.0", "model": {"vocab": {"$": 0, "a": 43, "b": 44}}}')

    assert Vocabulary.from_tokenizer_file(tokenizer).encode("ab") == [43, 44]


def test_drops_and_logs_symbols_the_model_does_not_know(caplog: pytest.LogCaptureFixture) -> None:
    vocabulary = Vocabulary({"h": 50, "i": 51})

    with caplog.at_level(logging.WARNING):
        ids = vocabulary.encode("hi😀")

    assert ids == [50, 51]
    assert "😀" in caplog.text
