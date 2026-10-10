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

### D-48 Kokoro model files come from one pinned, checksummed revision

- **Decision:** The model, `tokenizer.json` (for the vocabulary) and the voice files come
  from revision `1939ad2` of `onnx-community/Kokoro-82M-v1.0-ONNX` on Hugging Face
  (Apache-2.0). `tts/model-files.sha256` lists each file's SHA-256, and
  `tts/scripts/download-model.sh` downloads and verifies them; nothing is committed. The
  front end follows the model card's documented inputs: `input_ids` padded with 0 at
  both ends, `style` = row `len(tokens)` of the voice file, `speed` (settled 8 Oct in
  M1.9a).
- **Reason:** One source for the model, vocabulary and voices, so they always match; a
  checksum turns a changed or corrupted file into a hard failure. Reading the
  vocabulary from the model's own tokenizer avoids copying a table into the repo.
- **Trade-off:** Kokoro was trained on phonemes from its own G2P library, misaki; we use
  espeak-ng, which is far lighter but may mispronounce some words. Worth listening for.
- **Alternatives considered:** the kokoro-onnx release files (tied to the library we
  dropped); hexgrad/Kokoro-82M (PyTorch weights, not ONNX); misaki for phonemes (pulls
  in spaCy and more).

### D-49 Selectable voices, `af_heart` by default

- **Decision:** Sarjy speaks with `af_heart` by default, and the traveller can switch to
  one of the other voices the TTS image carries (`af_bella`, `af_sarah`, `am_michael`,
  `am_adam`). TTS lists them at `GET /voices`; the browser picks one with a `set_voice`
  message; the choice is remembered as one of the user's facts (settled 8 Oct; you chose
  the default after listening to the samples).
- **Reason:** Personal and cheap: every request already carries a voice, a voice file is
  0.5 MB, and switching only selects a different style vector, so latency is
  unchanged. The planned TTS cache (experiment 3) must include the voice in its key.
- **Alternatives considered:** one fixed voice (simpler, less personal).

### D-50 TTS returns WAV; full precision for now; voices and languages

- **Decision:** `POST /synthesize` returns 16-bit mono PCM at 24 kHz in a WAV container.
  The image carries the full-precision model (`model.onnx`) and five American English
  voices. Kokoro offers 54 voices in 9 languages: American English 20, British English 8,
  Mandarin 8, Japanese 5, Hindi 4, Spanish 3, Brazilian Portuguese 3, Italian 2, French
  1; there is no Arabic voice (settled 8 Oct in M1.9b, was O-15).
- **Reason:** WAV is self-describing, so the gateway and the browser decode it without
  side-channel metadata, and the 44-byte header costs nothing. Full precision was faster
  than int8 on this Mac with two or more threads (1.7 s against 2.5 s for 15 words at
  2 threads); Cloud Run's x86 CPUs may reverse that, so M1.10 measures both there.
- **Alternatives considered:** raw PCM (needs the rate and format sent separately); Opus
  (smaller, but encoding costs time and adds a dependency); the int8 model (92 MB
  instead of 325 MB).

### D-51 STT: Groq `whisper-large-v3-turbo`, one clip per turn

- **Decision:** The gateway uploads each turn's whole clip to Groq's
  `/openai/v1/audio/transcriptions` with `whisper-large-v3-turbo`, `language=en`,
  temperature 0 and a short spelling prompt (Sarjy, dirhams, the emirates). The clip's
  container (WebM, MP4, WAV, Ogg) is recognised from its first bytes. The key reaches the
  gateway from Secret Manager on Cloud Run and from `.env` locally, held as a
  `SecretStr` (settled 8 Oct in M1.7, was O-12).
- **Reason:** Groq lists it as its fastest transcription model (real-time factor 216) and
  it is on Sarj's list of preferred providers. Groq's endpoint is file-based, with no
  streaming, which suits push-to-talk: the clip is complete at release. A Kokoro-spoken
  test question came back word for word in about 0.4 s from Chrome's WebM and from
  Safari's MP4. Groq bills at least 10 seconds per request.
- **Alternatives considered:** `whisper-large-v3` (more accurate, slower); a streaming STT
  provider (worth it only with voice activity detection, M4.5); self-hosted Whisper (a GPU
  we do not have in `me-central1`).

### D-52 Day-one LLM: Qwen 3.8 27B on Groq, reasoning off

- **Decision:** The gateway uses `qwen/qwen3.8-27b` on Groq with `reasoning_effort`
  `none`, temperature 0.5 and at most 300 tokens. Experiment 4 makes the final choice
  (settled 8 Oct in M1.8, was O-13).
- **Reason:** Groq offers four chat models to this account (gpt-oss 20B and 120B, Qwen
  3.8 27B, ALLaM 7B). Streaming the same question three times each from here, median time
  to the first word was 386 ms for Qwen with reasoning off, 412 ms for gpt-oss-120b on
  low reasoning, and 993 ms for gpt-oss-20b on low reasoning. Qwen also kept replies
  shortest, closest to the spoken style the prompt asks for. All three placed the Dubai
  Aquarium in the wrong mall, which is why answers must come from tools (M2).
- **Alternatives considered:** gpt-oss-120b (close on speed, longer replies); gpt-oss-20b
  (slowest first word, ignored the brevity instruction); ALLaM 7B (Arabic-focused, 4k
  context, kept in mind for "what I'd do next").

### D-53 One hand-written client for OpenAI-compatible chat APIs

- **Decision:** `OpenAiCompatibleChatModel` calls `/chat/completions` with httpx2 and
  parses the server-sent events itself (settled 8 Oct in M1.8, was O-14).
- **Reason:** Groq, Cerebras and Gemini all speak this format, so one adapter covers
  experiment 4 and a later fallback provider. The parser is about thirty lines anyone can
  read, tested against recorded real streams; vendor SDKs would add a dependency per
  provider.
- **Alternatives considered:** the `groq` or `openai` SDKs.

### D-54 Browser marks go back over the voice socket; one turn at a time

- **Decision:** When Sarjy's audio starts, the browser sends
  `{"type": "browser_marks", "turn_id", "speech_end", "playback_start"}`, both from
  `performance.now()`. The gateway checks them (a gateway-made `turn_id`, finite numbers,
  playback not before speech end) and logs the turn's TTFA; M3.1 will store them. The talk
  button only works when Sarjy is idle (settled 8 Oct in M1.12).
- **Reason:** `speech_end` is taken at release, before the gateway has named the turn, so
  the browser holds it until the audio arrives with its `turn_id`. Allowing one turn at a
  time keeps that pairing exact without a queue, and matches the gateway, which answers
  one turn at a time anyway. `playback_start` is when the first sample is scheduled; the
  device's own output delay (a few milliseconds) is not included.
- **Alternatives considered:** a separate HTTP endpoint for marks (a second path for the
  same turn); letting the user talk over Sarjy (that is barge-in, on the cut list).

### D-55 The browser drops presses with no speech before they reach Whisper

- **Decision:** The browser measures the microphone level while the talk button is held.
  A press shorter than 0.3 s, or whose loudest moment stays below -45 dBFS, is cancelled
  with a `turn_cancel` message and never transcribed. If the level cannot be measured
  (the audio context is not running), the turn goes through (settled 8 Oct in M1.14).
- **Reason:** Whisper turns silence into words. Measured against Groq on 8 Oct: 1.5 s of
  silence and 0.7 s of room noise both came back as "Thank you.", which Sarjy then
  answered. Groq gives nothing to filter on: `no_speech_prob` was 0.000 for every clip,
  and the invented "Thank you." scored the same `avg_logprob` as a real one (-0.26 and
  -0.25). Browsers suppress background noise on the microphone, so a silent room sits far
  below -45 dBFS and speech far above it. Dropping these turns in the browser also saves
  the round trip.
- **Alternatives considered:** a list of known Whisper phrases (would also drop a real
  "thank you"); voice activity detection on the server (needs an audio decoder and a VAD
  model); proper VAD in the browser, which is M4.5 and can replace this check.

### D-56 SayTech: a read-only assistant API built for Sarjy

