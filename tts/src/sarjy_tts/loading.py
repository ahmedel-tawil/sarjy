from typing import TYPE_CHECKING

import onnxruntime

from sarjy_tts.phonemes import EspeakPhonemes
from sarjy_tts.synthesizer import KokoroSynthesizer
from sarjy_tts.vocabulary import Vocabulary
from sarjy_tts.voices import Voice


if TYPE_CHECKING:
    from pathlib import Path


# Expects the layout tts/scripts/download-model.sh creates: onnx/, voices/, tokenizer.json.
def load_synthesizer(model_dir: Path, model_file: str, threads: int | None = None) -> KokoroSynthesizer:
    options = onnxruntime.SessionOptions()
    if threads is not None:
        options.intra_op_num_threads = threads
    # CPU only, even where faster providers exist, so local numbers match Cloud Run.
    session = onnxruntime.InferenceSession(
        str(model_dir / "onnx" / model_file), sess_options=options, providers=["CPUExecutionProvider"]
    )
    voices = {path.stem: Voice.load(path) for path in sorted((model_dir / "voices").glob("*.bin"))}
    vocabulary = Vocabulary.from_tokenizer_file(model_dir / "tokenizer.json")
    return KokoroSynthesizer(session, EspeakPhonemes(), vocabulary, voices)
