# 8. Measuring latency

Latency is Sarjy's deep dive ([D-02](../DECISIONS.md#d-02-the-deep-dive-is-latency)). The metric is time to first audio (TTFA): from the
moment the traveller lets go of the orb to the moment the first sample of the answer plays
in the browser ([D-03](../DECISIONS.md#d-03-the-metric-is-time-to-first-audio-ttfa)). It is what a caller actually feels. Every turn is measured, every
turn's timings are stored, the page shows them live, and every TTFA and gap table in
[`docs/LATENCY.md`](../LATENCY.md) comes from a run file in the repository that anyone can
summarise again. A few figures, such as start-up times and network hops, come from logs
and Cloud Build output instead. This chapter shows how.

## The seven marks

Each turn has a `turn_id` and seven marks ([D-04](../DECISIONS.md#d-04-how-latency-is-measured)). Two come from the browser and five from
the gateway.

| Mark | Clock | Set in | When |
| --- | --- | --- | --- |
| `speech_end` | browser | [`voice-session.ts`](../../frontend/src/lib/voice-session.ts#L242) | The traveller lets go |
| `audio_received` | gateway | [`turn.py`](../../gateway/src/sarjy_gateway/turn.py#L241) | The pipeline starts, after `turn_end` and the checks |
| `stt_done` | gateway | [`turn.py`](../../gateway/src/sarjy_gateway/turn.py#L247) | The transcript is back |
| `llm_first_token` | gateway | [`SentenceSpeaker.heard`](../../gateway/src/sarjy_gateway/turn.py#L172), or [`_spoken`](../../gateway/src/sarjy_gateway/turn.py#L396) in the baseline | The first word that will be spoken arrives |
| `first_sentence_ready` | gateway | [`_say`](../../gateway/src/sarjy_gateway/turn.py#L200), or [`run`](../../gateway/src/sarjy_gateway/turn.py#L257) in the baseline | The first text for TTS is ready: a sentence, or the whole reply |
| `tts_first_byte` | gateway | [`_speak_in_order`](../../gateway/src/sarjy_gateway/turn.py#L211), or [`run`](../../gateway/src/sarjy_gateway/turn.py#L260) in the baseline | The first clip is back from TTS |
| `playback_start` | browser | [`voice-session.ts`](../../frontend/src/lib/voice-session.ts#L207) | The first clip starts playing |

`llm_first_token` needs care. In the baseline it is the first word of the round that turns
out to be the answer, after any tool rounds ([D-57](../DECISIONS.md#d-57-the-tool-loop-and-what-llm_first_token-means-with-tools)). Only when the model's last round ends is it
known which round that was, so the clock reading is saved when the word arrives and the mark is
set later with `Timeline.mark(at=...)`. In sentence mode every round's words are spoken,
so it is the first word of any round: when the model writes a short filler before a tool,
that filler is the first word, and also the first audio ([D-76](../DECISIONS.md#d-76-sentence-streaming-every-written-sentence-spoken-in-order-tools-first)).

`AGENTS.md` says a mark is never removed or renamed without updating `docs/LATENCY.md`. The
gateway's five names are a `Literal` type,
[`ServerMark`](../../gateway/src/sarjy_gateway/timeline.py#L10), so the type checker
rejects a misspelt one.

## Two clocks, never mixed

The browser's clock and the gateway's never agree, so a gap is never measured across them
([D-04](../DECISIONS.md#d-04-how-latency-is-measured)). The gateway's marks give the stages; the browser's two give TTFA; whatever TTFA
has beyond the gateway's own time is the network and the browser.

[`Timeline`](../../gateway/src/sarjy_gateway/timeline.py#L14) keeps the gateway's side.
It runs on `time.monotonic`, which never jumps. The first mark sets the start, so every
mark is milliseconds since `audio_received`, rounded to a tenth.
[`has`](../../gateway/src/sarjy_gateway/timeline.py#L29) lets the speaker set a mark only
once. The browser's two are `performance.now()` readings, on its own clock.

[`latency.py`](../../gateway/src/sarjy_gateway/latency.py) turns one turn's marks into gaps,
the same ones `docs/LATENCY.md` defines:

| Gap | Computed as | Clock |
| --- | --- | --- |
| `stt` | `stt_done − audio_received` | gateway |
| `llm_first_word` | `llm_first_token − stt_done` | gateway |
| `first_sentence` | `first_sentence_ready − llm_first_token` | gateway |
| `tts` | `tts_first_byte − first_sentence_ready` | gateway |
| `server_total` | `tts_first_byte − audio_received` | gateway |
| `ttfa` | `playback_start − speech_end` | browser |
| `network_and_browser` | `ttfa − server_total` | a difference of two durations |

`llm_first_word` holds every tool round, so tool time shows up there; each tool also logs
its own duration ([D-57](../DECISIONS.md#d-57-the-tool-loop-and-what-llm_first_token-means-with-tools)). [`percentile`](../../gateway/src/sarjy_gateway/latency.py#L72)
uses the nearest rank, so every p50 and p95 reported is a value that was really measured,
never one interpolated between two ([D-74](../DECISIONS.md#d-74-timings-in-postgres-for-every-turn-runs-as-json-lines-files)).

## Where the marks go

1. When the turn is done, the gateway sends its five in the `marks` message and logs them
   on the "turn completed" line.
2. The router then saves the turn and the five marks in `turn_timings` ([chapter 6](06-memory-and-storage.md)).
3. When the first clip starts playing, the page sends `browser_marks`. The gateway checks
   them (a 32-hex `turn_id`, finite numbers, playback not before speech end), logs the
   turn's TTFA on a "turn played" line, and stores both, only for a turn of the same visit
   ([D-54](../DECISIONS.md#d-54-browser-marks-go-back-over-the-voice-socket-one-turn-at-a-time), [D-74](../DECISIONS.md#d-74-timings-in-postgres-for-every-turn-runs-as-json-lines-files)).
4. The page combines the gateway's marks with its own TTFA into a waterfall of the last
   five turns ([D-79](../DECISIONS.md#d-79-the-waterfall-each-turns-stages-from-both-clocks-in-the-latency-card), [chapter 9](09-page.md)).

So every real visit is measured, not only experiments. A cached first sentence shows up
plainly: `tts_first_byte` lands at almost the same moment as `first_sentence_ready`.

## The scripts behind `docs/LATENCY.md`

Runs are JSON Lines files committed in [`docs/latency/`](../latency/), one turn per line,
so the deep dive's numbers need no access to Cloud SQL ([D-74](../DECISIONS.md#d-74-timings-in-postgres-for-every-turn-runs-as-json-lines-files)).

**[`harness.py`](../../gateway/scripts/harness.py)** stands in for the browser ([D-75](../DECISIONS.md#d-75-a-synthesised-script-played-by-a-harness-that-stands-in-for-the-browser)). It
plays the latency script, ten questions in
[`docs/latency/script/`](../latency/script/) spoken by Kokoro's `am_michael` voice, so every
run hears exactly the same audio. For each repetition it:

- gets an identity cookie from `GET /health`, then opens `/ws` like a page;
- [streams each clip](../../gateway/scripts/harness.py#L68) in chunks of about a third of
  a second, at the pace it was spoken, as a browser does while the orb is held, and marks
  `speech_end` when the clip ends, just before `turn_end`;
- takes `playback_start` at the first byte of the reply's audio, and sends `browser_marks`
  like the page, so the gateway stores and logs the turn as usual;
- waits 2 seconds after each answered question, and forgets its facts at the end of the
  visit.

It writes `docs/latency/runs/<label>.jsonl`, refuses to overwrite an existing run, and
prints p50 and p95 per gap. `docs/LATENCY.md` lists how it differs from a browser: it marks
`speech_end` after its last chunk is sent, where a browser still has one to upload; its
`playback_start` comes before decoding, so slightly early; and it uploads WAV rather than
Opus.

**[`latency.py`](../../gateway/scripts/latency.py)** prints the same table for any run
files, which is how every table in `docs/LATENCY.md` can be checked:

```bash
uv run python gateway/scripts/latency.py docs/latency/runs/final.jsonl
```

**[`models.py`](../../gateway/scripts/models.py)** is experiment 4. It sends the script's
ten questions, typed, through the real pipeline and tools, one model at a time with no
fallback. Small stand-ins replace speech to text, TTS and the fact store. It times the first
word (`llm_first_token − stt_done`, in sentence mode) and checks that each turn made the
tool calls its question needs, saved the facts or answered from memory, writing `docs/latency/models/<label>.jsonl`.
Groq's turns are paced a minute apart for its free tier.

**[`scripts/hops.sh`](../../scripts/hops.sh)** is experiment 7. With `curl`, it times the
connect, TLS handshake and first byte to Groq, Anthropic, SayTech, Open-Meteo, the gateway
and a ping service in several Google Cloud regions, as the median of five fresh connections.
Run on a laptop, it measures from there; run through Cloud Build in `me-central1`
([`cloudbuild.yaml`](../latency/hops/cloudbuild.yaml)), it measures from where the gateway
lives ([D-98](../DECISIONS.md#d-98-the-services-stay-in-doha-me-central1-for-the-submission)).

Smaller scripts in `gateway/scripts/` try one part at a time: `transcribe.py` times
Groq's speech to text, `chat.py` the chat model's first word, and `saytech.py` SayTech's
calls and the size of their lean results; `ask.py` runs typed turns through the real
pipeline and tools and prints each tool call, the reply and the marks.
[`tts/scripts/benchmark.py`](../../tts/scripts/benchmark.py) times Kokoro ([chapter 7](07-voice.md)).

## When something fails

- A failed turn sends `error` and no `marks`, so it has no timings. The harness logs it,
  carries on with the next question, and records only turns that finished.
- `browser_marks` for a turn that wasn't saved, because the database was down or the turn
  belongs to another visit, store nothing.
- The page draws no stages for a turn missing a mark.

## How it is tested

[`test_latency.py`](../../gateway/tests/test_latency.py) checks that the stages use the
gateway's clock and TTFA the browser's, that percentiles are nearest-rank, and the table.
In [`test_turn.py`](../../gateway/tests/test_turn.py) a `TickingClock` adds 10 ms per
reading, so `test_marks_follow_the_turn_in_order_from_audio_received`,
`test_streaming_marks_the_first_sentence_and_its_audio` and
`test_only_the_answer_after_the_tools_is_spoken_and_marks_llm_first_token` can check the
marks' order exactly. [`test_voice.py`](../../gateway/tests/test_voice.py) checks that a
turn's seven marks are stored together, and never for another visit's turn.
