from dataclasses import dataclass
from typing import TYPE_CHECKING

import numpy as np
import pytest
from sarjy_tts.synthesizer import MAX_TOKENS, PAD_ID, KokoroSynthesizer, UnknownVoiceError, to_pcm16
from sarjy_tts.vocabulary import Vocabulary
from sarjy_tts.voices import STYLE_SIZE, Voice


if TYPE_CHECKING:
    from collections.abc import Mapping, Sequence

    from numpy.typing import NDArray


VOCABULARY = Vocabulary({"$": PAD_ID, ",": 3, " ": 16, "a": 43, "b": 44})


type Feed = Mapping[str, NDArray[np.int64] | NDArray[np.float32]]


@dataclass(frozen=True)
class Harness:
    synthesizer: KokoroSynthesizer
    calls: list[Feed]


def make_harness(phonemes: str) -> Harness:
    calls: list[Feed] = []

    class FixedPhonemes:
        def to_phonemes(self, text: str) -> str:
            return phonemes if text else ""

    # Stands in for onnxruntime: records each call and returns one sample per token.
    class RecordingSession:
        def run(self, output_names: None, input_feed: Feed) -> Sequence[object]:
            assert output_names is None
            calls.append(input_feed)
            return [np.ones((1, input_feed["input_ids"].shape[1]), dtype=np.float32)]

    # Real voice files have 510 rows, so the longest usable chunk is 509 tokens.
    styles = np.repeat(np.arange(MAX_TOKENS, dtype=np.float32), STYLE_SIZE)
    synthesizer = KokoroSynthesizer(RecordingSession(), FixedPhonemes(), VOCABULARY, {"af_test": Voice(styles)})
    return Harness(synthesizer, calls)


def test_feeds_the_model_padded_ids_the_matching_style_and_speed() -> None:
    harness = make_harness("ab ba")

    harness.synthesizer.synthesize("hello", "af_test", speed=1.2)

    (call,) = harness.calls
    assert call["input_ids"].tolist() == [[PAD_ID, 43, 44, 16, 44, 43, PAD_ID]]
    assert call["input_ids"].dtype == np.int64
    assert np.array_equal(call["style"], np.full((1, STYLE_SIZE), 5, dtype=np.float32))
    assert call["speed"].tolist() == pytest.approx([1.2])


def test_long_input_runs_the_model_per_chunk_and_joins_the_audio() -> None:
    harness = make_harness(("ab" * 200 + ", ") * 3)

    audio = harness.synthesizer.synthesize("long text", "af_test")

    assert len(harness.calls) > 1
    assert all(call["input_ids"].shape[1] <= MAX_TOKENS - 1 + 2 for call in harness.calls)
    assert len(audio) == sum(call["input_ids"].shape[1] for call in harness.calls)


def test_empty_text_gives_empty_audio_without_running_the_model() -> None:
    harness = make_harness("")

    audio = harness.synthesizer.synthesize("", "af_test")

    assert len(audio) == 0
    assert harness.calls == []


def test_unknown_voice_is_refused() -> None:
    with pytest.raises(UnknownVoiceError):
        make_harness("ab").synthesizer.synthesize("hello", "nobody")


def test_pcm16_scales_and_clips_to_16_bit() -> None:
    audio = np.array([0.0, 0.5, -1.0, 2.0], dtype=np.float32)

    samples = np.frombuffer(to_pcm16(audio), dtype="<i2")

    assert samples.tolist() == [0, 16383, -32767, 32767]
