import pytest
from sarjy_tts.chunks import split_tokens


SPACE = 16
COMMA = 3
CLAUSE_ENDS = frozenset({COMMA})


@pytest.mark.parametrize(
    ("ids", "limit", "expected"),
    [
        ([1, 2, 3], 5, [[1, 2, 3]]),
        ([1, 2, COMMA, SPACE, 4, 5, SPACE, 6], 6, [[1, 2, COMMA], [4, 5, SPACE, 6]]),
        ([1, 2, SPACE, 4, 5, SPACE, 6, 7], 6, [[1, 2, SPACE, 4, 5], [6, 7]]),
        ([1, 2, 3, 4, 5, 6, 7], 3, [[1, 2, 3], [4, 5, 6], [7]]),
        ([], 5, []),
    ],
    ids=[
        "short input stays whole",
        "cuts after the last clause end that fits",
        "falls back to the last space that fits",
        "cuts at the limit only when there is no space",
        "empty input gives no chunks",
    ],
)
def test_split_tokens(ids: list[int], limit: int, expected: list[list[int]]) -> None:
    assert split_tokens(ids, limit, CLAUSE_ENDS, SPACE) == expected


def test_no_chunk_is_longer_than_the_limit() -> None:
    words = [1, 2, 3, SPACE] * 300

    chunks = split_tokens(words, 510, CLAUSE_ENDS, SPACE)

    assert all(len(chunk) <= 510 for chunk in chunks)
    assert sum(len(chunk) for chunk in chunks) >= len(words) - len(chunks)
