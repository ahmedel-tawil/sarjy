from collections import OrderedDict
import logging
from typing import TYPE_CHECKING

from sarjy_gateway.tts import TextToSpeechError


if TYPE_CHECKING:
    from collections.abc import Sequence

    from sarjy_gateway.tts import TextToSpeech, Voices


logger = logging.getLogger(__name__)

# Sentences Claude said word for word most often in the turns of 9 and 10 Oct, leaving out
# anything personal; warmed in the default voice when the gateway starts (D-97).
WARM_PHRASES = (
    "What would you like to know about Magic Experience?",
    "Would you like child prices for any of these?",
    "Want child prices for any of these?",
    "Thanks for telling me, I'll remember that.",
    "Thanks, I'll remember that.",
    "I've saved your name.",
)


# Audio already made, reused when the same words are said again in the same voice (D-97).
# It lives in the gateway's memory, so a hit skips the hop to TTS as well as the synthesis.
# Speed is always the default, and every deploy starts a new gateway, so a clip never
# outlives the TTS model that made it. The least recently used clips go first once the
# cache holds `max_bytes`.
class CachedTextToSpeech:
    def __init__(self, tts: TextToSpeech, max_bytes: int) -> None:
        self._tts = tts
        self._max_bytes = max_bytes
        self._clips: OrderedDict[tuple[str, str | None], bytes] = OrderedDict()
        self._bytes = 0
        self.hits = 0
        self.misses = 0

    async def voices(self) -> Voices:
        return await self._tts.voices()

    async def synthesize(self, text: str, voice: str | None) -> bytes:
        key = (text, voice)
        wav = self._clips.get(key)
        if wav is not None:
            self._clips.move_to_end(key)
            self.hits += 1
            self._log("hit", text)
            return wav
        wav = await self._tts.synthesize(text, voice)
        self.misses += 1
        self._log("miss", text)
        self._keep(key, wav)
        return wav

    # Fills the cache in the default voice while nobody is waiting. TTS being down stops
    # it quietly: the phrases are then made when first said, as without a cache.
    async def warm(self, phrases: Sequence[str]) -> None:
        for phrase in phrases:
            try:
                self._keep((phrase, None), await self._tts.synthesize(phrase, None))
            except TextToSpeechError as error:
                logger.info("tts cache warming stopped: %(reason)s", {"reason": str(error)})
                return
        logger.info("tts cache warmed with %(clips)s clips", {"clips": len(self._clips), "bytes": self._bytes})

    def _keep(self, key: tuple[str, str | None], wav: bytes) -> None:
        if key in self._clips or len(wav) > self._max_bytes:
            return
        self._clips[key] = wav
        self._bytes += len(wav)
        while self._bytes > self._max_bytes:
            _, oldest = self._clips.popitem(last=False)
            self._bytes -= len(oldest)

    def _log(self, result: str, text: str) -> None:
        logger.info(
            "tts cache %(result)s",
            {"result": result, "chars": len(text), "hits": self.hits, "misses": self.misses, "clips": len(self._clips)},
        )
