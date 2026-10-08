#!/usr/bin/env bash
# Downloads Kokoro-82M ONNX files listed in tts/model-files.sha256 from one pinned
# revision of onnx-community/Kokoro-82M-v1.0-ONNX (Apache-2.0), then verifies every
# checksum. With no file arguments it fetches the whole list; the Dockerfile names only
# the files the image needs.
# Usage, from the repository root: tts/scripts/download-model.sh <destination> [file ...]
set -euo pipefail

if [[ $# -lt 1 ]]; then
  echo "usage: tts/scripts/download-model.sh <destination> [file ...]" >&2
  exit 2
fi

destination="$1"
shift
manifest="$(cd "$(dirname "$0")/.." && pwd)/model-files.sha256"
revision="1939ad2a8e416c0acfeecc08a694d14ef25f2231"
base_url="https://huggingface.co/onnx-community/Kokoro-82M-v1.0-ONNX/resolve/${revision}"

selected="$(mktemp)"
trap 'rm -f "${selected}"' EXIT
if [[ $# -eq 0 ]]; then
  cp "${manifest}" "${selected}"
else
  for wanted in "$@"; do
    line="$(awk -v path="${wanted}" '$2 == path' "${manifest}")"
    if [[ -z "${line}" ]]; then
      echo "not in tts/model-files.sha256: ${wanted}" >&2
      exit 1
    fi
    echo "${line}" >> "${selected}"
  done
fi

while read -r _checksum path; do
  curl --fail --silent --show-error --location --create-dirs \
    --output "${destination}/${path}" "${base_url}/${path}"
done < "${selected}"

# macOS ships shasum; Debian-based images ship sha256sum.
cd "${destination}"
if command -v sha256sum > /dev/null; then
  sha256sum --check "${selected}"
else
  shasum --algorithm 256 --check "${selected}"
fi
