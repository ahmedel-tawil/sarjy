# Sarjy — decisions

Status: draft for review, 7 Oct 2026.

Each entry records a decision, why it was made, and what else was considered. D-01 to D-29
come from `docs/PRD.md` (draft, 7 Oct 2026) and `AGENTS.md`. When a task settles an open
decision (O-xx), it moves up as a new D entry. Approved `code-standards` exceptions are
recorded at the end.

Alternatives marked † are not written in the PRD; I added them as the obvious
candidates. Keep, edit or delete them, since reviewers may ask about them.

## Decisions made

### D-01 Sarjy is a voice concierge for Magic Experience

- **Decision:** Sarjy is a voice concierge for Magic Experience, a Dubai tour operator. A
  traveller talks to it; it finds real UAE activities, checks the weather and remembers
  their preferences across visits.
- **Reason:** It answers from live data: a real operator's catalogue on SayTech, which I
  built and run. That makes the answers useful and checkable, and the submission personal.
- **Alternatives considered:** a general-purpose assistant on the brief's example APIs
  (weather, calendar, maps, transit) †.

### D-02 The deep dive is latency

- **Decision:** Latency is the deep dive. Guardrails and reliability is an optional second
  deep dive, started only after the core is done and you say go.
- **Reason:** Time-to-first-audio is what a caller actually feels, it can be measured on
  every turn, and every experiment gives before/after numbers to discuss.
- **Alternatives considered:** the other options in the brief: UI/UX and multimodal,
  guardrails and reliability (kept as the optional second), multistep workflows,
  multiplayer, something else.

### D-03 The metric is time-to-first-audio (TTFA)

- **Decision:** TTFA runs from the moment the user stops speaking to the moment Sarjy's
  first audio sample plays in the browser.
- **Reason:** It is what the user feels, including network and playback, not only server
  time.
- **Alternatives considered:** server-side time to first TTS byte †; time to first LLM
  token †.

### D-04 How latency is measured

- **Decision:** Every turn gets a `turn_id`, and seven marks are recorded: `speech_end` and
  `playback_start` by the browser; `audio_received`, `stt_done`, `llm_first_token`,
  `first_sentence_ready` and `tts_first_byte` by the gateway. Browser gaps use the
  browser's clock and server gaps use the server's. Results are stored per turn and
  summarised as p50 and p95 over a fixed script of test questions.
- **Reason:** Browser and server clocks differ, so gaps are never measured across them. A
  fixed script makes experiments compare like with like, and p95 shows the slow turns a
  reviewer will notice.
- **Alternatives considered:** a single end-to-end timer †; distributed tracing such as
  OpenTelemetry †; synchronising the browser and server clocks †.

### D-05 Eight experiments, targets set by the baseline

- **Decision:** Experiments, each run against the same script and recorded in
  `LATENCY.md` with before/after numbers: (1) baseline: full reply, then synthesise all of
  it; (2) sentence streaming; (3) TTS cache; (4) model choice (Groq, Cerebras, Gemini);
  (5) tool payload size; (6) warm vs cold; (7) region; (8) stretch: Kokoro on GPU vs CPU.
  No targets are promised up front; the baseline sets them on day 2.
- **Reason:** Targets based on real numbers, not guesses; each experiment isolates one
  change.
- **Alternatives considered:** fixed targets up front †.

### D-06 One gateway owns each turn

- **Decision:** A single FastAPI gateway receives the user's audio, calls the services in
  order and streams Sarjy's voice back sentence by sentence. It is the only component that
  talks to providers.
- **Reason:** Keys stay server-side, and every stage can be timed in one place.
- **Alternatives considered:** the browser calling providers directly †; a voice-agent
  framework or hosted voice platform †.

### D-07 One WebSocket per session

- **Decision:** Browser and gateway talk over one WebSocket per session.
- **Reason:** It streams audio both ways with little overhead.
- **Alternatives considered:** one HTTP request per turn †; WebRTC †.

### D-08 Push-to-talk first, voice activity detection next

- **Decision:** Turn-taking starts as push-to-talk; voice activity detection comes next;
  barge-in is on the cut list.
