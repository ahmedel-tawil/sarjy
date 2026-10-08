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
image="${region}-docker.pkg.dev/${project}/sarjy/${service}:$(git rev-parse --short=12 HEAD)"

docker build --file "${service}/Dockerfile" --tag "${image}" .
docker push "${image}"
gcloud run services update "${service}" \
  --image="${image}" \
  --region="${region}" \
  --project="${project}" \
  --quiet
