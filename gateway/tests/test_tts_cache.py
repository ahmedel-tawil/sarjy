import asyncio
import logging

import pytest
from sarjy_gateway.tts import TextToSpeechError
from sarjy_gateway.tts_cache import CachedTextToSpeech

from gateway.tests.fakes import FakeTextToSpeech, SpeechRequest


# FakeTextToSpeech answers b"RIFF" + the text, so a clip is four bytes longer than its words.
def clip_size(text: str) -> int:
    return len(b"RIFF" + text.encode())


def test_the_same_words_in_the_same_voice_are_made_once() -> None:
    tts = FakeTextToSpeech()
    cache = CachedTextToSpeech(tts, max_bytes=1_000)

    first = asyncio.run(cache.synthesize("Hello.", "af_heart"))
    second = asyncio.run(cache.synthesize("Hello.", "af_heart"))

    assert first == second == b"RIFFHello."
    assert tts.requests == [SpeechRequest("Hello.", "af_heart")]
    assert (cache.hits, cache.misses) == (1, 1)


@pytest.mark.parametrize(
    ("max_bytes", "second_voice"),
    [(1_000, "am_adam"), (5, "af_heart")],
    ids=["another voice is another clip", "a clip bigger than the cache is not kept"],
)
def test_the_second_request_is_made_again(max_bytes: int, second_voice: str) -> None:
    tts = FakeTextToSpeech()
    cache = CachedTextToSpeech(tts, max_bytes=max_bytes)

    asyncio.run(cache.synthesize("Hello.", "af_heart"))
    asyncio.run(cache.synthesize("Hello.", second_voice))

    assert len(tts.requests) == 2


def test_the_least_recently_used_clip_goes_first() -> None:
    tts = FakeTextToSpeech()
    cache = CachedTextToSpeech(tts, max_bytes=clip_size("One.") + clip_size("Two."))

    async def say(*texts: str) -> None:
        for text in texts:
            await cache.synthesize(text, None)

    # "One." is used again after "Two.", so "Two." is the one that makes room for "Six."
    asyncio.run(say("One.", "Two.", "One.", "Six.", "One.", "Two."))

    assert [request.text for request in tts.requests] == ["One.", "Two.", "Six.", "Two."]


def test_warmed_phrases_are_hits_in_the_default_voice() -> None:
    tts = FakeTextToSpeech()
    cache = CachedTextToSpeech(tts, max_bytes=1_000)

    asyncio.run(cache.warm(["Anything else?"]))
    asyncio.run(cache.synthesize("Anything else?", None))

    assert tts.requests == [SpeechRequest("Anything else?", None)]
    assert cache.hits == 1


def test_warming_stops_quietly_when_tts_is_down(caplog: pytest.LogCaptureFixture) -> None:
    cache = CachedTextToSpeech(FakeTextToSpeech(error=TextToSpeechError("TTS answered HTTP 503")), max_bytes=1_000)

    with caplog.at_level(logging.INFO, logger="sarjy_gateway.tts_cache"):
        asyncio.run(cache.warm(["Anything else?", "Thanks."]))

    assert caplog.messages == ["tts cache warming stopped: TTS answered HTTP 503"]


def test_the_voice_list_comes_from_tts() -> None:
    tts = FakeTextToSpeech()

    voices = asyncio.run(CachedTextToSpeech(tts, max_bytes=1_000).voices())

    assert (voices.default, tts.voice_lists) == ("af_heart", 1)
