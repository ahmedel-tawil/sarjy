from typing import TYPE_CHECKING


if TYPE_CHECKING:
    from collections.abc import Sequence


# Cuts after the last clause end that fits, else at the last space, so a chunk never
# ends mid-word and pauses fall where a speaker would pause anyway.
def split_tokens(ids: Sequence[int], limit: int, clause_ends: frozenset[int], space: int) -> list[list[int]]:
    chunks: list[list[int]] = []
    rest = list(ids)
    while len(rest) > limit:
        cut = _cut_point(rest[:limit], clause_ends, space)
        chunks.append(rest[:cut])
        rest = rest[cut:]
        while rest and rest[0] == space:
            rest = rest[1:]
    if rest:
        chunks.append(rest)
    return chunks


def _cut_point(window: Sequence[int], clause_ends: frozenset[int], space: int) -> int:
    clause_end = _last_index(window, clause_ends)
    if clause_end > 0:
        return clause_end + 1
    word_gap = _last_index(window, frozenset({space}))
    if word_gap > 0:
        return word_gap
    # No clause end or space at all: only possible for input that is not prose.
    return len(window)


# Returns 0 when nothing matches: a cut at position 0 would make an empty chunk.
def _last_index(ids: Sequence[int], wanted: frozenset[int]) -> int:
    for index in range(len(ids) - 1, 0, -1):
        if ids[index] in wanted:
            return index
    return 0