- **Reason:** A reliable demo first.
- **Alternatives considered:** voice activity detection from the start. The PRD still lists
  this as an open question (O-16).

### D-09 Speech-to-text: a hosted Whisper-class model

- **Decision:** Use a hosted Whisper-class model, for example on Groq. The provider is
  confirmed on day 1 (O-12).
- **Reason:** It is fast, and on Sarj's list of preferred providers.
- **Alternatives considered:** self-hosted Whisper †; a streaming STT provider † (whether
  streaming is available and worth it is part of O-12).

### D-10 LLM: Groq or Cerebras, picked by measurement

- **Decision:** A streaming LLM with tool calls on Groq or Cerebras. The final provider and
  model are decided by experiment 4.
- **Reason:** Fast first token; both are on Sarj's list of preferred providers.
- **Alternatives considered:** Gemini (compared in experiment 4); other hosted providers †.

### D-11 Text-to-speech: Kokoro-82M as my own service

- **Decision:** The Kokoro-82M ONNX model, run with onnxruntime by our own code (D-38),
  as a separate Cloud Run service.
- **Reason:** Full control over latency and caching; it scales and is measured on its own;
  it costs compute time instead of a per-character bill.
- **Alternatives considered:** a hosted TTS, kept as the fallback for the live demo if
  Kokoro on CPU is too slow.

### D-12 Backend: Python, FastAPI, raw SQL

- **Decision:** Python with uv, FastAPI, Pydantic v2, asyncio, and psycopg 3 with raw SQL
  (no ORM).
- **Reason:** My strongest stack, and async fits streaming. Raw SQL keeps every query
  visible and explainable.
- **Alternatives considered:** an ORM such as SQLAlchemy †; a TypeScript backend †.

### D-13 Frontend: React, served by the gateway

- **Decision:** React + Vite + TypeScript + Tailwind + shadcn/ui, with HugeIcons as the one
  icon set. The gateway builds and serves it, so there is one origin.
- **Reason:** React is my strongest frontend and TypeScript matches Sarj's stack. One
  origin means no CORS and simple HTTPS mic access.
- **Alternatives considered:** Next.js †; hosting the frontend separately †.

### D-14 Identity is an anonymous cookie

- **Decision:** On first visit the server issues a random `user_id` in an HTTP-only cookie.
  There is no login; clearing cookies starts a fresh user. A "Forget me" button deletes the
  user's facts.
- **Reason:** The reviewer needs no setup.
- **Alternatives considered:** accounts and login (a non-goal); an id in `localStorage` †.

### D-15 Memory is explicit, saved through tools

- **Decision:** The LLM decides what is worth keeping and saves it with `remember_fact` or
  removes it with `forget_fact`. Only stable facts and preferences are saved, each under a
  short key, so "actually my favourite colour is blue" updates the same fact. Saved facts
  are loaded into the system prompt at the start of every session and shown in a "What
  Sarjy remembers" panel. Only the current session's recent turns go to the LLM; older
  sessions contribute their facts, not their transcripts.
- **Reason:** Memory stays visible, correctable and testable. Short prompts also keep
  latency down.
- **Alternatives considered:** saving every turn and retrieving by embedding search †;
  summarising past sessions into the prompt †.

### D-16 Database: Cloud SQL for PostgreSQL, five tables

- **Decision:** Cloud SQL for PostgreSQL on the smallest tier, with tables `users`,
  `facts` (unique on `user_id, key`, upserted with `ON CONFLICT`), `sessions`, `turns` and
  `turn_timings`.
- **Reason:** Matches Sarj's stack; `ON CONFLICT` upserts make fact updates simple.
- **Alternatives considered:** Firestore †; SQLite †.

### D-17 External APIs: SayTech and a weather API

- **Decision:** The SayTech public API (tours, prices, FAQs) and a third-party weather
  API, both exposed to the LLM as tools.
- **Reason:** A traveller's real questions are "what can I do" and "is it a good day for
  it". SayTech answers the first with a real operator's live catalogue; the weather API
  answers the second, since UAE heat decides whether a desert safari is fun or miserable.