- **Decision:** Sarjy reads Magic Experience's catalogue through three public endpoints
  added to SayTech for it (`apps/assistant/`, live 8 Oct), not through the website's
  public API (settled 8 Oct in M2.1, was O-17). The contract lives in the SayTech repo at
  `docs/api/assistant-contract-2026-10.md`.
  - **Base:** `https://magicexperience.api.saytech.ae/api/v1/public/assistant/`. GET only,
    no auth; the subdomain picks the organisation.
  - **`context/`:** the operator, cities with tour counts, categories and the site's FAQs.
    Loaded once per session into the system prompt.
  - **`products/`:** search with `q` (name words), `city`, `category`, `max_price`,
    `accessible`, `type` and `limit` (default 5, at most 20). Returns `{results, total}`.
  - **`products/<type>/<slug>/`:** one product: a plain-text summary, tickets with adult
    and child prices, children and cancellation policies, restrictions and notes.
  - **Prices:** `{currency, from_amount, on_request}`, where `on_request` is explicit and
    `from_amount` is `null` when there is no price. Website prices only.
  - **Errors:** `{"error": {"code", "message", "details"}}`, with `invalid_parameter`,
    `unknown_city` (lists the known cities), `unknown_category` (lists the known
    categories) and `not_found`. An unknown query parameter is a 400. The shared
    middleware's errors (400 no organisation, 403, 429 with `Retry-After`) are
    `{"error": "<string>"}`, so the adapter branches on the status code.
  - **Limits and caching:** 10,000 requests per hour per organisation and IP, in the
    assistant's own bucket. 200 responses carry `Cache-Control: public, max-age=300`;
    SayTech caches nothing itself. It logs `X-Request-Id`, so a slow turn can be traced.
- **Reason:** the website's public API couldn't back a voice assistant. Its category
  filter returned 500, an unknown destination returned every product, every ticket's
  price came back `null`, the helicopter's detail took 7.7 to 8.7 s, and descriptions
  were HTML with links to the API instead of the website. The PRD allowed a new endpoint
  when search is impossible without one. The new endpoints take 20 to 40 ms on SayTech's
  side (p95 under 300 ms), and 0.34 to 0.44 s per fresh request from a Mac.
- **Data kept as stored** (SayTech reports it unchanged, on purpose; prices will be
  loaded later):
  - No price: the buggy dune bashing tour (`DUNE- BUGGY`), the Dune Desert Safari, Dubai
    Parks and Resorts and both transfers return `on_request: true`. `max_price` leaves
    them out. The helicopter has 4 of 10 tickets priced, from AED 715.
  - Places: the Dune Desert Safari has no city, so no city search finds it; the Abu
    Dhabi City Tour is stored under Dubai; Sharjah has no tours.
  - Slugs keep their spaces and typos (`DUNE- BUGGY`, `Helicopter - Flight`,
    `ferrari-world-abu-dhbai`); Sarjy percent-encodes them, a space as `%20`.
  - Search doesn't filter by age: the Abu Dhabi under-400 results that scenario 1 (two
    kids) uses include an "18 years and above" Louvre ticket. Child prices and policies
    are on each ticket in the detail.
  - There is no availability endpoint, on purpose: SayTech can't yet tell "not tracked"
    from "closed". Sarjy says it can't check live dates and shares the product link.
- **Alternatives considered:** the website's public API with cleaning in Sarjy (wrong
  prices and 8-second calls can't be fixed by cleaning); reading the website's pages.

### D-57 The tool loop, and what `llm_first_token` means with tools

- **Decision:** a turn asks the model with the tools on offer, runs the tools it calls, and
  asks again with their results, for up to 3 rounds of tool calls. One more round offers
  no tools, so the model has to answer with what it has; a model still calling tools
  then fails the turn with `llm_failed`. Calls in one round run side by side. An unknown
  tool, invalid arguments, a `ToolError` or a call slower than 5 s goes back to the model
  as `{"error": "..."}` instead of failing the turn. Only the current turn's tool
  messages are sent; history keeps each turn's spoken reply. `llm_first_token` is the
  first word of the answer that is spoken, after any tool rounds (settled 8 Oct in M2.5).
- **Reason:** the mark sits on the path to the first audio, and a tool call's first token
  is never spoken. The time spent choosing and running tools then shows up between
  `stt_done` and `llm_first_token`, which is where experiment 5 (tool payload size) looks;
  each tool call also logs its own duration. Error results let the model recover in
  words ("which day?", "I can't check the weather right now"), which suits a voice call
  better than an error code.
- **Alternatives considered:** marking the first token of any round (it would hide the
  tool time inside the LLM stage); a separate mark for tools (the seven marks are fixed
  by D-04, and the per-tool log lines already give the split).

### D-58 SayTech answers are cached in the gateway, with a last known good copy

- **Decision:** each gateway process keeps SayTech's answers (the context, each search
  and each product) for 5 minutes and reuses them without asking again
  (`SARJY_SAYTECH_CACHE_SECONDS`). Older copies are kept: if SayTech is unavailable
  (timeout, network error, rate limit, server error, off-contract answer), the last good
  copy is served at any age and a warning is logged with its age. A refusal such as an
  unknown city is SayTech's real answer, so it is never cached or hidden behind an old
  copy. Each cache keeps at most 256 copies and drops the one stored longest ago (settled
  8 Oct in M2.9, the SayTech half of O-23).
- **Reason:** SayTech marks its answers cacheable for 5 minutes, and prices change rarely.
  A cache hit costs nothing, against 160 ms to 2 s for a call. The PRD's risk table names
  SayTech being down during review, and a stale price with a working demo is better
  than no answer. Each Cloud Run instance has its own cache; with at most two instances
  that costs at most one extra call per question.
- **Alternatives considered:** Postgres or Cloud Storage (shared between instances, but a
  network call each time, for data that is already one call away); no cache (every
  turn pays SayTech's latency and every outage reaches the traveller).

### D-59 Tool results and arguments shaped for the model and for Groq

- **Decision:** tool results leave out empty fields, and a tour's children's and
  cancellation policies are stated once (`every_ticket`) when every ticket shares them,
  which is the usual case. Tool arguments avoid names the model confuses with JSON
  Schema keywords: `get_tour` takes `slug` and `product_type` (default `tour`), not
  `type`. An error that a provider sends inside the stream is reported with its own
  message (settled 8 Oct in M2.10).
- **Reason:** every request of a turn resends all tool results, and Groq's free tier
  allows 8,000 tokens a minute (D-61). The buggy's nine tickets repeated the same two
  policies, so its details went from 5.3 KB to 2.1 KB (SayTech's raw answer is 7.9 KB);
  the helicopter's from 8.7 KB raw to 2.9 KB. With an argument named `type`, Qwen
  sometimes wrote `true` for it; Groq checks tool calls against their schema and rejected
  those turns mid-stream with `tool_use_failed`, two runs in four. After the rename,
  none in the following runs.
- **Alternatives considered:** retrying a rejected round (costs a second or more, and
  hides the cause); dropping fields the model might need, such as the summary.

### D-60 Weather: Open-Meteo, a fixed table of UAE cities, days in UAE time

- **Decision:** `get_weather(city, date)` reads Open-Meteo's forecast, which needs no key
  and is free for non-commercial use. Cities come from a fixed table of UAE coordinates,
  matched however they are written ("abu-dhabi", "ABUDHABI"), with no geocoding call.
  Days and hours are UAE time, a fixed UTC+4 with no daylight saving, so the container
  needs no time zone database. The tool checks the date itself: today to 15 days ahead,
  Open-Meteo's range, with "today" taken in the UAE. A day gives conditions, high, low,
  chance of rain, and temperatures at 6, 9, 12, 15, 18 and 21 o'clock (settled 8 Oct in
  M2.11, was O-21).
- **Reason:** scenario 3 needs the afternoon's temperature and a cooler time to suggest,
  not just a daily maximum. Checking the range before the call explains a bad date in
  words ("forecasts cover 8 to 23 October") and costs no request. A traveller's
  "tomorrow" is the UAE's tomorrow even when it is still today in UTC.
- **Alternatives considered:** a keyed provider such as OpenWeatherMap (one more secret,
  no gain for a demo); Open-Meteo's geocoding API (a second call per question, and it
  could match a place outside the UAE).

