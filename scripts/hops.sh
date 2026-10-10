#!/usr/bin/env bash
# Times the network hop from wherever it runs to each place a turn reaches (M3.11): the TCP
# connect after the DNS lookup (one round trip to the nearest server), the TLS handshake
# after it, and the wait for the first byte of a small answer after that; each the median
# of five fresh connections, in milliseconds. The gcp-* targets are gcping's ping
# services, one per Google Cloud region, which stand in for a gateway deployed there.
#   scripts/hops.sh                                    # from this machine
#   gcloud builds submit scripts --region=me-central1 --config=docs/latency/hops/cloudbuild.yaml
set -euo pipefail

targets=(
  "groq https://api.groq.com/openai/v1/models"
  "anthropic https://api.anthropic.com/v1/models"
  "saytech https://magicexperience.api.saytech.ae/api/v1/public/assistant/context/"
  "open-meteo https://api.open-meteo.com/v1/forecast?latitude=25.2&longitude=55.3&daily=temperature_2m_max"
  "gateway https://gateway-fvbd3h4ngq-ww.a.run.app/health"
  "gcp-me-central1 https://me-central1-5tkroniexa-ww.a.run.app/api/ping"
  "gcp-me-central2 https://me-central2-5tkroniexa-wx.a.run.app/api/ping"
  "gcp-europe-west1 https://europe-west1-5tkroniexa-ew.a.run.app/api/ping"
  "gcp-us-east1 https://us-east1-5tkroniexa-ue.a.run.app/api/ping"
  "gcp-us-central1 https://us-central1-5tkroniexa-uc.a.run.app/api/ping"
)

# The middle of five values, one per line.
median() {
  sort -n | sed -n '3p'
}

printf '%-18s %8s %8s %8s\n' target connect tls first_byte
for target in "${targets[@]}"; do
  read -r name url <<<"$target"
  samples=""
  for _ in 1 2 3 4 5; do
    samples+=$(curl --silent --output /dev/null --max-time 10 \
      --write-out '%{time_namelookup} %{time_connect} %{time_appconnect} %{time_starttransfer}' "$url" || true)
    samples+=$'\n'
  done
  # Each step is timed from the start of the request, so each column subtracts the one
  # before it; the medians are taken per step.
  steps=$(awk '{ print $2 - $1, $3 - $2, $4 - $3 }' <<<"$samples")
  connect=$(cut -d' ' -f1 <<<"$steps" | median)
  tls=$(cut -d' ' -f2 <<<"$steps" | median)
  first_byte=$(cut -d' ' -f3 <<<"$steps" | median)
  awk -v name="$name" -v c="$connect" -v t="$tls" -v f="$first_byte" \
    'BEGIN { printf "%-18s %8.0f %8.0f %8.0f\n", name, c * 1000, t * 1000, f * 1000 }'
done
