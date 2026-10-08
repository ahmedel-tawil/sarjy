from typing import TYPE_CHECKING, Self

import numpy as np


if TYPE_CHECKING:
    from pathlib import Path

    from numpy.typing import NDArray


STYLE_SIZE = 256


# A voice file holds one style vector per input length; Kokoro picks it by token count.
class Voice:
    def __init__(self, styles: NDArray[np.float32]) -> None:
        self._styles = styles.reshape(-1, STYLE_SIZE)

    @classmethod
    def load(cls, path: Path) -> Self:
        return cls(np.fromfile(path, dtype=np.float32))

    @property
    def max_tokens(self) -> int:
        return len(self._styles) - 1

    def style_for(self, token_count: int) -> NDArray[np.float32]:
        if not 0 < token_count <= self.max_tokens:
            message = f"this voice has styles for 1 to {self.max_tokens} tokens, not {token_count}"
            raise ValueError(message)
        # A one-row slice keeps the (1, 256) shape the model expects.
        return self._styles[token_count : token_count + 1]
