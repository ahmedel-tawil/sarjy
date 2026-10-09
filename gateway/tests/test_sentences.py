import pytest
from sarjy_gateway.sentences import SentenceChunker, speakable


def chunk(*pieces: str) -> list[str]:
    chunker = SentenceChunker()
    sentences: list[str] = []
    for piece in pieces:
        sentences += chunker.add(piece)
    return sentences + chunker.flush()


@pytest.mark.parametrize(
    ("pieces", "expected"),
    [
        (
            ("The Aquarium is from 209 dirhams. The Museum", " of the Future is from 169."),
            ["The Aquarium is from 209 dirhams.", "The Museum of the Future is from 169."],
        ),
        (
            ("A private tour costs AED 1,250.50 for the group. Children go free."),
            ["A private tour costs AED 1,250.50 for the group.", "Children go free."],
        ),
        (
            ("It is 3", ".", "5 kilometres from the hotel. Then you arrive."),
            ["It is 3.5 kilometres from the hotel.", "Then you arrive."],
        ),
        (
            ("Bring water, e.g. two bottles each. Ask Dr. Amal at the desk."),
            ["Bring water, e.g. two bottles each.", "Ask Dr. Amal at the desk."],
        ),
        (
            ("Prices are in U.S. dollars on the site. Pay in dirhams here."),
            ["Prices are in U.S. dollars on the site.", "Pay in dirhams here."],
        ),
        (
            ("Hmm... let me think about the evening. The heat drops after six."),
            ["Hmm... let me think about the evening.", "The heat drops after six."],
        ),
        (
            ("Sure. The safari leaves at four. Okay!"),
            ["Sure. The safari leaves at four.", "Okay!"],
        ),
        (
            ('She said "book early." It fills up by noon.'),
            ['She said "book early."', "It fills up by noon."],
        ),
        (
            ("Two good options:\n", "the Louvre and Qasr Al Watan"),
            ["Two good options:", "the Louvre and Qasr Al Watan"],
        ),
    ],
    ids=[
        "split across pieces",
        "a price with a decimal",
        "a decimal arriving in pieces",
        "abbreviations",
        "initials",
        "an ellipsis",
        "very short fragments join the next",
        "a closing quote stays with its sentence",
        "a line break ends a sentence, the rest is flushed",
    ],
)
def test_streamed_text_becomes_speakable_sentences(pieces: tuple[str, ...] | str, expected: list[str]) -> None:
    assert chunk(*((pieces,) if isinstance(pieces, str) else pieces)) == expected


def test_a_full_stop_at_the_end_of_a_piece_waits_for_the_next() -> None:
    chunker = SentenceChunker()

    held = chunker.add("The tour costs 3.")
    completed = chunker.add(" It runs daily.")

    assert held == []
    assert completed == ["The tour costs 3."]
    assert chunker.flush() == ["It runs daily."]


@pytest.mark.parametrize(
    ("written", "spoken"),
    [
        ("**The Louvre** costs _70_ dirhams.", "The Louvre costs 70 dirhams."),
        ("1. Ferrari World, from 345.", "Ferrari World, from 345."),
        ("- Qasr Al Watan", "Qasr Al Watan"),
    ],
    ids=["emphasis", "a numbered item", "a bullet"],
)
def test_markdown_and_list_markers_are_not_spoken(written: str, spoken: str) -> None:
    assert speakable(written) == spoken
