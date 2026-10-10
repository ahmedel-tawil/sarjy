# Cost per conversation

What one conversation costs Sarjy to run, from measured usage and list prices on 10 Oct
2026 (M5.1). A conversation here is the test script: ten spoken questions in one visit,
four of them with tools, the facts saved, about five minutes with a traveller.

## Measured usage

One pass of the script through the current code (`docs/latency/runs/cost-check-local.jsonl`,
gateway logs for the tokens):

| | Per conversation |
| --- | --- |
| Questions | 10, about 3 to 5 seconds of speech each |
| Model rounds (Claude Haiku 5.5) | 15 |
| Input tokens read fresh | 31,149 |
| Input tokens read from the cache | 59,130 (3,942 shared tokens a round, D-93) |
| Output tokens | 1,360 |
| Characters spoken | 1,840 |

## Variable cost

| Part | How it's billed | Per conversation |
| --- | --- | --- |
| Speech to text (Groq Whisper turbo) | $0.04 an hour of audio, at least 10 seconds a request | $0.0011 |
| Language model (Claude Haiku 5.5) | $0.10 per million input tokens, $0.01 cached, $0.50 output | $0.0044 |
| Text to speech (our Kokoro on Cloud Run) | 8 vCPU and 4 GiB while synthesising, about 37 seconds at 20 ms a character (D-70) | $0.0105 |
| Gateway (Cloud Run) | 1 vCPU and 0.5 GiB while the visit's socket is open, 5 minutes | $0.0106 at most |
| SayTech and Open-Meteo | Free | $0 |
| **Total** | | **about $0.027, or 10 fils** |

- **Prompt caching halves the model's bill.** Without it the same conversation would cost
  $0.0097 in tokens instead of $0.0044.
- **The gateway figure is a ceiling.** Cloud Run bills an instance, not a visit: while
  several visits share one instance, they share its seconds.
- Cloud Run's rates are Doha's (`me-central1`, Tier 2) from the Cloud Billing catalogue:
  $0.0000336 per vCPU-second and $0.0000035 per GiB-second while serving a request.

## Fixed cost

| Part | Cost |
| --- | --- |
| Cloud SQL, `db-f1-micro` with 10 GB | about $11.40 a month |
| A warm TTS instance (8 vCPU, 4 GiB idle, D-78) | about $3.63 a day |
| A warm gateway instance (1 vCPU, 0.5 GiB idle) | about $0.45 a day |
| Artifact Registry, five images per service | cents a month |

Both services keep one warm instance for the review week, about $28 in all, then go back
to scaling to zero, where idle costs nothing and the first turn after a quiet spell waits
for TTS to start (experiment 6).

## Self-hosted TTS against a per-character bill

The same 1,840 characters from hosted voices, at their list prices:

| Voice | Price | Per conversation |
| --- | --- | --- |
| Our Kokoro on Cloud Run | compute while synthesising | $0.0105 |
| OpenAI `tts-1` | $15 per million characters | $0.028 |
| OpenAI `tts-1-hd` | $30 per million characters | $0.055 |
| ElevenLabs Flash | $0.05 per thousand characters | $0.092 |

- **Per conversation, our own voice is the cheapest.** It is a third of `tts-1` and a ninth
  of ElevenLabs Flash.
- **Keeping it warm is the real cost.** A warm TTS instance costs $3.63 a day whether
  anyone talks or not. It pays for itself against ElevenLabs Flash from about 44
  conversations a day, and against `tts-1` from about 200. Below that, scaling to zero
  with the wake-up (D-78) is cheaper, at the price of a slower first turn.
- **Speed and control decided it, not price** (D-38, D-70): our TTS streams sentence by
  sentence from the same region, and the TTS cache (D-97) serves repeats for free.

Third-party TTS prices are from public pricing summaries of June to September 2026 and
should be checked before budgeting; Groq's and Anthropic's are their published list
prices; Google Cloud's are from its billing catalogue for Doha.
