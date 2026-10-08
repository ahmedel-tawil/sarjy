import logging
from typing import Protocol

import espeakng_loader
from phonemizer.backend import EspeakBackend
from phonemizer.backend.espeak.wrapper import EspeakWrapper


# phonemizer warns on every call whose word count changes, which spelling out numbers
# ("250" -> "two hundred fifty") does by design; keep only its errors.
phonemizer_logger = logging.getLogger("sarjy_tts.phonemizer")
phonemizer_logger.setLevel(logging.ERROR)


class PhonemeConverter(Protocol):
    def to_phonemes(self, text: str) -> str: ...


class EspeakPhonemes:
    def __init__(self) -> None:
        # espeakng-loader ships the espeak-ng library and its data, so nothing has to be
        # installed on the machine or in the image.
        EspeakWrapper.set_library(espeakng_loader.get_library_path())
        EspeakWrapper.set_data_path(espeakng_loader.get_data_path())
        self._backend = EspeakBackend(
            language="en-us", preserve_punctuation=True, with_stress=True, logger=phonemizer_logger
        )

    def to_phonemes(self, text: str) -> str:
        return self._backend.phonemize([text], strip=True)[0]
