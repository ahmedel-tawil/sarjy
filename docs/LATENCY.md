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
| `llm_first_token` | gateway | the first word that is spoken arrives: after any tool rounds (D-57), or in `sentence` mode a filler the model writes before a tool, which is spoken while the tool runs (D-76) |
| `first_sentence_ready` | gateway | the text TTS speaks first is ready: in `baseline` mode the whole reply, in `sentence` mode the first complete sentence (D-76) |
| `tts_first_byte` | gateway | TTS has audio to send: in `baseline` mode the whole WAV, in `sentence` mode the first sentence's |
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
the script's `clip`, `turn_id`, the gateway's marks and the client's), written by the experiment harness
(D-74, D-75). To summarise one or more runs:

```bash
uv run python gateway/scripts/latency.py docs/latency/runs/baseline.jsonl
```

### The script and the harness

The script is ten questions in `docs/latency/script/`: the four demo scenarios, the
general "what can I do in Dubai?", a name, a weather-only question and a short "thanks",
so tool turns and quick turns are both in every run. Each is a WAV spoken by Kokoro's
`am_michael` voice, which makes every run hear exactly the same audio.

The harness plays the whole script in one visit, as many times as asked, each visit with a
fresh identity that forgets its facts at the end, and records the run:

```bash
uv run python gateway/scripts/harness.py https://gateway-fvbd3h4ngq-ww.a.run.app baseline 3
```

It stands in for the browser, with these differences:

- **`speech_end`:** the harness streams each clip at the pace it was spoken, as the
  browser does while the button is held, and marks `speech_end` when the clip ends,
  just before `turn_end`. The browser marks it on release, when its recorder still has
  one last chunk to hand over, so the browser's TTFA includes a little more upload.
- **`playback_start`:** the harness takes the first byte of the reply's audio. The
  browser starts playing after decoding the WAV and scheduling it, typically tens of
  milliseconds later, so the harness's TTFA is slightly shorter.
- **Audio format:** the script is WAV at 24 kHz, about 48 KB per second of speech; Chrome
  sends WebM with Opus, roughly a tenth of that. The gateway uploads more to Groq, so
  `stt` is slightly longer than a browser's.
- **Network:** the harness runs from the same laptop and connection as a browser would,
  and reports the gateway's own marks unchanged.

## Experiment 1: baseline

The voice loop as it stands on 9 Oct, before any latency work: Groq's
`whisper-large-v3-turbo`; Claude Haiku 5.5 first with Groq's Qwen as fallback (D-69),
prompt v1.1; Kokoro on Cloud Run with 8 vCPU (D-70); the gateway on 1 vCPU; all in
`me-central1`. The whole reply is synthesised as one WAV before any of it is sent. The
harness played the script three times from the laptop, 11:59 to 12:06 UTC, after one
request to each service, so the instances were warm. All 30 turns finished and every
question was transcribed correctly. Run: `docs/latency/runs/baseline.jsonl`.

| Gap | p50 | p95 |
| --- | --- | --- |
| `stt` | 731 ms | 897 ms |
| `llm_first_word` | 2,276 ms | 3,570 ms |
| `first_sentence` | 375 ms | 534 ms |
| `tts` | 3,478 ms | 5,879 ms |
| `server_total` | 7,287 ms | 10,116 ms |
| `network_and_browser` | 496 ms | 970 ms |
| **`ttfa`** | **7,894 ms** | **10,674 ms** |

### Where the time goes

Shares of the mean TTFA (7.4 s):

| Gap | Mean | Share |
| --- | --- | --- |
| `tts` | 3.6 s | 48% |
| `llm_first_word` | 2.2 s | 30% |
| `stt` | 0.75 s | 10% |
| `network_and_browser` | 0.5 s | 7% |
| `first_sentence` | 0.36 s | 5% |

Medians per question, over the three passes:

