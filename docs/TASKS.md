# Sarjy — tasks

Status: reviewed 7 Oct 2026. Scope comes from `docs/PRD.md`; decisions live in
`docs/DECISIONS.md` (`D-xx` are made, `O-xx` are still open).

## How to use this file

- Each task is at most 2 hours. Estimates are upper bounds, not promises.
- **Critical path** means the task is needed for "voice loop deployed on day one" (8 Oct).
  M0 is on it by rule: no feature work starts before the standards are in place.
- Work one task at a time, following the loop in `AGENTS.md`: restate, plan, wait for
  "go", implement with tests, run checks, explain, propose a commit.
- From M0.2 on, each task is its own branch and pull request (D-34), within
  repo-standards' limit of 5 commits per pull request. You approve every push and merge.
- "New dependencies" names packages a task will probably need. Each one is still asked
  for, with a reason, when the task starts.
- Tick an acceptance criterion only after checking it.

## Overview

| Milestone | When | Tasks | Hours (upper bound) | Critical path |
| --- | --- | --- | --- | --- |
| M0 Repo skeleton and Sarj standards | 8 Oct, first | 5 | 5 | yes |
| M1 Voice loop deployed | 8 Oct | 13 | 20.5 | yes |
| M2 Memory, tools, tests | 9 Oct | 14 | 20.5 | no |
| M3 Latency deep dive | 9–10 Oct | 12 | 19 | no |
| M4 UI polish, Safari and phone | 9–10 Oct | 8 | 12 | no |
| M5 Docs, presentation, submission | 10–11 Oct | 8 | 11.5 | no |
| M6 Optional: guardrails and reliability | only after an explicit go | 5 | 9 | never |

**Schedule check.** The critical path adds up to 25.5 hours at upper bounds, for one
calendar day, now that deploys go through CI from day one (D-35). All core work (M0–M5)
adds up to about 89 hours across four days. Most tasks should take less than their
ceiling, but the gap is real. M1.1 (GCP setup, no code) runs alongside M0 to absorb some
of it. If scope must go, the PRD's cut list applies first: barge-in (M4.6), then the
custom domain (M4.7), then the GPU experiment (M3.12). We revisit after day one.

## Updates to Sarj

One short message a day, even on a quiet day (PRD).

- [ ] 7–8 Oct: PRD/TDD and plan
- [ ] 8 Oct: voice loop status, deployed URL, first TTFA numbers
- [ ] 9 Oct: memory and tools status, baseline numbers
- [ ] 10 Oct: experiments so far
- [ ] 11 Oct: final update with demo URL, repo, Loom and PDF (part of M5.8)

---

## M0 — Repo skeleton and Sarj standards

Goal: an empty but correctly wired repo, where every commit already passes Sarj's checks.

| ID | Task | Est. | Depends on | Critical path |
| --- | --- | --- | --- | --- |
| M0.1 | Initialise the repo and push the bootstrap commit | 1 h | none | yes |
| M0.2 | Python workspace skeleton (gateway and TTS) | 1 h | M0.1 | yes |
| M0.3 | Frontend scaffold | 1 h | M0.1 | yes |
| M0.4 | Adopt Sarj code standards | 1.5 h | M0.2, M0.3 | yes |
| M0.5 | Protect `main` and run tests in CI | 0.5 h | M0.4 | yes |

### M0.1 Initialise the repo and push the bootstrap commit

- [ ] `git init` with `main` as the default branch; `origin` is
      `github.com/ahmedel-tawil/sarjy` (public, D-34).
- [ ] The brief, the FAQ and `optional-deep-dive.md` live in `.context/`, and
      `git check-ignore` confirms all three are ignored. This matters more now that the
      repo is public.
- [ ] `.gitignore` covers `.env`, `.context/`, virtualenvs, `node_modules/`, build output,
      `.terraform/`, Terraform state, Kokoro model files and `.DS_Store`.
- [ ] `.env.example` exists with variable names only.
- [ ] `.python-version` pins 3.13 (D-30).
- [ ] The "Repo layout" section of `AGENTS.md` no longer says "proposed". Folders are
      created by the tasks that fill them, since git doesn't track empty folders.
- [ ] After your approval, the bootstrap commit is pushed straight to `main`: the only
      direct push to `main` (D-34).

### M0.2 Python workspace skeleton

- [ ] A uv workspace with `backend` and `tts` as members (D-31); `uv.lock` is committed.
- [ ] Each has a `src/` package and one passing smoke test; `uv run pytest` passes.
- [ ] No lint or type-check configuration is written by hand; M0.4 generates it.

New dependencies: `pytest` (dev).

### M0.3 Frontend scaffold

- [ ] `frontend/` is a Vite + React + TypeScript app with Tailwind and shadcn/ui
      initialised and HugeIcons installed, using npm (D-33) and a pinned Node version (O-27).
