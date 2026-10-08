#!/usr/bin/env bash
# Downloads the Kokoro-82M ONNX files listed in tts/model-files.sha256 from one pinned
# revision of onnx-community/Kokoro-82M-v1.0-ONNX (Apache-2.0), then verifies every
# checksum. Usage, from the repository root: tts/scripts/download-model.sh tts/models
set -euo pipefail

if [[ $# -ne 1 ]]; then
  echo "usage: tts/scripts/download-model.sh <destination>" >&2
  exit 2
fi

destination="$1"
manifest="$(cd "$(dirname "$0")/.." && pwd)/model-files.sha256"
revision="1939ad2a8e416c0acfeecc08a694d14ef25f2231"
base_url="https://huggingface.co/onnx-community/Kokoro-82M-v1.0-ONNX/resolve/${revision}"

while read -r _checksum path; do
  curl --fail --silent --show-error --location --create-dirs \
    --output "${destination}/${path}" "${base_url}/${path}"
done < "${manifest}"

# macOS ships shasum; Debian-based images ship sha256sum.
cd "${destination}"
if command -v sha256sum > /dev/null; then
  sha256sum --check "${manifest}"
else
  shasum --algorithm 256 --check "${manifest}"
fi