| Question | TTFA | LLM to first word | TTS |
| --- | --- | --- | --- |
| 01 kids under 400 in Abu Dhabi | 9.8 s | 2.5 s | 5.2 s |
| 02 colour and heights (two saves) | 7.9 s | 2.7 s | 3.5 s |
| 03 what's my colour (no tool) | 3.0 s | 1.0 s | 0.8 s |
| 04 Dubai this weekend | 8.9 s | 2.3 s | 4.9 s |
| 05 safari tomorrow (search and forecast) | 10.4 s | 3.5 s | 4.3 s |
| 06 buggy price | 6.4 s | 1.9 s | 2.8 s |
| 07 what can I do in Dubai | 8.0 s | 1.8 s | 4.6 s |
| 08 my name (one save) | 5.5 s | 2.3 s | 1.6 s |
| 09 Abu Dhabi weather on Saturday | 9.0 s | 3.4 s | 4.1 s |
| 10 thanks (no tool) | 4.0 s | 1.0 s | 1.5 s |

- **TTS is half the wait, and it grows with the reply.** A one-line answer takes 0.8 s to
  synthesise and a three-tour answer about 5 s, because the whole reply is synthesised
  before the first sound. The third pass's "what's my colour" got a longer answer, and
  its TTS took 6.2 s instead of 0.8 s.
- **Each tool round costs about a second.** With no tool, Claude's first word arrives in
  about 1.0 s; with one round, 1.8 to 2.5 s; with a search and a forecast, about 3.5 s.
- **Speech to text and the network are small and steady,** about 0.75 s and 0.5 s.

### Targets

Set from these numbers, for the experiments that follow:

| Experiment | Target |
| --- | --- |
| 2, sentence streaming (M3.6) | `tts` p50 under 1.5 s whatever the reply's length; TTFA p50 under 5 s and p95 under 7 s |
| 3, TTS cache (M3.7) | a cached sentence's `tts` under 100 ms, with the hit rate on the script reported |
| 4, model choice (M3.8) | `llm_first_word` p50 down by at least 0.5 s, only with a model that still saves facts (D-69) |
| 5, tool payload size (M3.9) | `llm_first_word` on tool turns down by at least 10% |
| 6, warm vs cold (M3.10) | the first turn after an idle period measured with no warm instance and with one, and its cost |

## Experiment 2: sentence streaming

One change against the baseline: `SARJY_PIPELINE_MODE=sentence` (D-76, D-77). Each
sentence goes to TTS as soon as the model has written it, and the page plays the clips
back to back. Everything else as in the baseline, including the prompt's new "tools
first" rule, which came with this mode. Same script, three passes, from the laptop, 12:46
to 12:53 UTC on 9 Oct, after a warm-up (TTS had scaled to zero; its first request took
7.8 s). All 30 turns finished and every question was transcribed correctly. Run:
`docs/latency/runs/sentence-streaming.jsonl`.

| Gap | Baseline p50 | Sentence p50 | Baseline p95 | Sentence p95 |
| --- | --- | --- | --- | --- |
| `stt` | 731 ms | 742 ms | 897 ms | 913 ms |
| `llm_first_word` | 2,276 ms | 1,010 ms | 3,570 ms | 2,789 ms |
| `first_sentence` | 375 ms | 224 ms | 534 ms | 659 ms |
| `tts` | 3,478 ms | 810 ms | 5,879 ms | 2,662 ms |
| `server_total` | 7,287 ms | 3,119 ms | 10,116 ms | 6,102 ms |
| `network_and_browser` | 496 ms | 230 ms | 970 ms | 625 ms |
| **`ttfa`** | **7,894 ms** | **3,369 ms** | **10,674 ms** | **6,548 ms** |

TTFA fell by 57% at p50 and 39% at p95. All three targets are met: `tts` p50 under 1.5 s,
TTFA p50 under 5 s and p95 under 7 s.

### Where the gain comes from

Medians per question, before and after:

