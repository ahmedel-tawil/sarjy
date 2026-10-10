# The code book

This book walks you through Sarjy's code in the order a turn runs: from the traveller
letting go of the orb to Sarjy's first words playing in the browser. Each chapter says what
one part does and why, follows the path through it with links to the exact lines, names
the types and functions that matter, says what happens when something fails, and shows
where it is tested.

Read it start to finish in a little over an hour, or jump to the part you need. The
reasons behind the code live in [`docs/DECISIONS.md`](../DECISIONS.md); each D-number in
the book links to its entry there.

## Chapters

| # | Chapter | What it covers | Minutes |
| --- | --- | --- | --- |
| 1 | [The shape](01-shape.md) | How the gateway is put together: `create_app`, the services built from `SARJY_*` settings, one `Protocol` and one adapter per provider, and the fakes the tests use instead. | 6 |
| 2 | [The API](02-api.md) | The three HTTP endpoints, and the WebSocket at `/ws` in full: every message in both directions, in the order one turn sends them, the identity cookie and the rate limits. Why `/docs` only shows the HTTP part. | 7 |
| 3 | [A visit opens](03-visit.md) | What happens when the page's socket connects: the cookie check, waking TTS, loading memory and earlier visits, the voice, then the loop that reads audio and control messages. The turn limits. | 6 |
| 4 | [One turn](04-turn.md) | `TurnPipeline.run`: transcribing while the prompt is built, then speaking each sentence as soon as the model writes it. The sentence chunker. | 7 |
| 5 | [The model and its tools](05-model-and-tools.md) | The tool loop and its guards, the turn's history, the two-part prompt, Claude and Groq behind one interface with a fallback, and the tools for tours, availability and weather. | 9 |
| 6 | [Memory and storage](06-memory-and-storage.md) | Facts, visits, turns and timings in Postgres: the schema, the migrations, and the SQL with its transactions and `ON CONFLICT`. | 6 |
| 7 | [The voice](07-voice.md) | The Kokoro TTS service with its own text front end, how the gateway calls it with an ID token, and the gateway's cache of spoken sentences. | 6 |
| 8 | [Measuring latency](08-latency.md) | The seven marks, how they are recorded and stored, and the scripts that produced every number in `docs/LATENCY.md`. | 6 |
| 9 | [The page](09-page.md) | The browser side of a turn: the session, the socket, the recorder, the player and voice mode's orb and captions. | 7 |
| 10 | [Shipping it](10-shipping.md) | Terraform for Cloud Run, Cloud SQL, the registry, secrets, keyless CI and the load balancer; the deploy workflow and script; Compose; the code standards. | 7 |

## The repository on one screen

```text
gateway/src/sarjy_gateway/   the voice gateway (FastAPI)
  app.py services.py settings.py            wiring and configuration            ch. 1
  health.py voices.py messages.py           the HTTP API and the socket's messages ch. 2
  voice.py identity.py limits.py            a visit on the WebSocket             ch. 3
  turn.py stt.py sentences.py               one turn, from audio to clips        ch. 4
  llm.py claude.py prompts.py tools.py      the model, the prompt, the tool loop ch. 5
  catalogue*.py tour_tools.py weather*.py   SayTech and Open-Meteo as tools      ch. 5
  memory.py conversation_store.py migrate.py migrations/   Postgres              ch. 6
  tts.py tts_cache.py                       the gateway's side of the voice      ch. 7
  timeline.py latency.py                    the marks and the percentiles        ch. 8
gateway/tests/               pytest; fakes.py stands in for every service
gateway/scripts/             experiment scripts: harness, latency, models, ask   ch. 8
tts/src/sarjy_tts/           the Kokoro TTS service                              ch. 7
frontend/src/lib/            the page's voice client                             ch. 9
frontend/src/components/     voice mode, the orb, the captions                   ch. 9
infra/                       Terraform for Google Cloud                          ch. 10
.github/workflows/  scripts/deploy.sh   CI and deploys                           ch. 10
scripts/hops.sh              network hops to the providers (experiment 7)        ch. 8
compose.yaml                 the whole stack on one machine                      ch. 10
docs/                        PRD, DECISIONS, LATENCY, COST; latency/ holds the runs
```

## Words this book uses

- **Visit:** one WebSocket connection, normally one page load. It is a row in `sessions`.
- **Turn:** one question and its answer. It has a `turn_id`, made by the gateway.
- **Round:** one request to the model inside a turn. A turn that calls tools has several.
- **Mark:** a named moment in a turn, such as `stt_done`. Seven marks make a turn's timeline.
- **Fact:** one thing Sarjy remembers about a traveller, a key and a value.
- **Clip:** one WAV file of speech, normally one sentence.

## How the links work

Links to code point at a file and line on the branch you are reading, for example
[`turn.py` line 238](../../gateway/src/sarjy_gateway/turn.py#L238). They were checked
against `main` on 11 Oct 2026. If the code moves on, the function names in the text still
find the right place.
