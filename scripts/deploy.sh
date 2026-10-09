#!/usr/bin/env bash
# Builds one service's image, pushes it to Artifact Registry and points the Cloud Run
# service at it. Only the image changes; Terraform owns every other setting.
# Run from the repository root: scripts/deploy.sh gateway
set -euo pipefail

if [[ $# -ne 1 ]]; then
  echo "usage: scripts/deploy.sh <gateway|tts>" >&2
  exit 2
fi

service="$1"
project="sarjy-ahmed-2026"
region="me-central1"

# The gateway is tagged with its commit and deploys on every merge. TTS is a 420 MB image
# that rarely changes, so its tag is a fingerprint of every file it is built from: the
# same files give the same tag, and an image already deployed is not built again (D-73).
if [[ "${service}" == "tts" ]]; then
  fingerprint="$(git ls-tree -r HEAD -- tts pyproject.toml uv.lock gateway/pyproject.toml .dockerignore | git hash-object --stdin)"
  tag="inputs-${fingerprint:0:12}"
else
  tag="$(git rev-parse --short=12 HEAD)"
fi
image="${region}-docker.pkg.dev/${project}/sarjy/${service}:${tag}"

# Nothing to do when the last deploy of this image succeeded: its newest revision is
# the one serving.
read -r ready created running < <(gcloud run services describe "${service}" \
  --region="${region}" \
  --project="${project}" \
  --format='value(status.latestReadyRevisionName,status.latestCreatedRevisionName,spec.template.spec.containers[0].image)')
if [[ "${running}" == "${image}" && "${ready}" == "${created}" ]]; then
  echo "${service} already runs ${image}; nothing to deploy"
  exit 0
fi

if gcloud artifacts docker images describe "${image}" --quiet >/dev/null 2>&1; then
  echo "${image} is already in the registry; deploying it without a rebuild"
else
  docker build --file "${service}/Dockerfile" --tag "${image}" .
  docker push "${image}"
fi
gcloud run services update "${service}" \
  --image="${image}" \
  --region="${region}" \
  --project="${project}" \
  --quiet