| Question | TTFA | LLM to first word | TTS |
| --- | --- | --- | --- |
| 01 kids under 400 in Abu Dhabi | 9.8 → 4.7 s | 2.5 → 2.4 s | 5.2 → 1.1 s |
| 02 colour and heights | 7.9 → 2.9 s | 2.7 → 1.0 s | 3.5 → 0.7 s |
| 03 what's my colour (no tool) | 3.0 → 2.8 s | 1.0 → 1.0 s | 0.8 → 0.7 s |
| 04 Dubai this weekend | 8.8 → 3.4 s | 2.3 → 1.1 s | 4.9 → 0.9 s |
| 05 safari tomorrow | 10.4 → 3.6 s | 3.5 → 1.0 s | 4.3 → 1.0 s |
| 06 buggy price | 6.4 → 3.2 s | 1.9 → 0.9 s | 2.8 → 1.0 s |
| 07 what can I do in Dubai | 8.0 → 3.2 s | 1.8 → 1.1 s | 4.6 → 0.8 s |
| 08 my name | 5.5 → 3.8 s | 2.3 → 2.2 s | 1.6 → 0.6 s |
| 09 Abu Dhabi weather on Saturday | 9.0 → 5.6 s | 3.4 → 2.7 s | 4.1 → 1.5 s |
| 10 thanks (no tool) | 4.0 → 2.8 s | 1.0 → 1.0 s | 1.5 → 0.6 s |

- **Streaming TTS is the main gain.** TTS now covers one sentence, 0.6 to 1.5 s whatever
  the reply's length, against 0.8 to 5.2 s for the whole reply. Questions 01, 08 and 09
  kept their tool rounds before the first word (2.2 to 2.7 s) and still lost 1.7 to 5.1 s
  of TTFA from this alone.
- **Fillers before a tool add to it.** In questions 02 and 04 to 07, the first word now
  comes after about a second, as with no tool at all: the model said a short sentence
  such as "I'll check tomorrow's weather" before calling its tool, which plays while the
  tool runs (D-76). For those, TTFA counts the filler, which is what the user hears
  first; the answer itself starts about 1 to 2.5 s later, as the old tool rounds show.
- **The wait is now spread out.** Shares of the mean TTFA (3.9 s): `llm_first_word` 37%,
  `tts` 27%, `stt` 20%, `network_and_browser` 8%, `first_sentence` 8%. The model and its
  tool rounds are now the largest part; experiments 4 and 5 address them.

## Experiment 6: warm vs cold

Both services scale to zero unless told otherwise (D-78). The first turn after a quiet
spell was measured on 9 Oct with the script's first question, kids under 400 dirhams in
Abu Dhabi, whose warm median is 4.7 s (experiment 2). One pass of the script each.

| First turn after a quiet spell | TTFA | `tts` | Run |
| --- | --- | --- | --- |
| TTS cold, gateway warm, no wake-up | 11.8 s | 7.5 s | `cold-tts.jsonl` |
| TTS cold, gateway warm, with the wake-up (D-78) | 5.2 s | 1.0 s | `cold-tts-woken.jsonl` |
| One warm instance of each, after 16 idle minutes | 5.9 s | 1.3 s | `warm-after-idle.jsonl` |

- **A cold TTS costs about 6 s.** Its instance needs 2.4 s to start the container and 3.3
  to 3.5 s to load and warm the model before it can synthesise.
- **Waking TTS when a visit opens hides it.** In the second run, the wake-up's request
  started the instance at 14:24:11.6 and it was ready at 14:24:17.7; the first sentence
  reached TTS at 14:24:21.9, after the question had been spoken, transcribed and
  answered, and took 1.0 s.
- **A cold gateway delays the page, not the turn.** Every gateway start on 9 Oct took 7
  to 10 s from instance start to serving, 8.8 s of it before the server process starts.
  The page itself waits that long, before any turn; TTFA starts after the question, so
  the harness can't see it, and the logs measure it instead.
- **Warm instances remove both.** After the apply no new instance started, and the first
  turn after 16 idle minutes met a warm TTS; its TTFA is within this question's warm
  spread (its first word took 2.7 s that turn).
- **Cost:** idle, a minimum instance is billed at Tier 2's idle rate, about $0.0000035 per
  vCPU-second and per GiB-second: about $0.45 a day for the gateway and $3.60 for TTS,
  roughly $28 for a review week or $123 a month.

The review week runs with one warm instance of each, set back to 0 afterwards; the
wake-up stays as the safety net when nothing is warm.

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
