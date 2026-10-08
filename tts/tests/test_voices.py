import numpy as np
import pytest
from sarjy_tts.voices import STYLE_SIZE, Voice


def voice_with_rows(rows: int) -> Voice:
    return Voice(np.repeat(np.arange(rows, dtype=np.float32), STYLE_SIZE))


def test_picks_the_style_row_for_the_token_count() -> None:
    style = voice_with_rows(510).style_for(42)

    assert np.array_equal(style, np.full((1, STYLE_SIZE), 42, dtype=np.float32))


def test_a_510_row_voice_covers_up_to_509_tokens() -> None:
    assert voice_with_rows(510).max_tokens == 509


@pytest.mark.parametrize("token_count", [0, 510], ids=["no tokens", "past the last row"])
def test_rejects_token_counts_without_a_style(token_count: int) -> None:
    with pytest.raises(ValueError, match="styles for 1 to 509 tokens"):
        voice_with_rows(510).style_for(token_count)