- **Alternatives considered:** the brief's other examples (calendar, maps, transit) †.

### D-18 Five tools with small, typed results

- **Decision:** `search_tours`, `get_tour`, `get_weather`, `remember_fact`, `forget_fact`.
  Each returns a small, typed result (for example up to 5 products with name, price or
  "on request", city and link).
- **Reason:** The model reads fewer tokens and cannot invent fields.
- **Alternatives considered:** passing raw API responses to the model, measured in
  experiment 5.

### D-19 SayTech adapter rules

- **Decision:** Sarjy calls SayTech's existing public API and cleans the data in one
  tested place: a missing price (`"from": null`) becomes "price on request", never zero;
  slugs with spaces are URL-encoded; destinations are used as they are, with known
  inconsistencies noted rather than silently "fixed". Responses are cached for a few
  minutes, with a last-known-good copy if SayTech is unreachable. A new SayTech endpoint
  is built only if search is impossible without it, time-boxed to a few hours.
- **Reason:** Honest data, cleaned once, and a demo that survives a SayTech outage.
- **Alternatives considered:** fixing the data inside SayTech first †; a new search
  endpoint (only if needed).

### D-20 Light, practical conversation guardrails

- **Decision:** Scope is UAE travel, Magic Experience products, weather and the user's own
  preferences, with a short friendly redirect for anything else. Prices, availability and
  forecasts come only from tool results; if a tool fails or returns nothing, Sarjy says
  so. No booking or payment: Sarjy shares the product link.
- **Reason:** The deep dive is latency; the aim is a public demo that stays honest,
  on-topic and within budget.
- **Alternatives considered:** strict guardrails as a full deep dive, kept as optional M6.

### D-21 Protecting the public URL and the budget

- **Decision:** Rate limits per user and per IP on new turns; a maximum audio length per
  turn and a maximum number of turns per session; provider keys in Secret Manager; a GCP
  budget alert; provider dashboards checked daily. The README gives a cost-per-conversation
  estimate from measured numbers.
- **Reason:** A public demo URL with paid providers behind it must not be abusable or
  surprise anyone with a bill.
- **Alternatives considered:** a login or access code in front of the demo † (conflicts
  with "no special setup").

### D-22 Hosting: GCP Cloud Run, Terraform, GitHub Actions

- **Decision:** The gateway and web app run as one Cloud Run service; Kokoro runs as a
  second one. Images live in Artifact Registry and keys in Secret Manager. Infrastructure
  is a small Terraform module; GitHub Actions deploys through Workload Identity Federation.
  DNS stays in DigitalOcean; the `*.run.app` URL works from day 1 and `sarjy.saytech.ae`
  is a nice-to-have.
- **Reason:** One origin for the app; TTS scales and is measured on its own; no
  long-lived service-account keys.
- **Alternatives considered:** a DigitalOcean droplet (kept as the fallback); other clouds †.

### D-23 Deploy on day 1

- **Decision:** Deploy on day 1, even if the app only says hello. A budget alert sits on
  the project from the first resource. The region is chosen after checking Cloud Run
  feature support, and the region itself becomes a latency experiment.
- **Reason:** HTTPS, WebSockets and mic permissions are the biggest hidden risks, and every
  later day should build on a working URL.
- **Alternatives considered:** deploying once features are done †.

### D-24 Every external service behind an interface

- **Decision:** STT, LLM, TTS, SayTech, weather and the database each sit behind a small
  `Protocol` with one adapter. Dependencies are injected; tests use fakes, never real
  network calls. Pydantic models sit at every boundary.
- **Reason:** Tests stay fast and deterministic, and swapping a provider (needed for
  experiment 4) touches one adapter.
- **Alternatives considered:** calling provider SDKs directly from the pipeline †.

### D-25 Tests focus on the logic that can break

- **Decision:** Tests cover the SayTech adapter's data cleaning, the sentence chunker, fact
  upserts, the latency timeline, tool argument validation and rate limiting.
- **Reason:** Four days: test where bugs would hurt the demo or the numbers.
- **Alternatives considered:** a coverage target †; end-to-end browser tests †.