- [ ] Generator output lands in its own commit whose message says it is generated (D-32).
- [ ] Design tokens are defined once in a CSS file, even if there are only a few so far.
- [ ] `npm run build` and `npx tsc --noEmit` pass; the lockfile is committed.
- [ ] The page shows only the word "Sarjy". No UI is invented ahead of its task.

New dependencies: react, react-dom, vite, typescript, tailwindcss, the shadcn/ui peer
packages, a HugeIcons React package.

### M0.4 Adopt Sarj code standards

- [ ] `uv tool install --python 3.14 code-standards`, then `code-standards setup` with the
      agreed hook runner (O-05), passing `--python-dest` / `--typescript-dest` only if
      root detection gets them wrong.
- [ ] `code-standards doctor` reports a healthy adoption.
- [ ] `code-standards check` exits 0 on the whole repo.
- [ ] `.sarj-standards.toml` pins the bundle version; `.github/workflows/standards.yml` and
      `.github/workflows/commit-policy.yml` exist.
- [ ] basedpyright runs in strict mode on both Python packages.
- [ ] The commit-msg hook rejects `git commit -m "stuff"` and accepts `chore: ...`.
- [ ] No exclusions. If one is unavoidable, it was approved, added with
      `code-standards exclude` and explained in `DECISIONS.md`.
- [ ] The "Commands" section of `AGENTS.md` lists install, lint, type check and test.

### M0.5 Protect `main` and run tests in CI

- [ ] A small CI job runs the Python tests and the frontend build (the generated
      workflows lint; they may not run tests).
- [ ] All workflows pass on this task's pull request.
- [ ] After your approval, `main` requires a pull request and passing checks, and the
      merge method is set (O-06).

---

## M1 — Voice loop deployed (8 Oct)

Goal: on the public `*.run.app` URL, hold a button, speak, and hear Sarjy answer. The
loop is built as experiment 1's baseline (full reply first, then synthesise all of it),
and every latency mark is recorded from the first turn.

| ID | Task | Est. | Depends on | Critical path |
| --- | --- | --- | --- | --- |
| M1.1 | GCP project bootstrap | 1 h | none (runs alongside M0) | yes |
| M1.2 | Terraform foundation | 2 h | M0.4, M1.1 | yes |
| M1.3 | Gateway skeleton | 1.5 h | M0.4 | yes |
| M1.4 | Push-to-talk audio round trip (echo) | 2 h | M0.3, M1.3 | yes |
| M1.5 | CI deploy with Workload Identity Federation | 2 h | M0.5, M1.2, M1.3 | yes |
| M1.6 | First deploy: hello over HTTPS | 1 h | M1.4, M1.5 | yes |
| M1.7 | STT adapter | 1 h | M1.3 | yes |
| M1.8 | LLM adapter (streaming) | 2 h | M1.3 | yes |
| M1.9 | Kokoro TTS service | 2 h | M0.4 | yes |
| M1.10 | Deploy TTS and connect the gateway | 1.5 h | M1.5, M1.9 | yes |
| M1.11 | Turn pipeline, baseline mode | 2 h | M1.7, M1.8, M1.10 | yes |
| M1.12 | Frontend voice loop | 1.5 h | M1.4, M1.11 | yes |
| M1.13 | Deploy the voice loop | 1 h | M1.6, M1.12 | yes |

### M1.1 GCP project bootstrap

No code: you run the steps; I prepare the exact commands.

- [ ] A GCP project exists with billing linked.
- [ ] A budget alert is on the project before any other resource, at the amount you choose.
- [ ] The needed APIs are enabled: Cloud Run, Artifact Registry, Secret Manager,
      Cloud SQL Admin, IAM Credentials, Security Token Service.
- [ ] A versioned Cloud Storage bucket holds Terraform state.
- [ ] The region is chosen and recorded in `DECISIONS.md`, after checking Cloud Run
      WebSockets, Cloud SQL, domain mapping and GPU availability there (O-08).
- [ ] If the GPU experiment (M3.12) stays in scope, the Cloud Run GPU quota request is
      filed now, since approval takes time.

### M1.2 Terraform foundation

- [ ] `infra/` holds the provider, the remote state backend and variables;
      `terraform fmt -check`, `terraform validate` and `code-standards check` pass.
- [ ] Resources: an Artifact Registry repository; one runtime service account each for
      the gateway and TTS; Secret Manager secrets (names only); Cloud Run services
      `gateway` and `tts` running a placeholder image.
- [ ] The gateway's request timeout allows long WebSocket sessions.
- [ ] `tts` cannot be called without authentication (O-09).
- [ ] Secret values are added by hand with `gcloud`; they never appear in Terraform state
      or in git.
- [ ] Image updates made by the deploy script do not show up as Terraform drift.
- [ ] `terraform apply` runs only after you approve the plan.

### M1.3 Gateway skeleton

- [ ] FastAPI app with a lifespan handler, settings read from environment variables into a
      Pydantic model, and structured JSON logs that Cloud Logging parses (O-10).
