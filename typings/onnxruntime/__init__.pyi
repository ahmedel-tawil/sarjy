# onnxruntime's compiled module ships without type information, so strict type checking
# cannot see into it. This declares only the parts the TTS service uses.
from collections.abc import Mapping, Sequence

import numpy as np
from numpy.typing import NDArray

class SessionOptions:
    intra_op_num_threads: int
    def __init__(self) -> None: ...

class InferenceSession:
    def __init__(
        self,
        path_or_bytes: str,
        sess_options: SessionOptions | None = None,
        providers: Sequence[str] | None = None,
    ) -> None: ...
    def run(
        self,
        output_names: Sequence[str] | None,
        input_feed: Mapping[str, NDArray[np.int64] | NDArray[np.float32]],
    ) -> list[object]: ...