### D-61 A second LLM provider for when Groq's free tier runs out (replaced by D-63)

- **Decision:** when Groq answers 429 at the start of a request, the same request goes to
  a second OpenAI-compatible provider, Cerebras, which also has a free tier. Sarj's
  higher-limit keys replace this if they arrive (settled 8 Oct, was O-28; built in
  M2.15). The question was first filed as O-27 by mistake: that ID belongs to D-36.
- **Reason:** every Groq free-tier model allows 8,000 tokens a minute (checked on 8 Oct
  for Qwen 3.8 27B and both gpt-oss models), and a turn with tools uses 2,000 to 4,000,
  so two or three tool turns a minute hit the limit; it happened three times on 8 Oct.
  The chat client is already provider-neutral (D-53), so a second provider is settings
  plus a small fallback wrapper, and experiment 4 compares providers anyway.
- **Alternatives considered:** Groq's paid Developer tier (costs money on my account);
  waiting for Sarj's keys alone (the demo depends on a reply).

### D-62 Prompt v1: the no-guessing rule first, defaults in code, context during STT

- **Decision:** the system prompt opens with its most important rule: Sarjy knows no
  tours or prices of its own, and calls `search_tours` before naming any, bookings
  included. Then come the speaking style, the scope, and the tool rules (details only when
  needed, ages for families, a cooler time when it's hot, no booking or live dates).
  SayTech's context follows, with categories framed as things to search by, then today's
  date. The prompt is rebuilt every turn, and its SayTech part is fetched through the
  cache while the speech is transcribed. A default that matters, such as Dubai when no
  city is named, is set in the tool's code as well as in the prompt (settled 9 Oct in
  M2.12).
- **Reason:** in the first test, with the no-guessing rule further down and the catalogue
  listing cities and categories, the model answered scenario 1 and a booking request
  with invented prices and no tool call. Moving the rule to the top fixed both. Told to
  assume Dubai, it still picked Abu Dhabi three times in a row; saying in the opening
  lines that travellers mean Dubai fixed it, and the tool's default protects the rest.
  Fetching the context alongside STT hides a cache miss behind the transcription.
- **Alternatives considered:** forcing a tool call every turn (`tool_choice: required`,
  which breaks greetings and off-topic replies); checking spoken numbers against tool
  results in code (the optional guardrail milestone, M6).

### D-63 Groq and Claude Haiku 5.5, switchable, each the other's fallback

- **Decision:** Sarjy has two chat providers: Groq's Qwen 3.8 27B through the
  OpenAI-compatible client (D-53), and Claude Haiku 5.5 (`claude-haiku-5-5`) through
  Anthropic's official Python SDK, behind the same `ChatModel` interface.
  `SARJY_LLM_PRIMARY` (on Cloud Run the Terraform variable `llm_primary`) says which
  answers first. If it fails before its first word (rate limit, refused or deactivated
  key, server or network error), `FallbackChatModel` sends the same request to the other;
  once words have arrived nothing switches. Claude runs with thinking off and effort
  `low`: thinking would delay the first word, and its blocks would have to travel back
  with every tool result through a message shape that has no place for them. Temperature
  is not sent, since Haiku 5.5 only takes its default, and the SDK's own retries are off,
  so the other provider answers at once instead (settled 9 Oct in M2.15; replaces D-61's
  Cerebras).
- **Reason:** Ahmed has $100 of Anthropic API credit, valid to 8 November, and reviewers
  use the deployed app, so no reviewer needs a key. Claude's rate limits are far above
  Groq's free tier (8,000 tokens a minute), so either order survives a busy demo, and
  deactivating the Claude key later just leaves Groq on its own. Anthropic recommends its
  SDK over its OpenAI-compatible endpoint; the SDK runs on httpx2, which the gateway
  already uses. Haiku is the fastest Claude to a first word, which is what a voice turn
  waits for. Measured on 9 Oct from a Mac: with tools, Claude's first word came after 2.7
  to 3.5 s, Groq's after about 1.5 s, so Groq stays first by default.
- **Alternatives considered:** Cerebras (D-61; another free tier to sign up for, while
  credit was already in hand); Anthropic's OpenAI-compatible endpoint (settings only, but
  Anthropic advises against it for production); Claude Sonnet 5.5 or Opus 5.5 (stronger
  but slower to the first word; Opus cannot turn thinking off). The API key must belong to
  a workspace: an organisation-level key is refused without a workspace header.

### D-64 Postgres 18 on the smallest Cloud SQL tier, reached through Cloud Run's socket

- **Decision:** one Cloud SQL for PostgreSQL 18 instance, `sarjy`, on `db-f1-micro`
  (shared core, Enterprise edition, which Postgres 16 and later need asked for by name),
  zonal, 10 GB, deletion protection on, no backups. The gateway reaches it through Cloud
  Run's built-in Cloud SQL connection: a Unix socket under `/cloudsql`, through the Cloud
  SQL Auth Proxy, authorised by the gateway's identity (`roles/cloudsql.client`). The
  instance has a public address but no authorised networks, so nothing else can
  connect. The connection URL, password included, sits in the `database-url` secret; the
  database user and that value are created by hand, so the password never passes
  through Terraform. Locally, `docker compose up db` runs the same major version. A
  psycopg pool of up to four connections opens at startup without waiting, so voice
  works even when the database doesn't, and `GET /ready` proves the connection with
  `SELECT 1` (settled 9 Oct in M2.2, with O-18).
- **Reason:** the data is small (facts, sessions, turns, timings), so the cheapest tier
  is enough, at about $10 a month. Postgres 18 has `uuidv7()` built in, which Sarj's
  `prefer-uuidv7-default` rule asks for (M2.3). The socket needs no VPC, connector or
  firewall rules. Keeping voice independent of the database means a database outage
  costs memory, not the whole demo.