- [ ] `GET /healthz` returns 200; WebSocket `/ws` echoes binary frames back.
- [ ] The gateway serves the built frontend from `/` (one origin).
- [ ] Routers follow the `*Router.build()` shape required by code-standards
      (`fastapi-class-router-contract`).
- [ ] A multi-stage Dockerfile builds the frontend and the gateway; `docker run` locally
      serves the page.
- [ ] Tests cover `/healthz` and the echo with FastAPI's test client.

New dependencies: fastapi, uvicorn (with WebSocket support), possibly pydantic-settings.

### M1.4 Push-to-talk audio round trip (echo)

- [ ] Holding a button records the mic; audio goes to the gateway in chunks while
      recording, so the upload overlaps speech.
- [ ] On release, the browser sends an end-of-turn message and plays back the echoed audio.
- [ ] Audio playback is unlocked by the first tap, as Safari requires.
- [ ] A denied mic permission shows a clear message instead of failing silently.
- [ ] WebSocket messages have one typed definition per side (O-11).
- [ ] Works locally in desktop Chrome.

New dependencies: possibly a schema library such as zod (O-11).

### M1.5 CI deploy with Workload Identity Federation

- [ ] Terraform creates a workload identity pool and provider limited to
      `ahmedel-tawil/sarjy`, plus a deploy service account with only the roles it needs.
- [ ] A deploy script builds the image, pushes it to Artifact Registry and rolls out a new
      Cloud Run revision. The workflow only calls the script (code-standards rule
      `workflow-embedded-program`).
- [ ] On a merge to `main`, GitHub Actions authenticates through Workload Identity
      Federation and deploys the gateway; TTS joins in M1.10.
- [ ] No service-account JSON key exists anywhere.
- [ ] `terraform apply` runs only after you approve the plan.

### M1.6 First deploy: hello over HTTPS

- [ ] Merging the M1.4 echo app deploys it through CI (D-35).
- [ ] The `*.run.app` URL loads over HTTPS.
- [ ] The WebSocket connects and the echo works in Chrome on a laptop and on a phone over
      mobile data; the mic permission prompt appears on both.
- [ ] If GCP blocks this, the same container runs on a DigitalOcean droplet instead (PRD
      fallback), and that is recorded in `DECISIONS.md`.

### M1.7 STT adapter

- [ ] A `SpeechToText` Protocol, one hosted adapter (O-12) and a fake for tests.
- [ ] Unit tests cover the request it builds and how provider errors map to our own
      exceptions, with no network calls.
- [ ] A dev script transcribes a Chrome (webm) and a Safari (mp4) recording correctly.
- [ ] `DECISIONS.md` records the provider and whether it can stream (PRD open question).

New dependencies: httpx.

### M1.8 LLM adapter (streaming)

- [ ] A `ChatModel` Protocol that streams events: text deltas now, with tool-call deltas
      already part of the event type.
- [ ] One adapter for OpenAI-compatible chat APIs, so Groq, Cerebras and Gemini differ
      only by base URL, key and model name (O-13, O-14). This also leaves room for a
      fallback provider later.
- [ ] Parsing of the streamed response is tested against recorded fixture streams;
      requests have a timeout.
- [ ] System prompt v0: Sarjy's persona, short spoken sentences, no markdown.
- [ ] A dev script streams a reply from the chosen provider.

New dependencies: none beyond httpx, unless O-14 picks a vendor SDK.

### M1.9 Kokoro TTS service

- [ ] `tts/` is a small FastAPI service: `POST /synthesize` takes text, voice and speed
      and returns audio in the agreed format (O-15); `GET /healthz`.
- [ ] Model and voice files are downloaded at image build time from pinned URLs with
      SHA-256 checks; the model loads once at startup.
- [ ] Input is validated: text length limit, known voice.
- [ ] Unit tests use a fake synthesiser, so they never load the model.
- [ ] The image runs locally and returns audible audio for "Hello from Sarjy".
- [ ] Noted for `LATENCY.md`: local synthesis time for a 10-word sentence. Recorded in
      `DECISIONS.md`: the available voices and languages (PRD open question).

New dependencies: kokoro-onnx (brings onnxruntime, numpy, phonemizer, espeakng-loader).

### M1.10 Deploy TTS and connect the gateway

- [ ] CI builds and deploys the TTS image to its Cloud Run service; CPU and memory sizes
      are recorded.
- [ ] An unauthenticated request to TTS is refused; the gateway's request succeeds (O-09).
- [ ] The gateway has a `TextToSpeech` Protocol, an HTTP adapter and a fake; tests cover
      request and response handling.
- [ ] A call from the deployed gateway to TTS returns audio.

### M1.11 Turn pipeline, baseline mode

- [ ] One turn: audio in → STT → LLM (streamed, full reply collected) → TTS on the whole
      reply → audio out. This is experiment 1's baseline.
