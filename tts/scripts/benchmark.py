# Times the real Kokoro model the way it will run on Cloud Run and writes voice samples.
# Run from the repository root after tts/scripts/download-model.sh tts/models:
#     uv run python tts/scripts/benchmark.py
# Apple silicon is faster than Cloud Run's CPUs, so treat these numbers as a lower bound.

import logging
from pathlib import Path
import statistics
import time

from sarjy_tts.loading import load_synthesizer
from sarjy_tts.synthesizer import SAMPLE_RATE, to_wav


MODELS_DIR = Path("tts/models")
SAMPLES_DIR = MODELS_DIR / "samples"
SENTENCE = "The desert safari starts at three in the afternoon and costs two hundred and fifty dirhams."
PRICE_SENTENCE = "Your tour is AED 1,250 on 12 October at 4:30 PM."
MODELS = ("model.onnx", "model_quantized.onnx")
# None means every core; 2 and 1 imitate Cloud Run instances with 2 or 1 vCPU.
THREADS = (None, 2, 1)
RUNS = 3

logger = logging.getLogger("benchmark")


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    logger.info("%-22s %-7s %10s %12s %8s", "model", "threads", "load s", "synth ms", "RTF")
    for model in MODELS:
        for threads in THREADS:
            time_model(model, threads)
    write_voice_samples()


def time_model(model: str, threads: int | None) -> None:
    started = time.perf_counter()
    synthesizer = load_synthesizer(MODELS_DIR, model, threads)
    load_seconds = time.perf_counter() - started
    # The first call warms onnxruntime up; only the calls after it are timed.
    audio = synthesizer.synthesize(SENTENCE, "af_heart")
    timings: list[float] = []
    for _ in range(RUNS):
        started = time.perf_counter()
        audio = synthesizer.synthesize(SENTENCE, "af_heart")
        timings.append(time.perf_counter() - started)
    synth_seconds = statistics.median(timings)
    real_time_factor = synth_seconds / (len(audio) / SAMPLE_RATE)
    logger.info(
        "%-22s %-7s %10.2f %12.0f %8.2f", model, threads or "all", load_seconds, synth_seconds * 1000, real_time_factor
    )


def write_voice_samples() -> None:
    synthesizer = load_synthesizer(MODELS_DIR, "model.onnx")
    SAMPLES_DIR.mkdir(exist_ok=True)
    for voice in synthesizer.voice_names:
        path = SAMPLES_DIR / f"{voice}.wav"
        path.write_bytes(to_wav(synthesizer.synthesize(f"{SENTENCE} {PRICE_SENTENCE}", voice)))
        logger.info("wrote %s", path)


if __name__ == "__main__":
    main()
