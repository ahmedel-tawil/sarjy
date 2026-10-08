import logging
from typing import TYPE_CHECKING, Self

from pydantic import BaseModel


if TYPE_CHECKING:
    from collections.abc import Mapping
    from pathlib import Path


logger = logging.getLogger(__name__)


class TokenizerModel(BaseModel):
    vocab: dict[str, int]


class TokenizerFile(BaseModel):
    model: TokenizerModel


# Kokoro reads one token per phoneme symbol, numbered as in the model's tokenizer.json.
class Vocabulary:
    def __init__(self, ids: Mapping[str, int]) -> None:
        self._ids = dict(ids)

    @classmethod
    def from_tokenizer_file(cls, path: Path) -> Self:
        return cls(TokenizerFile.model_validate_json(path.read_text(encoding="utf-8")).model.vocab)

    def encode(self, phonemes: str) -> list[int]:
        unknown = {symbol for symbol in phonemes if symbol not in self._ids}
        if unknown:
            logger.warning("dropped phonemes the model does not know: %s", "".join(sorted(unknown)))
        return [self._ids[symbol] for symbol in phonemes if symbol in self._ids]

    def ids_of(self, symbols: str) -> frozenset[int]:
        return frozenset(self._ids[symbol] for symbol in symbols if symbol in self._ids)
