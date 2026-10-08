# Build from the repository root: docker build -f gateway/Dockerfile .
# Base images are pinned by digest so every build starts from the same bytes.

FROM node:24-slim@sha256:d6aa754f16b3197301076f047b5def2f02ea1dbbc2ca920407d46d7ec7f87b20 AS frontend
WORKDIR /build/frontend
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci --no-audit --no-fund --ignore-scripts
COPY frontend/ ./
RUN npm run build

FROM python:3.14-slim@sha256:f85c5697265c178cc6887276c55fe16cf3d14ca35c3df6a5eab3b360534a55d2 AS python-deps
RUN pip install --no-cache-dir uv==0.12.18
ENV UV_COMPILE_BYTECODE=1 UV_LINK_MODE=copy UV_PYTHON_DOWNLOADS=never
WORKDIR /app
# uv needs every workspace member's pyproject.toml to check the lockfile, even though
# only the gateway is installed. Dependencies first, so code edits reuse this layer.
COPY pyproject.toml uv.lock ./
COPY gateway/pyproject.toml gateway/
COPY tts/pyproject.toml tts/
RUN uv sync --locked --no-dev --package sarjy-gateway --no-install-workspace
COPY gateway/src gateway/src
RUN uv sync --locked --no-dev --package sarjy-gateway --no-editable

FROM python:3.14-slim@sha256:f85c5697265c178cc6887276c55fe16cf3d14ca35c3df6a5eab3b360534a55d2
RUN useradd --create-home --uid 10001 sarjy
WORKDIR /app
COPY --from=python-deps /app/.venv /app/.venv
COPY --from=frontend /build/frontend/dist /app/frontend
ENV PATH="/app/.venv/bin:$PATH" \
    SARJY_HOST=0.0.0.0 \
    SARJY_FRONTEND_DIST=/app/frontend
USER sarjy
CMD ["python", "-m", "sarjy_gateway"]
