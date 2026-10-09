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

## Experiment 3: TTS cache

A spoken sentence is kept in the gateway's memory by its text and voice, and reused
when the same words are said again; six common sentences are made when the gateway
starts (D-97). `SARJY_TTS_CACHE_BYTES=0` turns it off. Before building it, the 160
replies stored by 10 Oct were split into the sentences TTS speaks: 17% of sentences
and 26% of first sentences had been said before. Most of those were the script's own
lines ("Nice to meet you, Sam.", "Your favourite colour is green."); the generic
ones, "What would you like to know about Magic Experience?" and "Would you like child
prices for any of these?", became the warmed phrases. Measured on 10 Oct with the
gateway and TTS on the laptop, two passes of the script each, the cache-on gateway
started fresh and warmed.

| Gap | Cache off p50 | Cache on p50 | Cache off p95 | Cache on p95 |
| --- | --- | --- | --- | --- |
| `tts` | 1,276 ms | 1,404 ms | 2,944 ms | 3,020 ms |
| `ttfa` | 3,808 ms | 3,854 ms | 5,944 ms | 6,974 ms |

The runs are `tts-cache-off-local.jsonl` and `tts-cache-on-local.jsonl`.

- **One sentence in ten was a hit.** 6 of 61 synthesised sentences: one warmed phrase
  ("Thanks for telling me, I'll remember that.") and five lines the first pass had
  already said to an earlier visitor called Sam.
- **A hit on the first sentence saves the whole TTS step.** Five of the twenty turns
  started with a hit: their `tts` took 0 to 2 ms instead of about 1.3 s, and their TTFA
  was 1.9 to 2.5 s, where the same questions took 2.5 to 4.0 s without the cache.
- **The medians don't move.** Most first sentences name a tour, a price or the
  traveller, and those differ from turn to turn, so the hits are too few to shift the
  p50; the other turns differ within the usual noise of the model and the laptop.
- **Replays and repeated lines are where it pays.** A replay of an answer this gateway
  has just spoken finds its sentences in the cache (by construction; not timed here),
  and so does any line a visitor hears again.

The cache stays on: it costs at most 32 MB of the gateway's 512 MiB and never slows a
miss. Real visitors will hit it less often than the script, which repeats its own
questions; the hit rate is logged on every sentence to show how much.

## Experiment 4: model choice

The same ten questions as typed text, so STT and TTS drop out, through the real pipeline
and tools in sentence mode, two passes per model, each pass a fresh visit with its own
memory and no fallback. Each turn is checked against what its question needs: a search
in Abu Dhabi under 400 dirhams, both facts of "colour and heights" saved, green answered
from memory, a Dubai search, tomorrow's forecast, "price on request" for the buggy tour,
the name Sam saved, Saturday's forecast for Abu Dhabi, and no tool for "thanks". Run on
10 Oct with `gateway/scripts/models.py`; the turns are in `docs/latency/models/`.
Cerebras and Gemini were not run: they need keys of their own (Ahmed's call, 10 Oct).

| Model | Checks passed | Facts saved (of 4) | First word p50 | p95 | Tool turns p50 |
| --- | --- | --- | --- | --- | --- |
| Claude Haiku 5.5 | 18 of 20 | 4 | 970 ms | 2,621 ms | 1,536 ms |
| Groq gpt-oss-120b | 17 of 20 | 2 | 1,702 ms | 3,267 ms | 1,841 ms |
| Groq gpt-oss-20b | 14 of 20 | 2 | 1,624 ms | 2,146 ms | 1,624 ms |
| Groq Qwen 3.8 27B | 11 of 20 | 0 | 684 ms | 1,821 ms | 1,706 ms |

Claude Sonnet 5.5 could not run through the gateway: its lowest thinking setting,
`between_tools`, returns thinking blocks that must go back with every tool round, which
the adapter doesn't do. Timed directly on two questions with no tool (the real prompt and
tools, ten each, interleaved with Haiku), its first word took 1,662 and 1,612 ms at p50
against Haiku's 924 and 914 ms.

- **Only Claude saves what the traveller says in passing.** Haiku saved green, the
  dislike of heights and the name in both passes. Qwen saved nothing, while saying
  "I've noted that" and "I've saved your name"; both gpt-oss models saved the colour and
  the name but never the heights.
- **Qwen answers without its tools.** It used one on only 7 of 20 turns, which is why its
  first word looks fast. It gave the buggy tour a price of 299 dirhams (SayTech has it on
  request) and a Saturday forecast without asking for one. On turns that did use a tool,
  Haiku was faster.
- **gpt-oss reads dates badly.** Both sizes asked for the weather on a Tuesday or a
  Wednesday and called it Saturday's; the 20b also saved the name again on "thanks" and
  looked for the buggy tour in Abu Dhabi.
- **Haiku's misses were one question.** "What can I do in Dubai?", after the Dubai search
  of question 4, it answered once from that earlier answer and once with a question back,
  neither with a fresh search.
- **Groq's free tier limits it to a fallback.** 8,000 tokens a minute per model is about
  one tool turn a minute, for every visitor together.

Claude Haiku 5.5 stays first (D-69). The fallback moves from Qwen to gpt-oss-120b: slower,
but it never answered a tour or forecast question without its tool (D-96).

## Experiment 5: tool payload size

