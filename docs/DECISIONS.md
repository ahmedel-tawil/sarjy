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

## Open decisions

Settled rows move up as D entries and their IDs are not reused, so gaps are expected.

| ID | Open decision | Options | Proposal | Settled in |
| --- | --- | --- | --- | --- |
| O-16 | Turn-taking (PRD open question) | push-to-talk first; voice activity detection from the start | Push-to-talk first, as the PRD's architecture table says; VAD in M4.5. | settled unless you object |
| O-19 | Migrations | a small runner over numbered SQL files; a migration tool | A small runner: no dependency, easy to explain. | M2.3 |
| O-20 | Database tests | real Postgres (Docker locally, a service container in CI); fakes only | Real Postgres: upsert behaviour can only be tested against Postgres. Tests go through repository classes (`no-raw-connection-in-tests`). | M2.3 |
| O-22 | Where rate-limit state lives | in memory per instance, with max instances capped; Postgres | In memory, with the trade-off written down. | M2.13 |
| O-23 | Where the TTS cache lives (SayTech's is settled in D-58) | in the gateway's process; in the TTS service; Cloud Storage | Decided by measurement. | M3.7 |
| O-24 | Audio for the test script | recorded by me; synthesised (Kokoro or macOS `say`) | Synthesised for repeatability, plus a few real recordings as a sanity check. | M3.3 |
| O-25 | Frontend unit tests | Vitest for pure logic (timing maths, message parsing); none | Add Vitest only if the client grows real logic. | M3.2 |
| O-29 | Cloud Run or a VM for the deployed services | stay on Cloud Run (D-22: scale to zero, managed HTTPS and WebSockets, keyless deploys, private TTS); a VM or a mix, for a faster always-warm CPU or a GPU for Kokoro | To discuss in detail with Ahmed (asked on 9 Oct): cold starts, CPU speed, the cost of keeping instances warm, GPU options, and what experiments 6 and 8 show. | a session before the review |
| O-26 | Voice activity detection approach | a browser VAD library (new dependency); a simple energy threshold; server-side VAD | Decide in M4.5, once push-to-talk is solid. | M4.5 |

## Approved code-standards exceptions

None yet. Each entry needs: the rule or path, the reason, who approved it, and the date.