- [ ] Each turn has a `turn_id`. The gateway records `audio_received`, `stt_done`,
      `llm_first_token`, `first_sentence_ready` and `tts_first_byte` on a monotonic clock.
- [ ] Per turn, one structured log line holds all server marks, and the marks are sent to
      the browser.
- [ ] The current session's recent turns go to the LLM as context (in memory for now).
- [ ] Each turn keeps a list of its tool results, empty for now (room for the optional
      grounding check).
- [ ] A failure in any stage sends an error message to the client; the socket stays open.
- [ ] Tests with fakes cover a full turn, the order of the marks and a failing stage.

### M1.12 Frontend voice loop

- [ ] Sarjy's audio plays through Web Audio.
- [ ] The user's transcript and Sarjy's reply appear as text.
- [ ] A simple state shows listening, thinking or speaking.
- [ ] The browser records `speech_end` (button release) and `playback_start` (first sample
      scheduled) with `performance.now()`, and sends both with the `turn_id`.
- [ ] TTFA per turn is visible in the dev console; the panel comes in M3.2.

### M1.13 Deploy the voice loop

- [ ] Merged and deployed through CI.
- [ ] On the deployed URL, "Hi Sarjy, what can I do in Dubai this weekend?" gets a spoken
      answer, on a laptop and on a phone.
- [ ] Provider keys come from Secret Manager.
- [ ] Cloud Logging shows the per-turn marks line.
- [ ] The first TTFA numbers from a few turns go into the day-one update.

---

## M2 — Memory, tools, tests (9 Oct)

Goal: the four demo scenarios work on the deployed URL.

| ID | Task | Est. | Depends on | Critical path |
| --- | --- | --- | --- | --- |
| M2.1 | SayTech API discovery | 1 h | none | no |
| M2.2 | Postgres locally and on Cloud SQL | 2 h | M1.2, M1.3 | no |
| M2.3 | Schema and migrations | 1.5 h | M2.2 | no |
| M2.4 | Identity cookie, sessions and turns | 1.5 h | M2.3, M1.11 | no |
| M2.5 | Tool-calling loop | 2 h | M1.11 | no |
| M2.6 | Memory tools and facts in the prompt | 1.5 h | M2.4, M2.5 | no |
| M2.7 | Memory panel and "Forget me" | 1.5 h | M2.6, M1.12 | no |
| M2.8 | SayTech adapter: client and data cleaning | 2 h | M2.1, M1.3 | no |
| M2.9 | SayTech cache and last-known-good | 1 h | M2.8 | no |
| M2.10 | `search_tours` and `get_tour` tools | 1.5 h | M2.5, M2.9 | no |
| M2.11 | Weather adapter and `get_weather` tool | 1.5 h | M2.5 | no |
| M2.12 | System prompt v1: scope and grounding | 1 h | M2.6, M2.10, M2.11 | no |
| M2.13 | Public URL protection | 1.5 h | M2.4 | no |
| M2.14 | Demo scenarios 1–4 on the deployed URL | 1 h | M2.7, M2.12, M2.13 | no |

### M2.1 SayTech API discovery

No code. The PRD makes this the first thing on day one, so it can fill any gap on 8 Oct.

- [ ] The public endpoints for listing, detail, filtering and FAQs are written down in
      `DECISIONS.md`: base URL, parameters, auth, rate limits (O-17).
- [ ] Sample responses are saved as test fixtures for the adapter.
- [ ] Known data quirks are listed: missing prices, slugs with spaces, inconsistent
      destinations.
- [ ] Decision recorded: is a new SayTech endpoint needed? If yes, it becomes a separate,
      time-boxed task in the SayTech repo, added only after your go.

### M2.2 Postgres locally and on Cloud SQL

- [ ] `docker compose up db` starts a local Postgres on the same major version as Cloud SQL
      (O-18).
- [ ] Terraform adds a Cloud SQL for PostgreSQL instance on the smallest tier, with deletion
      protection, a database, a user, and the password in Secret Manager.
- [ ] On Cloud Run the gateway connects through the Cloud SQL socket, with a connection pool
      opened at startup; a readiness check proves the connection.
- [ ] `terraform apply` runs only after you approve the plan.

New dependencies: psycopg (binary), psycopg-pool.

### M2.3 Schema and migrations

- [ ] Numbered SQL files create `users`, `facts` (unique on `user_id, key`), `sessions`,
      `turns` and `turn_timings`, as in the PRD.
- [ ] DDL is idempotent; times are `timestamptz`; strings are `text`; foreign keys have
      indexes; IDs follow O-18. The SQL rules pass.
- [ ] A small runner applies pending files in order, in a transaction, and records which
      ran; running it twice changes nothing (O-19).
- [ ] Tests run against a real Postgres locally and in CI (O-20).

### M2.4 Identity cookie, sessions and turns