One change: `SARJY_TOOL_PAYLOAD=raw` hands the model SayTech's responses exactly as they
came, instead of Sarjy's lean results, through the same tool specs (M3.9). Measured on
the laptop against a local gateway and TTS, since only what the model reads changes;
Claude, SayTech and the forecast are reached over the internet as in production. The
script twice per setting, 20 turns each, all transcribed correctly. The provider's own
token counts come from the gateway's log, one line per model round (D-91). Runs:
`payload-lean-local.jsonl`, `payload-raw-local.jsonl`.

Input tokens of the round after the tools, median per question:

| Question | Lean | Raw |
| --- | --- | --- |
| 01 kids under 400 in Abu Dhabi | 3,849 | 4,144 (+8%) |
| 04 Dubai this weekend | 4,802 | 4,994 (+4%) |
| 05 safari tomorrow | 4,245 | 4,305 (+1%) |
| 07 what can I do in Dubai | 4,621 | 5,094 (+10%) |
| 09 Abu Dhabi weather on Saturday | 4,152 | 4,134 (0%, no tour tool) |

| Gap | Lean p50 | Raw p50 | Lean p95 | Raw p95 |
| --- | --- | --- | --- | --- |
| `llm_first_word` | 1,140 ms | 1,029 ms | 3,965 ms | 2,948 ms |
| `ttfa` | 3,156 ms | 2,744 ms | 6,065 ms | 5,765 ms |

- **The lean results save little.** SayTech's assistant endpoints, built for Sarjy (D-56),
  already return compact answers, so the raw response adds 0 to 10% to the round that
  reads it. Over both runs raw even used 4% fewer tokens, because in it the model twice
  answered the buggy question without searching, and some fillers and tool rounds fell
  differently.
- **No latency effect shows.** The first-word gaps differ within the noise between runs,
  and in raw's favour; a few hundred extra tokens are nothing to the model's prefill.
- **The prompt is what the model reads.** A turn with no tool reads about 3,550 input
  tokens, nearly all of it the system prompt with SayTech's catalogue context, and a tool
  turn reads it twice, about 7,000 to 9,000 in all. That is the next lever: caching the
  prompt's stable part with Claude's prompt caching (experiment 9).

Lean stays the default: it never adds fields the model doesn't use, and a future change
to SayTech's responses can't swell it.

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

## Experiment 9: prompt caching

Every round sends the tools and the system prompt again, about 3,050 tokens that are the
same for every traveller and every turn (experiment 5). The prompt is now two system
blocks: the shared part (rules and SayTech's catalogue) and the turn's part (the
traveller's facts and the time). Claude caches the tools and the shared block for five
minutes after each use (D-93). `SARJY_CLAUDE_PROMPT_CACHE=false` turns it off for the
comparison. Measured on 9 Oct with the gateway and TTS on the laptop, Claude Haiku 5.5,
two passes of the script each.

| Gap | Cache off p50 | Cache on p50 | Cache off p95 | Cache on p95 |
| --- | --- | --- | --- | --- |
| `llm_first_word` | 1,060 ms | 1,105 ms | 2,654 ms | 2,981 ms |
| `ttfa` | 2,912 ms | 3,560 ms | 4,695 ms | 5,892 ms |

The runs are `cache-off-local.jsonl` and `cache-on-local.jsonl`. TTFA differs mostly in
`tts` (783 against 1,114 ms p50), the laptop's CPU, which caching doesn't touch.

To take STT, TTS and the tools out, the same request was sent to Claude 20 times each way,
interleaved: the real prompt, tools and catalogue, and the script's "thanks", timed to the
first word.

| Same request, 20 each | p50 | p90 | Fastest | Slowest |
| --- | --- | --- | --- | --- |
| Cached (3,054 read from the cache, 137 fresh) | 869 ms | 1,175 ms | 716 ms | 1,670 ms |
| Uncached (3,191 fresh) | 813 ms | 993 ms | 684 ms | 1,178 ms |

| Input tokens, from Claude's usage | Cache off | Cache on |
| --- | --- | --- |
| Model rounds | 36 | 34 |
| Read per round, on average | 3,926 | 3,931 |
| Read fresh | 141,345 | 29,831 |
| Read from the cache | 0 | 100,782 |
| Written to the cache | 0 | 3,054 (the first round only) |
| Billed per round, in full-price input tokens | 3,926 | 1,286 |

- **The cache works for every visitor.** The first round wrote 3,054 tokens; every later
  round read them, including the second pass's new identity with different facts,
  because nothing about the traveller comes before the cache point.
- **It doesn't make Sarjy answer sooner.** The first word came no sooner, in the voice
  runs or the direct requests; the differences are within the noise and lean the other
  way. At about 3,000 tokens, reading the prompt is a small part of Haiku's time to the
  first word.
- **It cuts the cost of what the model reads by two thirds.** Cache reads cost a tenth of
  the input price and the one write 1.25 times, so a round bills 1,286 full-price tokens
  instead of 3,926.
- **The fresh part grows with the visit.** From 158 tokens on a first question to about
  1,700 late in a visit: the recent turns and the tool results. Caching the history as well
  would mean moving the facts and the time after it; at under 2,000 tokens it isn't worth
  the change yet.

Caching stays on, since it lowers the cost without slowing anything. No pre-warming,
because a cold cache costs no time.

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
