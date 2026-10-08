# Build from the repository root: docker build -f tts/Dockerfile .
# Base images are pinned by digest so every build starts from the same bytes.

FROM python:3.14-slim@sha256:f85c5697265c178cc6887276c55fe16cf3d14ca35c3df6a5eab3b360534a55d2 AS models
RUN apt-get update \
    && apt-get install --yes --no-install-recommends curl \
    && rm -rf /var/lib/apt/lists/*
WORKDIR /build
COPY tts/model-files.sha256 tts/
COPY tts/scripts/download-model.sh tts/scripts/
# Only what the service uses: the full-precision model (O-15), the vocabulary and the
# voices listed at GET /voices (D-49). Every file's SHA-256 is checked.
RUN tts/scripts/download-model.sh /models \
    onnx/model.onnx tokenizer.json \
    voices/af_heart.bin voices/af_bella.bin voices/af_sarah.bin voices/am_michael.bin voices/am_adam.bin
# curl creates folders readable by root only; the service runs as a non-root user.
RUN chmod -R a+rX /models

FROM python:3.14-slim@sha256:f85c5697265c178cc6887276c55fe16cf3d14ca35c3df6a5eab3b360534a55d2 AS python-deps
RUN pip install --no-cache-dir uv==0.12.18
ENV UV_COMPILE_BYTECODE=1 UV_LINK_MODE=copy UV_PYTHON_DOWNLOADS=never
WORKDIR /app
# uv needs every workspace member's pyproject.toml to check the lockfile, even though
# only TTS is installed. Dependencies first, so code edits reuse this layer.
COPY pyproject.toml uv.lock ./
COPY gateway/pyproject.toml gateway/
COPY tts/pyproject.toml tts/
RUN uv sync --locked --no-dev --package sarjy-tts --no-install-workspace
COPY tts/src tts/src
RUN uv sync --locked --no-dev --package sarjy-tts --no-editable

FROM python:3.14-slim@sha256:f85c5697265c178cc6887276c55fe16cf3d14ca35c3df6a5eab3b360534a55d2
RUN useradd --create-home --uid 10001 sarjy
WORKDIR /app
COPY --from=python-deps /app/.venv /app/.venv
COPY --from=models /models /app/models
ENV PATH="/app/.venv/bin:$PATH" \
    SARJY_HOST=0.0.0.0 \
    SARJY_MODELS_DIR=/app/models
USER sarjy
CMD ["python", "-m", "sarjy_tts"]