- [ ] The first visit sets an HTTP-only, Secure, SameSite=Lax cookie holding a random user
      id; a missing or invalid cookie gives a new user.
- [ ] A WebSocket without the cookie is refused.
- [ ] Each visit upserts `users` (updating `last_seen_at`) and adds a `sessions` row.
- [ ] Each turn's user and assistant text is saved to `turns`.
- [ ] SQL runs only inside repository classes injected into the code that uses them
      (`no-psycopg-execution-outside-injected-owner`).
- [ ] Tests cover a new user, a returning user and a new session.

### M2.5 Tool-calling loop

- [ ] Each tool's arguments are a Pydantic model; the JSON schema sent to the LLM is
      generated from it.
- [ ] The pipeline collects tool-call deltas, validates the arguments (invalid ones go back
      to the model as an error result, not a crash), runs the tools (several at once if
      asked) and returns the results, up to a fixed number of rounds.
- [ ] Each turn's tool results are stored on the turn.
- [ ] What `llm_first_token` means when tools run first is decided and written down for
      `LATENCY.md`.
- [ ] Tests with a fake LLM and fake tools: one call, two calls, invalid arguments, a
      failing tool, too many rounds.

### M2.6 Memory tools and facts in the prompt

- [ ] `remember_fact(key, value)` upserts with `ON CONFLICT`; `forget_fact(key)` removes
      the fact.
- [ ] Keys are normalised (for example `favourite_colour`), so "actually it's blue" updates
      the same fact.
- [ ] Saved facts go into the system prompt at session start, and again after a save in
      the same session.
- [ ] The prompt tells the model to save stable facts and preferences only.
- [ ] Tests: saving the same key twice leaves one row with the latest value; forgetting
      removes it.
- [ ] Demo scenario 2 works locally: say the colour, reconnect, ask.

### M2.7 Memory panel and "Forget me"

- [ ] A "What Sarjy remembers" panel lists the user's facts and updates as soon as one is
      saved; the server pushes the change over the WebSocket.
- [ ] "Forget me" asks for confirmation, deletes the user's facts and empties the panel.
- [ ] Tests cover the delete path.

### M2.8 SayTech adapter: client and data cleaning

- [ ] A `Catalogue` Protocol, an HTTP adapter and a fake.
- [ ] Raw responses are parsed into Pydantic models, then mapped to lean results: name,
      price or "on request", city, link.
- [ ] `"from": null` becomes "price on request", never zero.
- [ ] Slugs containing spaces are URL-encoded before any request.
- [ ] Destinations pass through as they are; known inconsistencies are noted in tests, not
      silently "fixed".
- [ ] Requests have timeouts. Tests use the M2.1 fixtures and cover each rule above.

### M2.9 SayTech cache and last-known-good

- [ ] Responses are cached in the process for a configurable few minutes (O-23).
- [ ] If SayTech fails or times out, the last good copy is served and a warning is logged.
- [ ] Tests use a fake clock and a failing fake client.

### M2.10 `search_tours` and `get_tour` tools

- [ ] `search_tours(city, max_price_aed, category, accessible)` returns up to 5 products.
- [ ] `get_tour(slug)` returns one product's details and the matching FAQ answers.
- [ ] Argument validation is tested.
- [ ] Locally, demo scenarios 1 and 4 work, and the prices match the Magic Experience
      website.

### M2.11 Weather adapter and `get_weather` tool

- [ ] A `Weather` Protocol and one adapter (O-21).
- [ ] UAE cities map to coordinates through a fixed table, with no geocoding call.
- [ ] `get_weather(city, date)` returns that day's temperature and conditions, with dates
      in Dubai time.
- [ ] A date outside the forecast range gives a clear "no forecast" result.
- [ ] Tests use fixtures; demo scenario 3 works locally.

### M2.12 System prompt v1: scope and grounding

- [ ] The prompt covers: scope (UAE travel, Magic Experience products, weather, the user's
      own preferences); prices, availability and forecasts only from tool results;
      "price on request" wording; no booking, share the link instead; a short friendly
      redirect for off-topic requests; replies written to be spoken.
- [ ] Today's date and timezone are injected.
- [ ] The prompt lives in one file.
- [ ] A dev script that sends text turns through the pipeline (skipping STT) shows the
      expected behaviour for: an off-topic request, price bait, a missing price, and a
      booking request.

### M2.13 Public URL protection

- [ ] New turns are rate-limited per user and per IP; the limits come from configuration
      (O-22).
- [ ] Audio length per turn and turns per session have maximums.
- [ ] Hitting a limit gives the user a friendly message.
- [ ] Cloud Run's maximum instance count is capped, as a cost guard.
- [ ] Tests cover each limit with a fake clock.

### M2.14 Demo scenarios 1–4 on the deployed URL

- [ ] All four PRD scenarios pass end to end on the deployed URL in desktop Chrome.
- [ ] Results go into the 9 Oct update.

---

## M3 — Latency deep dive (9–10 Oct)