- **Alternatives considered:** a private IP with a Serverless VPC connector (more
  infrastructure for no gain here); IAM database login (Cloud Run's socket doesn't do it,
  and the Python connector that does doesn't support psycopg); a larger tier or
  backups (cost, for demo data); Terraform-generated passwords (they would sit in the
  state file).

### D-65 Schema, migrations at startup, and tests on a real Postgres

- **Decision:** the schema lives in numbered SQL files inside the gateway package
  (`sarjy_gateway/migrations/`), so the image carries it. A `turns` row is one exchange:
  the transcript, the reply and the turn's tool results, under the pipeline's turn id,
  which `turn_timings` refers to. `MigrationRunner` applies pending files in name order,
  all in one transaction, under a Postgres advisory lock, and records each in
  `schema_migrations`, which it creates in a transaction of its own first. It runs at
  gateway startup; a failure is logged and voice carries on. Mark names are checked by
  the typed Python models that write them, not by a database `CHECK`. Tests run against
  a real Postgres through the runner and, later, the repository classes, never raw SQL:
  a `sarjy_test` database in the local container, a Postgres 18 service in CI, failing
  rather than skipping in CI without one (settled 9 Oct in M2.3, were O-19 and O-20).
- **Reason:** the PRD's one-row-per-speaker shape had no single row for a turn's latency
  marks to belong to, while the pipeline already has one id per exchange. A runner of
  about forty lines needs no dependency and is easy to explain; one transaction and the
  lock make a half-applied schema or two racing instances impossible. Migrating at
  startup needs no separate job or CI access to the database. Upserts and constraints
  only behave as in production on Postgres itself.
- **Alternatives considered:** a migration tool such as Alembic (a dependency and its own
  concepts); a Cloud Run job or CI step for migrations (more infrastructure); fakes only
  for database tests.

### D-66 Identity by cookie, one session per visit, turns saved after they are spoken

- **Decision:** any response to a browser without a valid `sarjy_user` cookie, normally
  the page load, sets one: a new random user id (UUIDv7), HTTP-only, Secure, SameSite=Lax,
  for 400 days, the longest browsers allow. The cookie holds only the id, which works
  like a session token: knowing it is what makes a browser that user. The voice socket
  refuses a browser without it (HTTP 403 at the handshake). Each socket connection is a
  visit: the user is upserted (`last_seen_at` refreshed) and a session added, in one
  transaction. Each completed turn is saved after its audio and marks have been sent, so
  saving never delays a reply. If the database is unavailable, the visit and its turns
  go unrecorded with a warning and the conversation carries on. `SARJY_COOKIE_SECURE=false`
  lets browsers that refuse Secure cookies on plain-HTTP localhost keep it locally
  (settled 9 Oct in M2.4).
- **Reason:** the PRD has no accounts, so the browser is the user; every tab and later
  visit from it shares the same facts, while each tab keeps its own short conversation
  (D-65). Refusing cookieless sockets means every conversation belongs to a user, which
  rate limits per user (M2.13) rely on. Voice matters more than history, as with
  `/ready` (D-64).
- **Alternatives considered:** a signed cookie (another secret to manage, for an id that
  is already unguessable); setting the cookie in the socket handshake (scripts without a
  page could then talk freely); accounts and login (outside the PRD).

### D-67 Memory: facts per user, tools per visit, the prompt kept current in memory

- **Decision:** a fact is a key and a value per user, one row per key, so saying it again
  replaces it. `remember_fact` and `forget_fact` are created for each visit, bound to
  its user and conversation; every turn's toolbox is the shared tools plus these. The
  visit loads the user's facts once when it starts, the tools update that copy after
  each save or forget, and every turn's prompt lists the facts with their keys from it,
  so no turn reads the database for them. Keys are normalised to lower case with
  underscores. User, session and turn ids are distinct types (`UserId`, `SessionId`), so
  they can't be passed in each other's place (settled 9 Oct in M2.6).
- **Reason:** scenario 2 needs facts across visits and the PRD wants explicit memory,
  where the model decides what is worth keeping. Showing the keys lets "actually, it's
  blue" reuse `favourite_colour` without fuzzy matching. Binding the tools to the visit
  keeps one user's tool from touching another's facts by construction. A fact saved
  this turn is in the next turn's prompt without a query.
- **Alternatives considered:** passing a context argument to every tool (all tools would
  carry an argument only two use); reading facts from the database every turn (a query
  on every turn for data the visit already has); free-text memory without keys (no
  clean way to update one fact).

### D-68 Memory panel: the whole list over the socket, opened with the page

- **Decision:** The page opens its WebSocket as soon as it loads. The gateway sends a
  `memory` message with all of the user's facts when the visit starts and after every
  save or forget, always the full list sorted by key. "Forget me" is a `forget_me`
  message on the same socket, sent after a confirmation dialog: the gateway deletes the
  user's facts, empties the visit's copy and sends an empty list, or `forget_failed` if
  the database is down. As the PRD says, it deletes facts only; sessions and turns stay.
  The button waits while a turn runs (settled 9 Oct in M2.7).
- **Reason:** The visit owns the copy of the facts its prompts use (D-67), so forgetting
  has to go through it: deleted over HTTP, the open visit would keep using them. The full
  list keeps the page free of merging logic, and it is a handful of rows. Opening the
  socket with the page fills the panel before the first question, and takes the
  WebSocket handshake out of the first turn's latency.
- **Trade-off:** another tab of the same browser sees a change only when it reconnects,
  and an idle tab holds its socket until Cloud Run's 60-minute request timeout.
- **Alternatives considered:** HTTP endpoints to read and delete facts (the open visit
  would not hear about it); sending only the changed fact (merging in the page for a
  tiny list); opening the socket on the first press, as before (an empty panel until
  then).

### D-69 Claude answers first for now

- **Decision:** On Cloud Run, Claude Haiku 5.5 answers first and Groq's Qwen is the
  fallback: the Terraform variable `llm_primary` defaults to `claude`. Locally the
  setting still defaults to `groq`; set `SARJY_LLM_PRIMARY=claude` in `.env` to match.
  Experiment 4 (M3.8) revisits the choice (settled 9 Oct, was O-30).
- **Reason:** Scenario 2 needs the model to save a fact the traveller mentions in
  passing. With "My favourite colour is green, and I don't like heights." through the
  real pipeline, Claude saved both facts in 3 of 3 tries. Qwen said "I've noted that"
  without calling `remember_fact` in 7 of 7; two firmer prompt wordings saved in 1 of 6,
  and thinking on in 1 of 3. Asked "Please remember that…", Qwen saved both in 3 of 3, so
  it can call the tool but doesn't decide on its own that a remark is worth keeping.
  gpt-oss-120b on Groq saved the colour every time and the heights never.
- **Consequences:** the first word comes after about 2.7 to 3.5 s on tool turns instead
  of about 1.5 s, which the latency deep dive reports. Claude spends the $100 Anthropic
  credits (valid to 8 Nov 2026), and its key expires in 30 days; once it does, Groq takes
  over through the fallback, with Qwen's weakness at saving.
- **Alternatives considered:** keeping Qwen first and asking demo users to say "Please
  remember" (fragile); gpt-oss-120b (saves only some facts); a second, background model
  call after each reply that extracts facts (keeps Qwen's speed, but adds code, a call per
  turn, and departs from the PRD's tool-based memory; a possible later improvement).

### D-70 TTS on 8 vCPU, still scaling to zero

- **Decision:** The TTS service runs on 8 vCPU and 4 GiB with `SARJY_THREADS=8`, at most
  two instances and none when idle. The service-level instance limit is set to 2 in
  Terraform as well (settled 9 Oct in M2.17; D-72 lowers both limits to one instance,
  after two per revision made a deploy exceed the quota).
- **Reason:** Timed directly on Cloud Run, synthesis got faster at every step: the
  60-word reply from the 9 Oct screenshot took 14.0 s on 2 vCPU, 9.0 s on 4 and 6.3 s
  on 8; a 13-word sentence 3.7, 2.7 and 2.1 s. Scaling to zero means we pay only while
  synthesising, under a cent per reply at any size. Google gives a new service a limit
  of 3 instances, and Cloud Run checks it times the vCPUs per instance against the
  region's 20-vCPU quota, so 8 vCPU was refused until that limit came down to 2.
- **Trade-off:** TTS can now use 16 of the 20 vCPU in `me-central1` and the gateway 3, so
  a bigger gateway would need a quota increase. Keeping an 8-vCPU instance warm would
  cost roughly $17 a day (Tier 2 rates, unconfirmed); M3.10 decides that.
- **Alternatives considered:** 4 vCPU (half the speed-up); a GPU (M3.12, not on the
  free trial); keeping 2 vCPU and relying on sentence streaming alone (M3.5 still comes;
  both shorten the wait).

### D-71 Prompt v1.1: names, weather only from the tool, under fifty words

- **Decision:** Prompt v1 gains three rules. Memory: save lasting facts "even in
  passing", with the traveller's name among the examples, and call them by name.
  Weather: never describe the weather, temperature or season unless `get_weather`
  returned it in that turn. Style: every reply under fifty words, three tours at most,
  and the "can't book, see the website" line only when the traveller asks (settled 9 Oct
  in M2.18).
- **Reason:** On the deployed URL Claude skipped "my name is Ahmed", said a helicopter
  flight was "a great choice for cool, clear skies" in October without a forecast, and
  spoke 60 words, which TTS then took 12.8 s to synthesise. With the same three
  questions through the real pipeline, before and after: the name was saved in 5 of 5
  runs after, against 0 of 2 before; replies fell from 56 to 89 words to 36 to 55; and
  the booking line stopped closing every answer. Scenario 2 still saved both facts in 3
  of 3.
- **Trade-off:** "I like winter more", said inside a question, was saved in none of 5
  runs; the model treats it as part of the question. One reply still called winter "a
  lovely time for outdoor fun", a general remark rather than a claim about today.
- **Alternatives considered:** checking spoken weather against tool results in code (the
  optional guardrail milestone, M6); a tighter token limit (cuts replies off mid-sentence).

### D-72 Turn limits in memory, per user and per IP, counted per instance

- **Decision:** Before each turn runs, the gateway checks three limits: 30 turns per user
  and 90 per IP in any ten minutes (a sliding window), and 100 turns per visit. All four
  numbers are settings. The counts live in each instance's memory; the gateway runs at
  most two instances, now capped at the service level too. The visitor's IP is the last
  entry of `X-Forwarded-For`, which Cloud Run's front end appends; without the header
  (locally) it is the socket's peer. A refused turn costs nothing and gets its own error
  code, `too_many_turns` or `visit_limit`, with a friendly message (settled 9 Oct in
  M2.13, was O-22).
- **Reason:** A spoken turn takes at least twenty seconds, so a person stays well under
  thirty in ten minutes, and an IP has room for a few people behind one router. The IP
  limit stops a bot that clears its cookie; the visit cap stops a runaway client. Memory
  needs no table or extra round trip on the turn path, and with two instances a visitor
  gets at most twice the limit. Earlier entries of `X-Forwarded-For` come from the
  client and can be forged, so only Cloud Run's own entry is trusted, the same choice as
  Flask's `ProxyFix(x_for=1)` on Cloud Run.
- **Instance caps:** the gateway runs at most two instances, TTS one. On 9 Oct a TTS
  deploy failed its startup check after four minutes: the old revision still had a warm
  8-vCPU instance and the new one tried to start two, 24 vCPU against the region's 20,
  so the new instances were never placed. With one each, a deploy needs at most 8 + 8
  for TTS and a few for the gateway. One TTS instance serves up to four syntheses at
  once, which share its eight threads.
- **Trade-off:** counts reset when an instance restarts or a deploy rolls out. If Cloud
  Run ever added a proxy address after the visitor's, every visitor would share one IP
  key; the visible symptom would be `too_many_turns` for everyone at once.
- **Alternatives considered:** counts in Postgres (shared and durable, but a write on
  every turn for a two-instance demo); a fixed one-minute window (a burst at the boundary
  gets twice the limit); a login or access code (D-21 rejects it).

### D-73 TTS images tagged by what they are built from; five versions kept

- **Decision:** `scripts/deploy.sh` tags the gateway image with its commit, as before,
  and the TTS image with `inputs-` and a fingerprint: the hash of the git listing of
  `tts/`, the workspace's `pyproject.toml`, `uv.lock`, `gateway/pyproject.toml` and
  `.dockerignore`. Before building, the script stops if the service already serves that
  image from a successful deploy, and skips the build if the registry already has it.
  Artifact Registry keeps the five newest versions of each image and deletes the rest
  (settled 9 Oct in M2.16).
- **Reason:** every merge rebuilt and pushed a 420 MB TTS image and rolled out a new TTS
  revision, though TTS rarely changes: 48 images by 9 Oct, and one rollout failed on the
  CPU quota (D-72). A fingerprint of the files the image is built from is the same for
  every commit that leaves them alone, so the decision needs no knowledge of which
  commits a push contains, and a re-run or a skipped deploy still does the right thing.
  Five versions leave a few deploys to roll back to.
- **Alternatives considered:** a job that diffs the push's changed files and runs the TTS
  deploy only when a TTS path changed (needs the previous commit, which a first push or
  a force push lacks); a path filter action (another third-party action to pin); keeping
  images by age instead of count (a quiet week would delete the only good image).

### D-74 Timings in Postgres for every turn, runs as JSON Lines files

- **Decision:** the gateway saves its five marks with each turn and the browser's two
  when `browser_marks` arrives, all in `turn_timings`; an insert only lands for a turn of
  the same visit, and a mark already stored is kept. A labelled run is a JSON Lines file
  in `docs/latency/runs/`, one turn per line with both clocks' marks, written by the
  experiment harness; `gateway/scripts/latency.py` prints p50 and p95 per gap from it.
  Gaps never mix clocks, and percentiles use the nearest rank (settled 9 Oct in M3.1).
- **Reason:** storing every turn keeps real visits measurable later, while the runs the
  deep dive reports on need no access to Cloud SQL from a laptop, which has no
  authorised networks and would need the Cloud SQL Auth Proxy. Run files committed with
  the docs let anyone recompute every number in `LATENCY.md`. Tying a mark to its
  session stops a browser from writing into another visit's turns.
- **Alternatives considered:** a run label stored on the session and a summary query over
  Cloud SQL (needs the proxy, and a column for one script); an HTTP endpoint for the
  summary (a public surface for an internal tool); interpolated percentiles (report
  values nobody measured).

### D-75 A synthesised script, played by a harness that stands in for the browser

- **Decision:** the latency script is ten questions stored as WAV clips spoken by Kokoro's
  `am_michael` voice, with their text in `script.json`. A Python harness plays the whole
  script over the gateway's WebSocket, one visit per repetition with a fresh identity:
  it streams each clip at its spoken pace, marks `speech_end` when the clip ends and
  `playback_start` at the reply's first audio byte, sends `browser_marks` like the page,
  writes the run to `docs/latency/runs/<label>.jsonl` (never over an existing run), and
  prints the M3.1 table. Each visit forgets its facts at the end (settled 9 Oct in M3.3,
  was O-24).
- **Reason:** the same audio every run is what makes runs comparable; a recording of a
  person would vary with the microphone and the room, and none of Ahmed's voice goes into
  a public repository. Pacing the upload like a held button keeps `speech_end` honest.
  The harness reports what it can measure itself and says in `LATENCY.md` how a browser
  differs.
- **Alternatives considered:** recorded questions (not repeatable, and personal);
  driving the real page in a headless browser (closest to a user, but needs a fake
  microphone and a browser automation dependency); sending each clip at once (would
  count the whole upload after `speech_end`).

### D-76 Sentence streaming: every written sentence spoken in order, tools first

- **Decision:** in `sentence` mode (`SARJY_PIPELINE_MODE`), the model's text is split
  into sentences as it streams; each complete sentence passes the per-sentence step and
  goes to TTS at once, one at a time, and each clip is sent with an `audio` message
  carrying the words it speaks. Text written before a tool call is spoken too, while the
  tool runs. The reply is everything spoken, sent after the last clip, and is what the
  history keeps. The prompt now asks the model to call any tool before writing anything.
  `baseline` stays the default until the page queues clips (settled 9 Oct in M3.5).
- **Reason:** first audio should wait for one sentence, not the whole reply; TTS was 48%
  of the baseline's TTFA and grew with the reply. A sentence can't be taken back once it
  is spoken, and a round is only known to end in a tool call when it ends, so text before
  a tool can't be held without losing the gain. In a local trial without the new rule,
  Claude named tours before searching ("Ferrari World and Warner Bros. World are good
  choices") and the next turn misread its own "I'll remember that" as an unkept promise;
  with the rule, only short fillers such as "I'll check tomorrow's weather" remained.
  Sentences go to TTS one at a time because Kokoro on 8 vCPU synthesises faster than it
  speaks, and order then needs no bookkeeping.
- **Trade-off:** a filler before a tool counts as first audio, which is what the user
  hears, so TTFA improves more than the answer itself does; `LATENCY.md` notes it. If the
  model ignores the rule, words written before a tool are spoken unchecked.
- **Alternatives considered:** holding each round's sentences until it is known not to
  call a tool (no gain on the rounds that matter); speaking only the last round and
  dropping the rest (needs the model to say which round is last); synthesising sentences
  in parallel (faster on long replies, but order and CPU sharing to manage).

### D-77 The page plays sentence clips back to back; sentence mode by default

- **Decision:** the player schedules each clip on the audio context's clock for the
  moment the previous one ends, decoding clips in the order they arrived; a turn ends
  once the gateway's `marks` message has come and the last clip has played. The session
  reports each clip as it starts through an optional `onSpeak(text, durationMs)`, keeps
  `onReply` for the whole reply (shown with the first clip, or on arrival once a clip is
  playing), and offers `inputLevel()` and `outputLevel()` from 0 to 1, read from the
  microphone's meter and an analyser on the player's output. `sentence` becomes the
  gateway's default, and Terraform's `pipeline_mode` sets it on Cloud Run (settled 9 Oct
  in M3.6).
- **Reason:** scheduling on the audio clock rather than starting each clip when the
  previous one's "ended" event fires leaves no gap between sentences, and no clip can
  start while another plays. The UI session asked for the sentence text, its duration and
  the two levels, to show words as they are spoken and animate the voice; Kokoro gives no
  word timings, so the page spreads a sentence's words across its duration. With the page
  ready, there is no reason to keep the slower mode as the default; the switch stays for
  comparisons.
- **Alternatives considered:** starting each clip on the previous one's `ended` event
  (a small gap each time, larger on a busy phone); joining clips into one growing buffer
  (more code, and a clip arriving late still stalls); word timestamps from TTS (Kokoro
  has none).

### D-80 Sarjy's identity: a voice-trail mark, a talk orb, three palettes

- **Decision:** Sarjy's mark is an S traced by eleven dots that grow like a voice, the
  last in the accent colour, beside a lowercase "sarjy" in Figtree. The talk control is a
  sphere of dots drawn on a canvas: hold it (or Space) to talk; it ripples with the
  microphone, sweeps a band of light while thinking and pulses while speaking. One screen
  holds the visit's conversation, set like a script, with Sarjy's reply appearing word by
  word as it is spoken; the memory panel (saved facts fly from the orb onto it) and the
  latency panel (the last five turns, where M3.2's waterfall goes) sit beside it on a
  laptop and behind a "Remembers" button on a phone. The colours come in three palettes in
  `index.css`, Pearl, Night and Coral, switched by `data-palette` on `<html>`, chosen with
  three swatches and kept in the browser; a system in dark mode starts in Night. Every
  visit opens with a welcome of about two seconds: the trail draws itself, its name
  appears, then the trail gathers, flies to the talk control and the orb grows out of it.
  A tap skips it, and under reduced motion the page simply appears. The motion rule in `AGENTS.md` now reads: transitions take at most
  300 ms; continuous motion only when it shows something real (a voice level or Sarjy's
  state), plus this welcome. The favicon, light or dark with the browser, was exported
  from the design board, so its colours live in image files, not in code. In development, `?rehearse` plays scripted
  turns without a gateway (settled 9 Oct in M4.1).
- **Reason:** A first plan of two columns of cards and a round mic button looked like
  every voice app, and a desert scene made Sarjy look like a safari seller rather than a
  concierge for every UAE activity. Orbs are common in voice products, so the brand lives
  in the mark and in the moment the mark becomes the orb. Keeping the conversation on
  screen serves the demo scenarios, which ask about earlier turns. Tokens under shadcn's
  own names keep every shadcn component right in each palette. A plain Canvas 2D drawing,
  with no new dependency, keeps every line explainable.
- **Timing:** Sarjy's words follow its voice through `onSpeak(text, durationMs)`, one
  clip per sentence (D-77): each sentence's words are spread across its audio, longer
  words taking longer, revealed by CSS delays rather than timers; the full `onReply` text
  shows only when the voice never played. The orb reads the session's `inputLevel()`
  while listening and `outputLevel()` while speaking, so the page opens no microphone of
  its own.
- **Trade-off:** the orb redraws every frame while the tab is visible; the welcome costs
  every visit two seconds unless tapped away; words are timed by their length, not by
  Kokoro, so a long pause inside a sentence runs ahead; three palettes mean three sets of
  colours to check for contrast in M4.8.
- **Alternatives considered:** dunes that answer the voice (too literally desert); a
  lattice of light; a screen of type alone; one palette; a Three.js or WebGL orb such as
  ElevenLabs UI's or LiveKit's Aura (new dependencies, and harder to explain); copying the
  21st.dev "thinking orb" component Ahmed found (MIT, but `AGENTS.md` asks for code
  written from scratch, so only its ideas were reused: the pill becoming a ball, the
  dotted sphere, the blurred word reveal).

### D-78 Cold starts: TTS woken when a visit opens; warm instances a setting

- **Decision:** when a visit's socket opens, the gateway asks TTS for its voices in the
  background, which starts a TTS instance while the page loads and the traveller speaks;
  a failure is only logged. The minimum instance counts of the gateway and TTS are
  Terraform variables (`gateway_min_instances`, `tts_min_instances`), 0 by default and 1
  for the review week (settled 9 Oct in M3.10).
- **Reason:** both services scale to zero. Measured on 9 Oct: a turn that met a cold TTS
  waited 11.8 s for its first audio against 4.7 s warm for the same question, because the
  TTS instance took about 6 s to start (2.4 s for the container, 3.3 s to load and warm
  the model) before synthesising; and the gateway takes 7 to 10 s from instance start to
  serving (about 9.5 s typically, 8.8 s of it before the server process starts), so a
  cold visitor waits that long for the page itself. The page opens its socket as it loads
  (D-68), and a traveller takes several seconds to read and ask, which hides most of
  TTS's start. A warm instance removes a cold start entirely: idle, a minimum instance is
  billed at the idle rate, in Tier 2 about $0.0000035 per vCPU-second and per GiB-second,
  so about $0.45 a day for the gateway and $3.60 a day for TTS (D-70's $17 used the
  active rate). Variables make the review-week setting one value to set and to undo.
- **Alternatives considered:** a scheduled ping every few minutes (another service, and
  Cloud Run may still retire an idle instance); warm instances all the time (about $120 a
  month, mostly TTS); a faster gateway start (smaller image, lazier imports; worth doing,
  but warm instances solve the review week now).

### D-79 The waterfall: each turn's stages from both clocks, in the latency card

- **Decision:** the page computes a turn's stages once it has both the gateway's marks
  and its own time to first audio, with the same gaps as `LATENCY.md` (speech to text,
  first word, first sentence, voice, and the network as what is left), and reports them
  through an optional `onStages`. The "How fast Sarjy answered" card draws the last five
  turns as bars on one scale, each split into its stages in the palette's chart colours,
  with the last turn's values in a legend and each bar labelled for screen readers
  (settled 9 Oct in M3.2).
- **Reason:** the demo should show where a turn's time went, live, as `LATENCY.md` does
  for a run. The two clocks only agree on durations, so the page combines the gateway's
  gaps with its own TTFA rather than comparing timestamps. One scale makes turns compare
  at a glance; the chart tokens keep the stages distinct in every palette.
- **Alternatives considered:** a waterfall that offsets each stage on a timeline (the
  stages already follow one another, so a stacked bar shows the same thing in less
  space); the gateway sending stages itself (it can't know the browser's playback start);
  a chart library (a new dependency for five coloured spans).

### D-90 Tour links beside the reply, a remembered voice, and reconnecting

- **Decision:** with each reply the gateway sends the pages of the tours it names, taken
  only from that turn's tool results: a tour counts as named when the reply contains two
  of its distinctive words, or its only one ("Louvre"), and links come in the order the
  reply names them. A voice picked with `set_voice` is saved as the user's `voice` fact,
  pushed to the memory panel, and applied when their next visit starts. The page's socket
  reopens by itself after an unexpected close, after 1, 2, 4 and then every 10 seconds,
  only while the tab is visible, and reports `connecting`, `online` or `offline`. The
  page reads voices through `VoicesClient`, with a 5-second timeout (settled 9 Oct, for
  the UI session's M4.2 and M4.9).
- **Reason:** Sarjy never says a web address (prompt v1), yet M4.2 wants its tours
  clickable, so the links travel beside the words; taking them only from tool results
  means no link is ever invented. Two distinctive words keep "World" from linking Ferrari
  World when the reply named Warner Bros. World. A fact is already where a user's
  preferences live and what "Forget me" deletes. Reconnecting only in a visible tab keeps
  a forgotten tab from holding the gateway open all night, since an open socket is an
  active request on Cloud Run.
- **Alternatives considered:** asking the model to list the tours it named (another
  round, and it can still be wrong); linking every tour the search returned (noise); a
  voice column on users (a schema change for one setting); reconnecting in hidden tabs
  too (the cost above).

### D-81 Problems shown where they belong; links and a dropped connection on screen

- **Decision:** every problem the page can hear has a kind, kept in one table
  (`components/problems.ts`). A slip of the hand (no speech, too long) is a quiet hint
  under the orb. A question that was heard but not answered (the model, the connection or
  our side failed) gets a note on that turn in the conversation, and a reply whose voice
  failed is shown in writing with a note. A denied microphone and a full visit get a
  shadcn Alert above the orb: the first says how to allow the microphone and clears on the
  next press, the second has a "Start a new visit" button and disables the orb. Rate
  limits and anything else show under the orb in the error colour. When a connection that
  was up drops, the header says "Reconnecting…" and the orb waits until the socket is
  back (D-90), then "Back online" shows for 2.5 s; the first connection as the page opens
  says nothing. The tours a reply named appear under it as outline buttons that open
  their pages in a new tab. The empty conversation shows how to talk, three questions
  from the demo scenarios, and that the browser will ask for the microphone. In
  development, `?rehearse=problems` plays each failure in turn (settled 9 Oct in M4.2).
- **Reason:** one red line for every problem made a denied microphone look like a slow
  model, and lost the history of what went wrong. Putting each problem where it can be
  acted on (the turn, the card, the line under the orb) keeps the conversation honest and
  tells the traveller what to do next.
- **Alternatives considered:** a toast for every problem (they vanish before they are
  read, and need a new component); a modal for the microphone (blocks the page for
  something the browser's own prompt already asks); retrying failed turns automatically
  (a second wait the traveller did not ask for).

### D-82 The voice picker sits under the orb; the voice fact stays out of memory

- **Decision:** a shadcn Select under the talk control lists the voices `GET /voices`
  returns (D-90), named by the last part of Kokoro's id (af_heart is "Heart", am_adam is
  "Adam"), preselected from the user's `voice` fact if TTS still offers it, else the
  list's default. Choosing one shows at once and sends `set_voice`; the gateway applies it
  to the next reply and saves it as the `voice` fact for the next visit, and a bad id
  comes back as `unknown_voice`, which puts the picker back. The picker is disabled while
  a turn runs and hidden when TTS cannot list its voices. "What Sarjy remembers" leaves the
  `voice` fact out, and its count with it, since the picker already shows the choice
  (settled 9 Oct in M4.9, with Ahmed).
- **Reason:** the voice is a setting, not something Sarjy learned about the traveller, so
  it belongs next to the control it changes; naming voices by their first names avoids
  showing Kokoro's codes. Hiding the picker without a voice list is honest: Sarjy keeps
  the voice it has.
- **Alternatives considered:** the picker in the header beside the colour swatches (far
  from the voice it changes); showing the voice as a fact in the memory panel too (said
  twice); names with accents and genders ("Heart, American, female"), more than five
  voices need.

### D-91 Token counts logged per round; lean tool payloads stay

- **Decision:** both model adapters report the provider's own token counts (Claude from
  its stream's start and end events, Groq from the usage on its last chunk), and the
  pipeline logs input and output tokens for every round with the turn's id.
  `SARJY_TOOL_PAYLOAD` switches the tour tools between Sarjy's lean results (the default)
  and SayTech's raw responses (settled 9 Oct in M3.9).
- **Reason:** experiment 5 needed what the model actually read, not an estimate, and the
  same lines show where a turn's tokens go from now on. Raw payloads added 0 to 10% to
  the round after a tour tool and no measurable latency, because SayTech's assistant
  endpoints are already compact; the system prompt, about 3,550 tokens, dominates every
  request. Lean results stay: they drop empty and unused fields, and a change on
  SayTech's side can't swell them.
- **Alternatives considered:** estimating tokens with a tokenizer (another dependency, and
  not the provider's count); asking Groq for usage with `stream_options` (it already
  sends it under `x_groq`, and another provider might reject the option).

### D-92 Earlier visits sent with the visit; replays re-synthesised

- **Decision:** after the memory list, every visit gets a `history` message: the user's
  last 3 visits that had a question, newest first, each with its last 10 exchanges
  (transcript and reply). A `replay` message names one of the user's own turns; the
  gateway re-synthesises its stored reply in the visit's current voice, sentence by
  sentence through the normal `audio` messages, then sends `replay_done`. A replay counts
  against the turn limits and sends no latency marks. "Forget me" still deletes facts
  only (settled 9 Oct, at Ahmed's request, as M4.10).
- **Reason:** returning visitors asked to see what was said before and hear it again. The
  turns are already stored per session and user (D-66), so the history is one query.
  Audio isn't stored, so replaying means synthesising again, which costs TTS time like a
  turn, hence the limits. Every page load is a visit, so visits without a question are
  skipped; checking the turn's owner in SQL keeps a page from replaying someone else's.
- **Alternatives considered:** storing the reply audio (storage and cost for something
  rarely replayed); an HTTP endpoint for the history (the visit's socket already knows the
  user and opens with the page); deleting history with "Forget me" (Ahmed chose facts only
  for now).

### D-83 Settings with a tap-to-talk mode; the orb and the welcome for keyboards and readers

- **Decision:** a gear beside the colour swatches opens a settings popover (shadcn
  Popover and Radio Group) with Sarjy's voice, moved there from under the orb, and how you
  talk: hold the orb or Space while speaking, or tap once to start and again to send. The
  choice is kept in the browser; the orb's label ("Tap to talk to Sarjy", then "Tap to
  send"), the line under it and the first-visit text follow it. The orb is described by
  that line (`aria-describedby`), so a screen reader hears "Listening…" or "Thinking…",
  and declares Space as its shortcut. While the welcome plays, the page under it is
  `inert`, and any key skips it, as a tap does. The focus ring is darker in Pearl and
  Coral: measured against the page background it was 2.91:1 and 2.64:1, under the 3:1 a
  focus indicator needs, and is now 4.17:1 and 3.96:1; Night was 6.99:1. Every text pair
  the page uses passes AA in all three palettes, the tightest being Coral's accent label
  at 4.74:1 (settled 9 Oct in M4.8, with Ahmed).
- **Reason:** holding a button is hard for some people with motor impairments, and the
  hold also had to be learned; a second way to talk, chosen once, removes that without
  changing the default. The line under the orb already says what Sarjy is doing, so
  pointing the orb at it gives screen readers the state for free; the M3 session will
  make that line say what Sarjy is really doing ("Checking the weather in Dubai"), sent
  from the tool loop.
- **Alternatives considered:** a settings page or a dialog (heavier than two choices
  need); a separate visible state label on the orb (says the same thing twice); a
  toggle on the orb itself, such as double-tap to lock (hard to discover).

### D-84 Earlier visits above the conversation, folded by age; replays light up in place

- **Decision:** the visits from `onHistory` (D-92) sit above today's conversation, oldest
  at the top, each a shadcn Collapsible headed by its start time in the visitor's own
  time zone and its number of questions; the most recent earlier visit is open and older
  ones are folded, and a "This visit" label marks where today begins. Earlier exchanges
  are set a size quieter than today's. Each of Sarjy's earlier answers has a play button
  that calls `replay(turnId)`; while it runs, the line under the orb says "Getting that
  answer ready…" then "Sarjy is replaying an earlier answer", the answer's words light up
  as they are spoken, and the orb and the other play buttons wait. The page sends a
  replay's `onSpeak` clips to the answer being replayed, never to today's last turn, and
  drops them when the visit is idle again. A returning visitor's empty conversation says
  "Welcome back" instead of the three example questions (settled 9 Oct in M4.10, with
  Ahmed).
- **Reason:** the history explains why Sarjy remembers what it does, and folding older
  visits keeps today's conversation in view on a phone. Reading the thread in time order
  matches how today's turns are already laid out, newest at the bottom by the orb.
- **Alternatives considered:** every visit open (a long scroll before today's); a separate
  history panel or page (another place to look, against the one-screen layout of D-80);
  newest earlier visit at the top (breaks the time order of the thread).

### D-93 Claude caches the shared part of the prompt

- **Decision:** the system prompt is two blocks. The shared part is the rules and
  SayTech's catalogue, the same for every traveller and every turn. The turn's part, the
  traveller's facts and the date and time, comes after it. The Claude adapter puts a
  5-minute cache mark (`cache_control`) on the shared block, so Claude caches the tools
  and the shared prompt together. `SARJY_CLAUDE_PROMPT_CACHE` (default true) turns it off
  for measuring. Each round logs its fresh, cached and written input tokens. There is no
  pre-warming and no second mark on the history.
- **Reason:** M3.9 showed the system prompt, about 3,050 tokens with the tools, is most
  of what every round reads. With the cache, every round after the first read those tokens
  from it, across visitors, and a round's input bills about a third as much (experiment
  9). The first word came no sooner, timed through the pipeline and directly, so caching
  is a cost decision, not a latency one. That is also why there is no pre-warming: a
  cold cache costs no time.
- **Alternatives considered:** leaving the prompt whole (the date, time and facts at its
  end would change the cached bytes every minute and for every traveller); a second mark
  after the history (the facts and time would have to move after it, and the fresh part
  is under 2,000 tokens a round); reading Groq's cache counts too (Claude is the primary
  model, D-69).

### D-94 Activity status from fixed templates, sent before each tool runs

- **Decision:** when the model's tool calls are about to run, the gateway sends one
  `{"type": "activity", "turn_id", "text"}` per call, in order. The words come from
  fixed templates and the call's arguments, in `activity.py`: the search's city, the
  tour's name when this turn's search returned it, the weather's day counted from the
  date the prompt gave the model (today's, tomorrow's, a weekday within the week, else
  the date), and fixed words for the memory tools. A call whose arguments don't parse,
  or an unknown tool, has none. No latency mark is added.
- **Reason:** the UI session asked, at Ahmed's request, for the line under the orb to
  say what is really happening instead of "Thinking…" while tools run. The line is
  aria-live, so it also tells screen-reader users. Templates are instant, can't
  invent anything, and are tested; counting from the prompt's date keeps "tomorrow" the
  model's tomorrow.
- **Alternatives considered:** asking the model to narrate (slower, and its words could
  promise what the tools then don't find); each tool describing itself (spreads the
  wording over seven classes and their test fakes, and get_tour can't see this turn's
  search); a `tool_start` mark (marks are one per turn, D-04, and each tool's time is
  already logged).

### D-95 A turn never says its answer twice

- **Decision:** two rules in the tool loop. First, a round that wrote words and whose
  only tool calls are `remember_fact` or `forget_fact`, all successful, is the whole
  answer: the facts are saved and the model isn't asked again. A failed save still goes
  back to the model. Second, with sentence streaming, when a round wrote words before
  other tool calls, the next round gets a system note quoting what the traveller already
  heard and asking it to carry on without repeating, greeting or thanking again.
- **Reason:** on 10 Oct a greeting came out twice ("Hello Ahmed, lovely to meet you…
  Hello Ahmed, it's good to have you here"). Claude answered and saved the name in one
  round, then answered again when given the save's result. Since sentence streaming
  speaks every round's words (D-76), both reached the traveller. Before it, the baseline
  kept only the last round, so the first answer was silently thrown away. A saved fact
  gives the model nothing it needs, and skipping the round also saves about a second and
  a model call. Other tools' results are needed, so there the note is the fix: in three
  live passes no reply repeated itself, but in the model runs of M3.8 one of Haiku's two
  answers to "colour and heights" (facts saved together with a search) still thanked
  twice. The note makes repeats rarer, not impossible.
- **Alternatives considered:** holding a round's words until it is known whether it calls
  tools (gives back sentence streaming's gain, D-76); a standing rule in the system
  prompt (the tools-first rule shows such rules are not always kept, and a note quoting
  the exact words is more direct); removing duplicate sentences (repeats are rephrased,
  not identical).

### D-96 Claude Haiku 5.5 first, gpt-oss-120b as the fallback

- **Decision:** Claude Haiku 5.5 stays the first model (D-69). Groq's fallback model
  changes from Qwen 3.8 27B to `openai/gpt-oss-120b`, at reasoning effort `low` (gpt-oss
  can't turn reasoning off). Both are settings defaults, so the change ships with the
  gateway.
- **Reason:** experiment 4 ran the script's ten questions twice per model, checking each
  turn's tool calls. Haiku passed 18 of 20 and was the only model to save the facts said
  in passing, with a first word at 970 ms p50. Qwen passed 11: it saved no fact while
  saying it had, invented a price and a forecast, and is fast only because it skipped its
  tools. gpt-oss-120b passed 17, never answered a tour or weather question without its
  tool, and is the safer fallback despite a first word at 1.7 s. Sonnet 5.5 was 0.7 s
  slower to its first word than Haiku and costs more.
- **Alternatives considered:** keeping Qwen for speed (a fallback that invents prices is
  worse than a slower one); gpt-oss-20b (faster on tool turns, but it saved a fact on
  "thanks" and lost the buggy tour); Cerebras and Gemini (not measured, no keys); Sonnet
  5.5 through the gateway (needs its thinking blocks passed back between tool rounds, for
  a slower model).

### D-97 A TTS cache in the gateway's memory (settles O-23)

- **Decision:** the gateway keeps the audio of each spoken sentence in memory, keyed by
  its text and voice, and reuses it when the same words are said again in the same
  voice. The least recently used clips go first once it holds `SARJY_TTS_CACHE_BYTES`
  (32 MB by default, about 11 minutes of speech; 0 turns it off). When the gateway
  starts, it makes six common phrases in the default voice in the background. Every
  lookup logs a hit or a miss with the running counts.
- **Reason:** a hit skips both the hop to TTS and the synthesis, so a turn that opens
  with a cached sentence starts speaking about 1.3 s sooner (experiment 3). Speed is
  always the default, and every deploy starts a new gateway revision, so a cached clip
  never outlives the TTS model that made it, and neither needs to be in the key.
  A replay of an answer this gateway has just spoken finds its sentences already there
  (by construction; not timed). 32 MB is a small share of the gateway's 512 MiB.
- **Alternatives considered:** in the TTS service (still a network hop, and shared by
  both gateway instances, but a TTS deploy would have to clear it); Cloud Storage
  (survives deploys, but adds a bucket and a read of tens of milliseconds for a hit rate
  this low);
  warming more phrases (Claude rarely repeats a sentence word for word, so they would
  mostly sit unused); warming on the first visit instead of at startup (would compete
  with that visit's first turn for TTS).

### D-98 The services stay in Doha (`me-central1`) for the submission

- **Decision:** the gateway, TTS and Cloud SQL stay in `me-central1`. A US region is
  recorded as the option to revisit after the submission, once the hop from the Gulf can
  be measured from the Gulf.
- **Reason:** experiment 7 timed the hops from inside each region. From Doha, Groq and
  Anthropic answer their first byte in about 254 and 192 ms; from US East in 84 and
  48 ms, which would save roughly 0.3 s on a turn without a tool and 0.45 s on a turn with
  one. A Gulf visitor would pay part of that back on the longer hop to a US gateway,
  estimated at 0.2 s a turn. A net gain of 0.1 to 0.25 s isn't worth moving the database,
  the registry, the secrets and both services a day before the submission, and the bigger
  levers (sentence streaming, warm instances) are already in.
- **Alternatives considered:** moving everything to `us-east1` (the gain above, plus GPUs
  for TTS, but a full migration and a longer hop for Gulf visitors); splitting the gateway
  and TTS across regions (Google's path between Doha and US East took about a second);
  `me-central2` (Dammam, nearer Saudi visitors, but the project has no access to it).

## Open decisions

Settled rows move up as D entries and their IDs are not reused, so gaps are expected.

| ID | Open decision | Options | Proposal | Settled in |
| --- | --- | --- | --- | --- |
| O-16 | Turn-taking (PRD open question) | push-to-talk first; voice activity detection from the start | Push-to-talk first, as the PRD's architecture table says; VAD in M4.5. | settled unless you object |
| O-25 | Frontend unit tests | Vitest for pure logic (timing maths, message parsing); none | Add Vitest only if the client grows real logic. | M3.2 |
| O-29 | Cloud Run or a VM for the deployed services | stay on Cloud Run (D-22: scale to zero, managed HTTPS and WebSockets, keyless deploys, private TTS); a VM or a mix, for a faster always-warm CPU or a GPU for Kokoro | To discuss in detail with Ahmed (asked on 9 Oct): cold starts, CPU speed, the cost of keeping instances warm, GPU options, and what experiments 6 and 8 show. | a session before the review |
| O-26 | Voice activity detection approach | a browser VAD library (new dependency); a simple energy threshold; server-side VAD | Decide in M4.5, once push-to-talk is solid. | M4.5 |

## Approved code-standards exceptions

None yet. Each entry needs: the rule or path, the reason, who approved it, and the date.
