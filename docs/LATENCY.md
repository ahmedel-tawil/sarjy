# Latency

Sarjy's deep dive: time to first audio (TTFA) on every turn, where that time goes, and
the experiments that bring it down. Every number here was measured. Each experiment
changes one thing against the current best configuration, runs the same script, and
records p50 and p95 before and after.

## Marks

Every turn has a `turn_id` (a UUIDv7 in hex) and seven marks (D-04).

| Mark | Clock | Set when |
| --- | --- | --- |
| `speech_end` | browser | the user lets go of the talk button |
| `audio_received` | gateway | the turn's audio is complete and the pipeline starts; the gateway's other marks count from it |
| `stt_done` | gateway | the transcript is back |
| `llm_first_token` | gateway | the first word of the spoken answer arrives, after any tool rounds (D-57) |
| `first_sentence_ready` | gateway | the text TTS speaks first is ready; until sentence streaming (M3.5), the whole reply |
| `tts_first_byte` | gateway | TTS has audio to send; until sentence streaming, the whole WAV |
| `playback_start` | browser | the first sample of the reply plays |

The gateway sends its five in the `marks` message and logs them on the turn's
"completed" line; the browser sends its two in `browser_marks`, from
`performance.now()`. All seven are stored in `turn_timings` under the turn's id; the
browser's only for a turn of the same visit (D-74).

## Gaps

The two clocks are never mixed: stage gaps use the gateway's, TTFA the browser's, and
what TTFA has beyond the gateway's own time is the network and the browser.

| Gap | Computed as | What it holds |
| --- | --- | --- |
| `stt` | `stt_done − audio_received` | Whisper on Groq |
| `llm_first_word` | `llm_first_token − stt_done` | the prompt if it outlasts STT, every tool round, then the first word |
| `first_sentence` | `first_sentence_ready − llm_first_token` | the rest of the text TTS speaks first |
| `tts` | `tts_first_byte − first_sentence_ready` | synthesis and the call to the TTS service |
| `server_total` | `tts_first_byte − audio_received` | everything the gateway does |
| `network_and_browser` | `ttfa − server_total` | the last audio upload, the reply's download, decoding and the start of playback |
| `ttfa` | `playback_start − speech_end` | what the user waits for |

Percentiles use the nearest rank, so every reported number is one that was measured.

## Runs

A labelled run is a JSON Lines file in `docs/latency/runs/`, one turn per line (`run`,
`turn_id`, the gateway's marks and the client's), written by the experiment harness
(M3.3). To summarise one or more runs:

```bash
uv run python gateway/scripts/latency.py docs/latency/runs/baseline.jsonl
```

## Before the deep dive

Measured while building the voice loop, and kept as the earliest points.

- **TTS on a Mac (M1.9b):** a 10-word sentence took 1.08 s over HTTP natively and 2.2 s
  in Docker Desktop; loading and warming the model took 1.8 to 2.1 s.
- **TTS on Cloud Run, 2 vCPU (M1.10):** the same kind of sentence took about 2.5 to 2.8 s
  of synthesis, roughly 2.5 times the Mac.
- **TTS instance size (M2.17, D-70):** timed directly, warm, with about 0.5 s of each
  being the network from the Mac:

  | TTS size | 13-word sentence | 60-word reply (22 s of audio) |
  | --- | --- | --- |
  | 2 vCPU | 3.7 s | 14.0 s |
  | 4 vCPU | 2.7 s | 9.0 s |
  | 8 vCPU | 2.1 s | 6.3 s |

- **Model (D-69):** on tool turns the first word came after about 1.5 s with Groq's Qwen
  and 2.7 to 3.5 s with Claude Haiku; Claude answers first because Qwen didn't save
  facts.
- **Demo scenarios on the deployed URL (M2.14):** the first word after 1.6 to 4.0 s, the
  first TTS byte after 6.5 to 9.9 s, for replies of 10 to 21 s of audio.