Goal: TTFA measured on every turn, shown live, and driven down by documented experiments.
Each experiment changes one thing against the current best configuration, runs the same
script, and records p50/p95 before and after in `docs/LATENCY.md`. Experiment switches are
configuration (environment variables), not code branches.

| ID | Task | Est. | Depends on | Critical path |
| --- | --- | --- | --- | --- |
| M3.1 | Store timings and summarise p50/p95 | 1.5 h | M2.3, M1.12 | no |
| M3.2 | Live latency waterfall panel | 2 h | M3.1 | no |
| M3.3 | Test script and experiment harness | 2 h | M3.1 | no |
| M3.4 | Experiment 1: baseline | 1 h | M3.3, M2.14 | no |
| M3.5 | Sentence chunker and per-sentence pipeline | 2 h | M3.4 | no |
| M3.6 | Experiment 2: sentence streaming end to end | 1.5 h | M3.5 | no |
| M3.7 | Experiment 3: TTS cache | 1.5 h | M3.6 | no |
| M3.8 | Experiment 4: model choice | 1.5 h | M3.4 | no |
| M3.9 | Experiment 5: tool payload size | 1 h | M3.4 | no |
| M3.10 | Experiment 6: warm vs cold | 1 h | M3.4 | no |
| M3.11 | Experiment 7: region | 2 h | M3.4 | no |
| M3.12 | Experiment 8 (stretch): Kokoro on GPU | 2 h | M3.4, GPU quota | no (cut list #3) |

### M3.1 Store timings and summarise p50/p95

- [ ] All seven marks of every turn are stored in `turn_timings`; the browser's marks
      arrive with their `turn_id`.
- [ ] Gaps are computed per clock: TTFA = `playback_start − speech_end` on the browser
      clock; stage gaps from `audio_received` to `tts_first_byte` on the server clock;
      "network and browser" is what remains.
- [ ] A command prints p50 and p95 per gap for a labelled run.
- [ ] Tests cover the gap and percentile maths (the PRD's "latency timeline" tests).
- [ ] `docs/LATENCY.md` exists with the mark definitions and how each gap is computed.

### M3.2 Live latency waterfall panel

- [ ] After each turn, the UI shows a waterfall of its stages and the TTFA as a headline.
- [ ] The last few turns stay visible for comparison.
- [ ] Colours come from tokens; motion respects `prefers-reduced-motion`.
- [ ] Any client-side timing maths has unit tests if O-25 adds a frontend test runner.

### M3.3 Test script and experiment harness

- [ ] A fixed script of about ten questions covers the four demo scenarios, stored as audio
      files (O-24).
- [ ] A Python command plays the script against a URL as a WebSocket client, N times, under
      a run label.
- [ ] The harness records its own client marks: `speech_end` when the last audio chunk is
      sent, and `playback_start` approximated by the first audio byte received.
      `LATENCY.md` states how this differs from a real browser.
- [ ] It prints the p50/p95 table from M3.1.

### M3.4 Experiment 1: baseline

- [ ] Baseline p50/p95 for TTFA and each stage are in `LATENCY.md`, measured on the
      deployed URL.
- [ ] A short "where the time goes" breakdown.
- [ ] Targets for the later experiments are set from these numbers (PRD: set on day 2).

### M3.5 Sentence chunker and per-sentence pipeline

- [ ] A sentence chunker splits streamed text into speakable sentences. Unit tests cover
      abbreviations, decimals, prices such as "AED 1,250.50", ellipses and very short
      fragments.
- [ ] A per-sentence step sits between the LLM and TTS, where the optional grounding check
      would run later.
- [ ] In `sentence` pipeline mode, each sentence goes to TTS as soon as it is complete, and
      audio is sent in order.
- [ ] `first_sentence_ready` now marks the first complete sentence.
- [ ] Tests with fakes check ordering and marks.

### M3.6 Experiment 2: sentence streaming end to end

- [ ] The browser queues sentence audio so playback has no gaps or overlaps.
- [ ] Before/after numbers against the baseline are in `LATENCY.md`.

### M3.7 Experiment 3: TTS cache

- [ ] Audio is cached by a hash of text, voice, speed and model version (O-23 decides
      where it lives).
- [ ] Common phrases (greetings, confirmations) are warmed at startup.
- [ ] The hit rate is logged; before/after numbers are in `LATENCY.md`.

### M3.8 Experiment 4: model choice

- [ ] Groq, Cerebras and Gemini, with at least two model sizes, are compared on first-token
      time using the same script.
- [ ] Tool calls are checked for correctness, not just speed.
- [ ] The final provider and model are recorded in `DECISIONS.md` with the numbers.

Needs API keys for each provider.

### M3.9 Experiment 5: tool payload size

- [ ] A switch sends the model either the lean SayTech result or the raw API response.
- [ ] Prompt tokens (from the provider's usage data) and time to first token are compared
      in `LATENCY.md`.

### M3.10 Experiment 6: warm vs cold

- [ ] TTFA of the first turn after idle is measured with minimum instances at 0 and at 1,
      for the gateway and for TTS.
- [ ] The monthly cost of a minimum instance is noted, and a setting for review week is
      chosen.

### M3.11 Experiment 7: region

- [ ] The cost of the network hop is measured: from the Gulf to the gateway, and from the
      gateway's region to each provider.
- [ ] If a second region is deployed for the test, it is removed afterwards, with your
      approval.
- [ ] Results and the final region choice are in `LATENCY.md` and `DECISIONS.md`.

### M3.12 Experiment 8 (stretch, cut list #3): Kokoro on GPU

- [ ] Runs only if GPU quota was granted (requested in M1.1).
- [ ] TTS runs on a Cloud Run GPU; synthesis time, TTFA and cost are compared with CPU.

---

## M4 — UI polish, Safari and phone (9–10 Oct)

Goal: delightful on a laptop and a phone, in Chrome and Safari, with nothing invented
beyond the PRD.

| ID | Task | Est. | Depends on | Critical path |
| --- | --- | --- | --- | --- |
| M4.1 | Visual identity and layout | 2 h | M2.7, M3.2 | no |
| M4.2 | Conversation states and errors | 1.5 h | M4.1 | no |
| M4.3 | Safari and iOS audio | 2 h | M1.12 | no |
| M4.4 | Device test matrix | 1 h | M4.3, M2.14 | no |
| M4.5 | Voice activity detection | 2 h | M1.12 | no |
| M4.6 | Barge-in | 1.5 h | M4.5, M3.5 | no (cut list #1) |
| M4.7 | Custom domain `sarjy.saytech.ae` | 1 h | M1.6 | no (cut list #2) |
| M4.8 | Accessibility and motion pass | 1 h | M4.1 | no |

### M4.1 Visual identity and layout

- [ ] Sarjy's own tokens (colours, type scale, spacing, radius) live in one CSS file; no hex
      values or ad-hoc colour classes anywhere else.
- [ ] One screen, built only from what the PRD describes: the talk control, the
      conversation, the memory panel and the latency panel.
- [ ] Works at phone and laptop widths.
- [ ] HugeIcons only; shadcn/ui primitives wherever one exists.
- [ ] Motion is at most 300 ms and switches off under `prefers-reduced-motion`.

### M4.2 Conversation states and errors

- [ ] Clear states for: mic denied, connection lost (with automatic reconnect), provider
      failure, rate limit hit.
- [ ] Product links in Sarjy's replies are clickable in the conversation.
- [ ] One person who hasn't seen the app before understands what to do within seconds.

### M4.3 Safari and iOS audio

Do this on 9 Oct (PRD: "Test Safari on day 2, not day 4").

- [ ] The recording format is chosen by what the browser supports (webm in Chrome, mp4 in
      Safari), and STT accepts both.
- [ ] Playback starts reliably on iOS after the first tap, including after the screen
      locks and unlocks.
- [ ] The full loop works in Safari on macOS and on iOS.

### M4.4 Device test matrix

- [ ] The four demo scenarios pass in Chrome and Safari on a laptop, in iOS Safari, and in
      Android Chrome if a device is available.
- [ ] A results table is ready for the README.

### M4.5 Voice activity detection

- [ ] A hands-free mode ends the turn when the user stops speaking; push-to-talk stays
      available.
- [ ] In this mode `speech_end` is when speech actually stopped, not when VAD noticed; the
      detection delay is measured and noted in `LATENCY.md`.
- [ ] The approach follows O-26.

### M4.6 Barge-in (cut list #1)

- [ ] Speaking while Sarjy talks stops playback at once and cancels the turn in flight on
      the server; LLM and TTS tasks are cancelled cleanly.
- [ ] Tests cover cancellation without leaked tasks.

### M4.7 Custom domain `sarjy.saytech.ae` (cut list #2)

- [ ] The domain serves the app over HTTPS, through Cloud Run domain mapping if the region
      supports it.
- [ ] You add the DNS record in DigitalOcean.
- [ ] The mic and the WebSocket work on the custom domain.

### M4.8 Accessibility and motion pass

- [ ] The talk control works from the keyboard (hold Space) and has an accessible name.
- [ ] Focus is visible; the token palette passes WCAG AA contrast.
- [ ] Nothing moves under `prefers-reduced-motion`.

---

## M5 — Docs, presentation, submission (10–11 Oct)

Goal: submitted by 11 Oct, 5 PM, with docs a reviewer can follow without me.

| ID | Task | Est. | Depends on | Critical path |
| --- | --- | --- | --- | --- |
| M5.1 | Cost per conversation | 1 h | M3.4 | no |
| M5.2 | README | 2 h | M5.1, M4.4 | no |
| M5.3 | Finish `LATENCY.md` | 2 h | the M3 experiments that ran | no |
| M5.4 | Code walkthrough and clean-up | 2 h | M2–M4 done | no |
| M5.5 | Final acceptance run | 1 h | M5.4 | no |
| M5.6 | Loom walkthrough | 1.5 h | M5.5 | no |
| M5.7 | Short PDF | 1.5 h | M5.3 | no |
| M5.8 | Submit | 0.5 h | M5.6, M5.7 | no |

### M5.1 Cost per conversation

- [ ] A small table estimates one conversation's cost from measured numbers: STT seconds,
      LLM tokens, TTS compute time, hosting.
- [ ] It shows what self-hosted TTS changes compared with a per-character bill.

### M5.2 README

- [ ] One-command local run, checked on a fresh clone.
- [ ] Architecture diagram; decisions and trade-offs (linking `DECISIONS.md`); the API
      justification in 2–3 sentences, as the brief asks; cost estimate; tested-devices
      table; links to `LATENCY.md`.
- [ ] Credit to Sarj's public standards, and how AI was used.
- [ ] Every command in it has been run and works.

### M5.3 Finish `LATENCY.md`

- [ ] Where the time goes (final breakdown), each experiment with before/after p50/p95,
      what worked, what didn't, and what I'd do with another week.

### M5.4 Code walkthrough and clean-up

- [ ] You have read every file and can explain each line.
- [ ] No dead code, unexplained TODOs or leftover debug output.
- [ ] `code-standards check`, type checks and tests are green.

### M5.5 Final acceptance run

- [ ] The four scenarios pass on the deployed URL across the M4.4 device matrix.
- [ ] Rate limits and the budget alert are confirmed, minimum instances are set for review
      week, and provider keys have headroom.

### M5.6 Loom walkthrough

- [ ] A short script: the four scenarios with the latency waterfall, the architecture, the
      latency story, one code tour.
- [ ] Recorded, and the link works when logged out.

### M5.7 Short PDF

- [ ] Two to four pages: what Sarjy is, how to try it, architecture, latency results,
      decisions and next steps.

### M5.8 Submit (by 11 Oct, 5 PM)

- [ ] If the repo is private, the reviewer's GitHub account has access.
- [ ] The repository URL is submitted through Ashby.
- [ ] Final update to Sarj with the demo URL, repo, Loom and PDF.

---

## M6 — Optional: guardrails and reliability

**Optional.** Never on the critical path, never started without your explicit go, and may
be dropped (see `.context/optional-deep-dive.md`). The core already leaves room for it:
tool results are recorded per turn (M1.11, M2.5), a per-sentence step sits between the LLM
and TTS (M3.5), and the LLM adapter can take a second provider (M1.8). Measured by the
red-team pass rate and the latency each guard adds, using the same marks.

| ID | Task | Est. | Depends on | Critical path |
| --- | --- | --- | --- | --- |
| M6.1 | Grounded facts check | 2 h | M3.5, M2.10, M2.11 | never |
| M6.2 | Topic and jailbreak guard | 2 h | M2.12 | never |
| M6.3 | Tool data is data | 1 h | M2.10 | never |
| M6.4 | Red-team set and `docs/GUARDRAILS.md` | 2 h | M2.14 | never |
| M6.5 | Reliability: timeouts, fallback, spoken failures | 2 h | M1.8, M1.11 | never |

The order follows the optional brief's priorities. Measuring "before and after each
guard" needs the red-team set first, so a small version of M6.4 may be worth building
before M6.1. Your call if M6 starts.

### M6.1 Grounded facts check

- [ ] Every price, availability or temperature in a sentence is checked against the same
      turn's tool results before TTS.
- [ ] An unbacked number is replaced with safe wording ("price on request",
      "let me check that").
- [ ] The latency added per sentence is measured; tests cover backed, unbacked and
      differently formatted numbers.

### M6.2 Topic and jailbreak guard

- [ ] Simple rules plus a small, fast model check the user's input in parallel with the
      main LLM call.
- [ ] A flagged input cancels the main reply, and Sarjy says a short, friendly redirect.
- [ ] The added TTFA is measured for flagged and unflagged turns.

### M6.3 Tool data is data

- [ ] Tool results are clearly delimited and marked as data in the prompt.
- [ ] A fixture with instructions hidden in a SayTech description does not change Sarjy's
      behaviour.

### M6.4 Red-team set and `docs/GUARDRAILS.md`

- [ ] About 30 scripted prompts with expected behaviour: off-topic requests, jailbreak
      attempts, price bait, instructions hidden inside user claims.
- [ ] A script reports the pass rate; results go in `docs/GUARDRAILS.md`.

### M6.5 Reliability: timeouts, fallback, spoken failures

- [ ] Every stage has a timeout.
- [ ] On a timeout or rate limit, the LLM falls back to a second provider.
- [ ] Any failure produces a short spoken message, never silence.
- [ ] Tests cover each path with fakes.