### D-26 Sarj's code standards from the first commit

- **Decision:** Adopt Sarj's public `code-standards` and `repo-standards` in M0, before any
  feature work. Hooks and the generated CI must pass and are never bypassed. An exception
  needs approval, goes through `code-standards exclude`, and is explained in this file.
- **Reason:** `AGENTS.md` and your instruction for M0. The PRD originally said the linter
  "runs near the end" and that deviations go in the README; it was updated to match on
  7 Oct.
- **Alternatives considered:** running the linter near the end (the PRD's original plan).

### D-27 The cut list

- **Decision:** If a day slips, cut in this order: barge-in, then the custom domain, then
  the GPU experiment.
- **Reason:** Agreed in advance, so time pressure doesn't decide what goes.
- **Alternatives considered:** none recorded.

### D-28 Non-goals

- **Decision:** No booking or payment, no accounts or login, no Arabic voice output (Kokoro
  has no Arabic voice, as far as I know; this goes in "what I'd do next"), no telephony,
  multiplayer or avatars.
- **Reason:** Four calendar days; every hour must show up in the demo, the latency numbers
  or the presentation.
- **Alternatives considered:** none recorded.

### D-29 Presentation, updates and AI use

- **Decision:** A Loom walkthrough and a short PDF go out before the meeting. Sarj gets a
  short update every day. AI is used openly, with `AGENTS.md` documenting the conventions.
- **Reason:** The brief recommends the Loom or PDF, and the rubric scores communication.
  The rule I hold myself to: nothing is merged that I can't explain line by line.
- **Alternatives considered:** none recorded.

### D-30 Python 3.14 for both services

- **Decision:** The gateway and the TTS service both run on Python 3.14 (settled 7 Oct as
  3.13, was O-01; changed to 3.14 on 8 Oct).
- **Reason:** Sarj's code-standards Python profile requires every Python project to allow
  3.14; `setup` refuses a project capped below it. 3.13 had been chosen only because
  kokoro-onnx caps itself below 3.14, and D-38 removes that library. onnxruntime, numpy,
  phonemizer and espeakng-loader all support 3.14.
- **Alternatives considered:** 3.13 for both (blocked by code-standards); the gateway on
  3.14 and TTS on 3.13 with kokoro-onnx, excluded from code-standards (an exception
  reviewers would see, two lockfiles); 3.14 with kokoro-onnx pinned to 0.4.7, its last
  release without the cap (April 2025, stale).

### D-31 One uv workspace for the Python services

- **Decision:** A root `pyproject.toml` defines a uv workspace whose members are `gateway`
  and `tts` (settled 7 Oct, was O-02). Each member uses the `src/` layout, and folder,
  service and package share a name: `gateway/src/sarjy_gateway`, `tts/src/sarjy_tts`.
  The folder was first proposed as `backend/` and renamed on 7 Oct, because the PRD and
  the code call it the gateway.
- **Reason:** One lockfile and one Python root for code-standards; each Docker image
  installs only its own member. The `sarjy_` prefix avoids clashing with an existing `TTS`
  package on PyPI.
- **Alternatives considered:** two independent uv projects; a flat layout without `src/`.

### D-32 Generator output is allowed, committed separately

- **Decision:** Output of official generators (`npm create vite`, the shadcn CLI,
  `code-standards setup`) may be committed, each in its own commit whose message says it
  is generated (settled 7 Oct, was O-03).
- **Reason:** These are the standard way to start such projects, and keeping them in
  separate commits makes it easy to tell generated code from written code.
- **Alternatives considered:** writing all boilerplate by hand.

### D-33 npm for the frontend

- **Decision:** The frontend uses npm (settled 7 Oct, was O-04).
- **Reason:** Nothing extra to install, and code-standards finds the frontend by its npm
  lockfile.
- **Alternatives considered:** pnpm.

### D-34 Public GitHub repo, one pull request per task

- **Decision:** The code lives in the public repo `ahmedel-tawil/sarjy`. The bootstrap
  commit goes straight to `main`, since a pull request needs a base branch. After that,
  every task is a branch and a pull request, and you approve each push and merge (settled
  7 Oct, was part of O-06).
- **Reason:** Standard practice: CI checks every change before it reaches `main`, and
  repo-standards' pull-request rules (up to 5 commits per pull request by default) apply.
- **Alternatives considered:** committing straight to `main`.

### D-35 Deploy through CI from day one

- **Decision:** From 8 Oct, deploys go through GitHub Actions with Workload Identity
  Federation. There is no interim deploy from the laptop (settled 7 Oct, was O-07).
- **Reason:** Do the deploy path properly once, rather than building a temporary one and
  replacing it a day later.
- **Alternatives considered:** a laptop deploy script on 8 Oct with CI on 9 Oct (proposed
  to shorten the critical path; declined).

### D-36 Node 24 LTS for the frontend

- **Decision:** The frontend builds with Node 24, pinned in `frontend/.nvmrc` and in
  `engines` in `package.json`; CI and the Docker build stage use the same major version
  (settled 8 Oct, was O-27).
- **Reason:** Node 24 is the current long-term-support line and is already installed
  through nvm. The default `node` on this Mac is 23.7, which is no longer supported
  upstream.
- **Alternatives considered:** Node 22 LTS; staying on 23.7.

### D-37 shadcn/ui with the Maia preset, ejected

- **Decision:** shadcn/ui is initialised with Radix primitives and the Maia preset, which
  sets HugeIcons as shadcn's icon library and Figtree as the font. Its base stylesheet is
  ejected into `frontend/src/styles/shadcn.css` (generated, not edited by hand), so the
  `shadcn` CLI is not a runtime dependency. Individual shadcn components are added in the
  task that first uses them (settled 8 Oct).
- **Reason:** With HugeIcons set at the source, every component we add uses the one icon
  set `AGENTS.md` allows, with no hand edits. Ejecting cuts the install from 480 to 189
  packages. Keeping the ejected CSS in its own file leaves `index.css` holding only our
  tokens.
- **Alternatives considered:** the default Nova preset with lucide icons swapped by hand
  per component; keeping the `shadcn` CLI as a dependency (no extra CSS in the repo, but
  about 290 more packages); installing HugeIcons only at first use (first planned, but the
  preset installs it).

### D-38 Our own Kokoro front end instead of kokoro-onnx

- **Decision:** The TTS service does not use kokoro-onnx. Our code turns text into
  phonemes with espeak-ng (through phonemizer and espeakng-loader), maps phonemes to the
  model's token ids, and runs the Kokoro-82M ONNX model with onnxruntime and the voice's
  style vector (settled 8 Oct).
- **Reason:** kokoro-onnx caps itself below Python 3.14, which Sarj's standards require
  (D-30). The front end is small enough to write and explain line by line, and owning it
  gives direct control over onnxruntime's session options and warm-up, which the latency
  deep dive needs.
- **Alternatives considered:** the three listed under D-30. If the front end stalls on
  day one, the fallback is the gateway on 3.14 and TTS on 3.13 with kokoro-onnx, behind
  an approved exclusion.

### D-39 pre-commit runs the standards hooks

- **Decision:** `code-standards setup --hooks pre-commit` installs two hooks: the staged
  standards check before each commit and the managed commit-message check (settled
  8 Oct in M0.4, was O-05).
- **Reason:** `AGENTS.md` names pre-commit, and it needs no extra tool: the hooks run
  code-standards through `uvx`.
- **Alternatives considered:** lefthook, which code-standards also supports.

### D-40 Rebase-merge only, and a protected `main`

- **Decision:** Pull requests land on `main` by rebase-merge only. `main` requires a pull
  request and passing Standards, Commit policy and Tests checks, with linear history, no
  force pushes, and the same rules for admins. Merged branches are deleted
  automatically, and auto-merge is allowed so a green pull request can land without
  another manual step (settled 8 Oct in M0.5, was O-06).
- **Reason:** Each small Conventional Commit stays on a linear `main`, so the history
  tells the plan, and nothing reaches `main` without CI, not even a direct push.
- **Alternatives considered:** squash-merge (one commit per task, losing the small
  commits); merge commits (noisier history); no protection (relies on discipline).

### D-41 Health checks use `/health`, not `/healthz`

- **Decision:** Every service's health endpoint is `GET /health` (settled 8 Oct in M1.3).
- **Reason:** Cloud Run reserves some URL paths ending in "z" and recommends avoiding all
  of them, so `/healthz` could be answered by Google's front end instead of our service.
- **Alternatives considered:** `/healthz`, the common Kubernetes convention.

### D-42 Logs are JSON lines from the standard library

- **Decision:** The gateway logs through Python's `logging` with a small JSON formatter:
  one line per event with `severity`, `message`, `logger` and `time`. uvicorn runs with
  `log_config=None`, so its logs use the same format, and its access log is off because
  Cloud Run already logs every request (settled 8 Oct in M1.3, was O-10).
- **Reason:** Cloud Logging parses these fields from JSON lines, and no extra dependency
  is needed.
- **Alternatives considered:** structlog; uvicorn's default text logs.

### D-43 httpx2 instead of httpx

- **Decision:** The test client uses `httpx2`, and it is the proposed HTTP client for the
  provider adapters (O-14) (settled 8 Oct in M1.3).
- **Reason:** Starlette 1.7 deprecates `httpx` for its test client and asks for `httpx2`.
  `httpx2` is maintained under the pydantic organisation by httpx's original author; the
  `httpx` package has had no stable release since 0.28.1 (December 2024).
- **Alternatives considered:** keeping `httpx` and living with the deprecation warning.

### D-44 Region: `me-central1` (Doha)

- **Decision:** Every GCP resource runs in `me-central1`, in project `sarjy-ahmed-2026`
  (settled 8 Oct in M1.1, was O-08).
- **Reason:** The closest region to Gulf users, and it supports Cloud Run (WebSockets
  included), Cloud SQL, Artifact Registry and Secret Manager.
- **Consequences:** Calls to Groq and other US-based providers cross from the Gulf to the
  US; experiment 7 measures that hop. Cloud Run domain mapping is not offered here (its
  10 regions don't include `me-central1`, and it is still in preview), so the custom
  domain (M4.7) would need a global load balancer. Cloud Run has no GPUs here, so the GPU
  experiment (M3.12) would need a second region.
- **Alternatives considered:** `europe-west1` or `us-central1`: closer to the providers,
  with domain mapping and GPUs, but further from users.

### D-45 TTS is private; the gateway calls it with its own identity

- **Decision:** The TTS Cloud Run service has no public access. Only the gateway's
  service account holds `roles/run.invoker` on it, and the gateway will send a Google ID
  token from the Cloud Run metadata server with each request (settled 8 Oct in M1.2, was
  O-09; the client side lands in M1.10).
- **Reason:** No shared secret to create, store or rotate; Cloud Run checks the token
  before our code runs.
- **Alternatives considered:** a shared secret header (one more secret to manage); a
  public TTS service (anyone could spend our compute); internal-only ingress (needs a VPC
  connector for the gateway's calls).

### D-46 CI deploys through Workload Identity Federation and one script

- **Decision:** A push to `main` runs the Deploy workflow, which exchanges GitHub's OIDC
  token for the `sarjy-deployer` service account and calls `scripts/deploy.sh`. The pool's
  provider accepts only repository ID `1409336200` on `refs/heads/main`. The deployer can
  push images, update the `gateway` and `tts` services (granted on those services, not the
  project) and act as their runtime accounts; the script changes only the image
  (settled 8 Oct in M1.5).
- **Reason:** No long-lived keys anywhere; a fork, another branch or a renamed repository
  cannot deploy. Keeping the logic in a script satisfies `workflow-embedded-program` and
  keeps the workflow readable. Branch protection means `main` only receives commits that
  passed every check.
- **Alternatives considered:** a service-account JSON key in GitHub secrets (long-lived
  credential); Cloud Build triggers (a second CI system); matching the repository by name
  (open to name reuse).

### D-47 The voice socket: binary audio, JSON control, schemas on both sides

- **Decision:** On `/ws`, audio travels as binary frames and control messages as JSON
  text frames with a `type` field. The browser streams a turn's recorder chunks, then
  sends `{"type": "turn_end"}`; the gateway answers with binary audio or
  `{"type": "error", "code": ...}`. Messages are Pydantic models in
  `gateway/src/sarjy_gateway/messages.py` and zod schemas in
  `frontend/src/lib/protocol.ts`, kept in sync by hand (settled 8 Oct in M1.4, was O-11).
- **Reason:** Binary frames carry audio without base64's 33% overhead; JSON keeps control
  messages readable. Validating both directions turns a mismatch into a clear error
  instead of undefined behaviour. Two hand-written files are small enough to keep in step
  without a code generator.
- **Alternatives considered:** everything as JSON with base64 audio (bigger, slower);
  generating TypeScript types from the Pydantic models (one more build step).

## Open decisions

Settled rows move up as D entries and their IDs are not reused, so gaps are expected.

| ID | Open decision | Options | Proposal | Settled in |
| --- | --- | --- | --- | --- |
| O-12 | STT provider and streaming (PRD open question) | Groq `whisper-large-v3-turbo` (file upload); a streaming STT provider | Groq on day 1. Check and record whether streaming is offered and worth it. | M1.7 |
| O-13 | LLM provider and model for day 1 | Groq; Cerebras | Groq (one key for STT and LLM); the final pick comes from experiment 4. | M1.8, M3.8 |
| O-14 | LLM client | httpx2 against the OpenAI-compatible API; vendor SDKs | httpx2 (D-43): one adapter for every provider, every line visible, and it is already a dependency. | M1.8 |
| O-15 | Kokoro model, voice and audio format (PRD open question on voices) | fp32 or int8 model; which voice; 16-bit PCM, WAV or Opus on the wire | Measure fp32 vs int8 on CPU; pick a voice by ear; send 16-bit PCM as binary frames. | M1.9a, M1.9b |
| O-16 | Turn-taking (PRD open question) | push-to-talk first; voice activity detection from the start | Push-to-talk first, as the PRD's architecture table says; VAD in M4.5. | settled unless you object |
| O-17 | SayTech public endpoints (PRD open question) | existing list, detail, filter and FAQ endpoints; a new endpoint if search is impossible | Use what exists; time-box any new endpoint. | M2.1 |
| O-18 | Postgres version and ID type | Postgres 18 with `uuidv7()` defaults (code-standards rule `prefer-uuidv7-default`); an older version with IDs generated in Python | Postgres 18, if Cloud SQL offers it. | M2.2, M2.3 |
| O-19 | Migrations | a small runner over numbered SQL files; a migration tool | A small runner: no dependency, easy to explain. | M2.3 |
| O-20 | Database tests | real Postgres (Docker locally, a service container in CI); fakes only | Real Postgres: upsert behaviour can only be tested against Postgres. Tests go through repository classes (`no-raw-connection-in-tests`). | M2.3 |
| O-21 | Weather provider | Open-Meteo (no key, free for non-commercial use); a keyed provider such as OpenWeatherMap | Open-Meteo. | M2.11 |
| O-22 | Where rate-limit state lives | in memory per instance, with max instances capped; Postgres | In memory, with the trade-off written down. | M2.13 |
| O-23 | Where caches live (SayTech, TTS) | in the process; Postgres; Cloud Storage | In the process for SayTech. For TTS, in the gateway or the TTS service, decided by measurement. | M2.9, M3.7 |
| O-24 | Audio for the test script | recorded by me; synthesised (Kokoro or macOS `say`) | Synthesised for repeatability, plus a few real recordings as a sanity check. | M3.3 |
| O-25 | Frontend unit tests | Vitest for pure logic (timing maths, message parsing); none | Add Vitest only if the client grows real logic. | M3.2 |
| O-26 | Voice activity detection approach | a browser VAD library (new dependency); a simple energy threshold; server-side VAD | Decide in M4.5, once push-to-talk is solid. | M4.5 |

## Approved code-standards exceptions

None yet. Each entry needs: the rule or path, the reason, who approved it, and the date.
