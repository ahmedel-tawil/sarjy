import io
from typing import TYPE_CHECKING, Protocol
import wave

import numpy as np

from sarjy_tts.chunks import split_tokens


if TYPE_CHECKING:
    from collections.abc import Mapping, Sequence

    from numpy.typing import NDArray

    from sarjy_tts.phonemes import PhonemeConverter
    from sarjy_tts.vocabulary import Vocabulary
    from sarjy_tts.voices import Voice


SAMPLE_RATE = 24_000
# The model's context is 512 tokens, and two of them are the pads around the input.
MAX_TOKENS = 510
PAD_ID = 0
CLAUSE_ENDS = ".!?;:,—…"


class InferenceSession(Protocol):
    def run(
        self, output_names: None, input_feed: Mapping[str, NDArray[np.int64] | NDArray[np.float32]]
    ) -> Sequence[object]: ...


class UnknownVoiceError(LookupError):
    pass


class KokoroSynthesizer:
    def __init__(
        self,
        session: InferenceSession,
        phonemes: PhonemeConverter,
        vocabulary: Vocabulary,
        voices: Mapping[str, Voice],
    ) -> None:
        self._session = session
        self._phonemes = phonemes
        self._vocabulary = vocabulary
        self._voices = voices
        self._clause_ends = vocabulary.ids_of(CLAUSE_ENDS)
        self._space = vocabulary.encode(" ")[0]

    @property
    def voice_names(self) -> list[str]:
        return sorted(self._voices)

    def synthesize(self, text: str, voice: str, speed: float = 1.0) -> NDArray[np.float32]:
        if voice not in self._voices:
            raise UnknownVoiceError(voice)
        chosen = self._voices[voice]
        ids = self._vocabulary.encode(self._phonemes.to_phonemes(text))
        # Voice files can hold fewer styles than the model's context allows.
        limit = min(MAX_TOKENS, chosen.max_tokens)
        parts = [self._run(chunk, chosen, speed) for chunk in split_tokens(ids, limit, self._clause_ends, self._space)]
        return np.concatenate(parts) if parts else np.zeros(0, dtype=np.float32)

    def _run(self, ids: list[int], voice: Voice, speed: float) -> NDArray[np.float32]:
        outputs = self._session.run(
            None,
            {
                "input_ids": np.array([[PAD_ID, *ids, PAD_ID]], dtype=np.int64),
                "style": voice.style_for(len(ids)),
                "speed": np.array([speed], dtype=np.float32),
            },
        )
        audio = outputs[0]
        if not isinstance(audio, np.ndarray):
            message = f"expected audio samples from the model, got {type(audio).__name__}"
            raise TypeError(message)
        return audio.astype(np.float32, copy=False).reshape(-1)


# 16-bit PCM is half the size of the model's float32 and plays in every browser.
def to_pcm16(audio: NDArray[np.float32]) -> bytes:
    return (np.clip(audio, -1.0, 1.0) * 32767).astype("<i2").tobytes()


# The WAV header makes the audio self-describing: anyone can decode it without knowing
# the sample rate or format in advance.
def to_wav(audio: NDArray[np.float32]) -> bytes:
    buffer = io.BytesIO()
    with wave.open(buffer, "wb") as file:
        file.setnchannels(1)
        file.setsampwidth(2)
        file.setframerate(SAMPLE_RATE)
        file.writeframes(to_pcm16(audio))
    return buffer.getvalue()
