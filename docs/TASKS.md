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
| M1 Voice loop deployed | 8 Oct | 14 | 22 | yes |
| M2 Memory, tools, tests | 9 Oct | 14 | 20.5 | no |
| M3 Latency deep dive | 9–10 Oct | 12 | 19 | no |
| M4 UI polish, Safari and phone | 9–10 Oct | 9 | 13 | no |
| M5 Docs, presentation, submission | 10–11 Oct | 8 | 11.5 | no |
| M6 Optional: guardrails and reliability | only after an explicit go | 5 | 9 | never |

**Schedule check.** The critical path adds up to 27 hours at upper bounds, for one
calendar day, now that deploys go through CI from day one (D-35) and the Kokoro front end
is our own code (D-38). All core work (M0–M5) adds up to about 90 hours across four days. Most tasks should take less than their
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

- [x] `git init` with `main` as the default branch; `origin` is
      `github.com/ahmedel-tawil/sarjy` (public, D-34).
- [x] The brief, the FAQ and `optional-deep-dive.md` live in `.context/`, and
      `git check-ignore` confirms all three are ignored. This matters more now that the
      repo is public.
- [x] `.gitignore` covers `.env`, `.context/`, virtualenvs, `node_modules/`, build output,
      `.terraform/`, Terraform state, Kokoro model files and `.DS_Store`.
- [x] `.env.example` exists with variable names only.
- [x] `.python-version` pins the Python version (3.13 at first; 3.14 since 8 Oct, D-30).
- [x] The "Repo layout" section of `AGENTS.md` no longer says "proposed". Folders are
      created by the tasks that fill them, since git doesn't track empty folders.
- [x] After your approval, the bootstrap commit is pushed straight to `main`: the only
      direct push to `main` (D-34).

### M0.2 Python workspace skeleton

- [x] A uv workspace with `gateway` and `tts` as members (D-31); `uv.lock` is committed.
- [x] Each has a `src/` package and one passing smoke test; `uv run pytest` passes.
- [x] No lint or type-check configuration is written by hand; M0.4 generates it.

New dependencies: `pytest` (dev).

### M0.3 Frontend scaffold

- [x] `frontend/` is a Vite + React + TypeScript app with Tailwind and shadcn/ui
      initialised, using npm (D-33) and Node 24 pinned in `.nvmrc` and `engines` (D-36).
- [x] Generator output lands in its own commits whose messages say they are generated
      (D-32).
- [x] Design tokens are defined once in a CSS file, even if there are only a few so far.
- [x] `npm run build` and the TypeScript build check pass; the lockfile is committed.
- [x] The page shows only the word "Sarjy". No UI is invented ahead of its task.
- [x] shadcn uses the Maia preset with HugeIcons as its icon library; its base styles are
      ejected into their own file, and neither the `shadcn` CLI nor lucide-react is a
      dependency (D-37).

New dependencies: from the Vite template, react, react-dom, vite, @vitejs/plugin-react,
typescript, @types/react, @types/react-dom, @types/node, oxlint; tailwindcss and
@tailwindcss/vite; from shadcn's Maia preset, radix-ui, class-variance-authority, cn,
tw-animate-css, @hugeicons/react, @hugeicons/core-free-icons,
@fontsource-variable/figtree.

### M0.4 Adopt Sarj code standards

- [x] `uv tool install --python 3.14 code-standards`, then `code-standards setup` with the
      agreed hook runner (D-39), passing `--python-dest` / `--typescript-dest` only if
      root detection gets them wrong.
- [x] `code-standards doctor` reports a healthy adoption.
- [x] `code-standards check` exits 0 on the whole repo.
- [x] `.sarj-standards.toml` pins the bundle version; `.github/workflows/standards.yml` and
      `.github/workflows/commit-policy.yml` exist.
- [x] basedpyright runs in strict mode on both Python packages.
- [x] The commit-msg hook rejects `git commit -m "stuff"` and accepts `chore: ...`.
- [x] No exclusions. If one is unavoidable, it was approved, added with
      `code-standards exclude` and explained in `DECISIONS.md`.
- [x] The "Commands" section of `AGENTS.md` lists install, lint, type check and test.

### M0.5 Protect `main` and run tests in CI

- [x] A small CI job runs the Python tests and the frontend build (the generated
      workflows lint; they may not run tests).
- [x] All workflows pass on this task's pull request.
- [x] After your approval, `main` requires a pull request and passing checks, and the
      merge method is set (D-40).

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
| M1.9a | Kokoro front end and model runner | 2 h | M0.4 | yes |
| M1.9b | Kokoro TTS service | 1.5 h | M1.9a | yes |
| M1.10 | Deploy TTS and connect the gateway | 1.5 h | M1.5, M1.9b | yes |
| M1.11 | Turn pipeline, baseline mode | 2 h | M1.7, M1.8, M1.10 | yes |
| M1.12 | Frontend voice loop | 1.5 h | M1.4, M1.11 | yes |
| M1.13 | Deploy the voice loop | 1 h | M1.6, M1.12 | yes |
| M1.14 | Fixes from live testing | 1.5 h | M1.13 | yes |

### M1.1 GCP project bootstrap

No code: you run the steps; I prepare the exact commands.

- [x] A GCP project exists with billing linked (`sarjy-ahmed-2026`).
- [x] A budget alert is on the project before any other resource, at the amount you
      choose (USD 50).
- [x] The needed APIs are enabled: Cloud Run, Artifact Registry, Secret Manager,
      Cloud SQL Admin, IAM Credentials, Security Token Service.
- [x] A versioned Cloud Storage bucket holds Terraform state (`sarjy-ahmed-2026-tfstate`,
      created in M1.2).
- [x] The region is chosen and recorded in `DECISIONS.md`, after checking Cloud Run
      WebSockets, Cloud SQL, domain mapping and GPU availability there (D-44).
- [x] GPU quota not filed: Cloud Run has no GPUs in `me-central1`, so M3.12 would need a
      second region (D-44).

### M1.2 Terraform foundation

- [x] `infra/` holds the provider, the remote state backend and variables;
      `terraform fmt -check`, `terraform validate` and `code-standards check` pass.
- [x] Resources: an Artifact Registry repository; one runtime service account each for
      the gateway and TTS; Secret Manager secrets (names only); Cloud Run services
      `gateway` and `tts` running a placeholder image.
- [x] The gateway's request timeout allows long WebSocket sessions.
- [x] `tts` cannot be called without authentication (D-45): an anonymous request gets 403.
- [x] Secret values are added by hand with `gcloud`; they never appear in Terraform state
      or in git.
- [x] Image updates made by the deploy script do not show up as Terraform drift
      (confirmed: `terraform plan` shows no changes after the first CI deploy).
- [x] `terraform apply` runs only after you approve the plan.

### M1.3 Gateway skeleton

- [x] FastAPI app with a lifespan handler, settings read from environment variables into a
      Pydantic model, and structured JSON logs that Cloud Logging parses (D-42).
- [x] `GET /health` returns 200 (not `/healthz`, D-41); WebSocket `/ws` echoes binary
      frames back.
- [x] The gateway serves the built frontend from `/` (one origin).
- [x] Routers follow the `*Router.build()` shape required by code-standards
      (`fastapi-class-router-contract`).
- [x] A multi-stage Dockerfile builds the frontend and the gateway; `docker run` locally
      serves the page.
- [x] Tests cover `/health` and the echo with FastAPI's test client.

New dependencies: fastapi, uvicorn (with WebSocket support), possibly pydantic-settings.

### M1.4 Push-to-talk audio round trip (echo)

- [x] Holding a button records the mic; audio goes to the gateway in chunks while
      recording, so the upload overlaps speech.
- [x] On release, the browser sends an end-of-turn message and plays back the echoed audio.
- [x] Audio playback is unlocked by the first tap, as Safari requires.
- [x] A denied mic permission shows a clear message instead of failing silently.
- [x] WebSocket messages have one typed definition per side (D-47).
- [x] Works in desktop Chrome: checked with a synthetic microphone in Chromium, then by
      you with a real microphone on the deployed app.

New dependencies: zod (D-47). The shadcn Button and the HugeIcons mic needed no new
package beyond what M0.3 installed (D-37).

### M1.5 CI deploy with Workload Identity Federation

- [x] Terraform creates a workload identity pool and provider limited to
      `ahmedel-tawil/sarjy`, plus a deploy service account with only the roles it needs.
- [x] A deploy script builds the image, pushes it to Artifact Registry and rolls out a new
      Cloud Run revision. The workflow only calls the script (code-standards rule
      `workflow-embedded-program`).
- [x] On a merge to `main`, GitHub Actions authenticates through Workload Identity
      Federation and deploys the gateway; TTS joins in M1.10.
- [x] No service-account JSON key exists anywhere.
- [x] `terraform apply` runs only after you approve the plan.

### M1.6 First deploy: hello over HTTPS

- [x] Merging the M1.4 echo app deploys it through CI (D-35).
- [x] The `*.run.app` URL loads over HTTPS.
- [x] The WebSocket connects and the echo works in Chrome on a laptop and on a phone over
      mobile data; the mic permission prompt appears on both. Laptop: done (8 Oct, you
      heard your own words back). Phone: checked on 8 Oct through the full voice loop in
      M1.13 (Chrome on an iPhone), which replaced the echo.
- [x] Fallback not needed: GCP worked. (Had it blocked this, the same container would
      run on a DigitalOcean droplet, as the PRD plans.)

### M1.7 STT adapter

- [x] A `SpeechToText` Protocol, one hosted adapter (Groq, D-51) and a fake for tests
      (a fake HTTP transport).
- [x] Unit tests cover the request it builds and how provider errors map to our own
      exceptions, with no network calls.
- [x] A dev script transcribes a Chrome (webm) and a Safari (mp4) recording correctly:
      both returned the test question word for word, in 372 ms and 396 ms.
- [x] `DECISIONS.md` records the provider and whether it can stream (D-51: it cannot).
- [x] On Cloud Run the gateway receives the key from Secret Manager (Terraform, applied
      with your approval; revision `gateway-00008-vd2` became ready, so the secret resolves).

New dependencies: none (httpx2 came with M1.10).

### M1.8 LLM adapter (streaming)

- [x] A `ChatModel` Protocol that streams events: text deltas now, with tool-call deltas
      already part of the event type. `stream()` is an async context manager, so the HTTP
      response closes even if a caller stops reading early.
- [x] One adapter for OpenAI-compatible chat APIs, so Groq, Cerebras and Gemini differ
      only by base URL, key and model name (D-52, D-53). This also leaves room for a
      fallback provider later.
- [x] Parsing of the streamed response is tested against recorded fixture streams (a
      plain reply and a tool call from Groq); requests time out through the client.
- [x] System prompt v0: Sarjy's persona, short spoken sentences, no markdown
      (`gateway/src/sarjy_gateway/prompts.py`).
- [x] A dev script streams a reply from the chosen provider: Qwen 3.8 27B answers with its
      first word in about 0.4–0.5 s from here.
- [x] On Cloud Run the gateway gets `SARJY_LLM_API_KEY` (the same Groq secret); added with
      the pipeline in M1.11, so Terraform changes once.

New dependencies: none (httpx2 came with M1.10).

### M1.9a Kokoro front end and model runner

Our own code instead of kokoro-onnx, which does not allow Python 3.14 (D-38).

- [x] Text becomes phonemes with espeak-ng (US English), through phonemizer and
      espeakng-loader.
- [x] Phonemes become token ids through the model's published vocabulary, read from the
      pinned `tokenizer.json` (D-48); unknown symbols are dropped and logged.
- [x] onnxruntime runs the model with the tokens, the voice's style vector (picked by
      token count) and the speed, and returns 24 kHz audio.
- [x] Input longer than the model's token limit is split at sentence or phrase
      boundaries, never mid-word (the limit also respects the voice files' 509 usable
      rows).
- [x] Unit tests cover phoneme-to-token mapping, the length limit and style selection,
      using a fake onnxruntime session, so they never load the model.
- [x] The real model speaks, and it sounds right: from `tts/scripts/benchmark.py`'s five
      samples you chose `af_heart` as Sarjy's default voice (D-49).

New dependencies: onnxruntime, numpy, phonemizer, espeakng-loader, and pydantic for
reading `tokenizer.json`.

### M1.9b Kokoro TTS service

- [x] `tts/` is a small FastAPI service: `POST /synthesize` takes text, voice and speed
      and returns a 16-bit mono 24 kHz WAV (D-50); `GET /health` (D-41).
- [x] Model and voice files are downloaded at image build time from pinned URLs with
      SHA-256 checks; the model loads once at startup, with one warm-up synthesis.
- [x] Input is validated: text length limit, known voice, speed range.
- [x] `GET /voices` lists the voices the image carries and the default (`af_heart`), for
      the selectable voice (D-49).
- [x] Unit tests use a fake synthesiser, so they never load the model.
- [x] The image runs locally and returns audible audio for "Hello from Sarjy".
- [x] Noted for `LATENCY.md` (M3.1 creates it): a 10-word sentence takes 1.08 s over HTTP
      on this Mac natively and 2.2 s in Docker Desktop; load and warm-up take 1.8–2.1 s.
      Voices and languages recorded in D-50.

New dependencies: fastapi, uvicorn, pydantic-settings.

### M1.10 Deploy TTS and connect the gateway

- [x] CI builds and deploys the TTS image to its Cloud Run service: 2 vCPU, 2 GiB,
      `SARJY_THREADS=2`, at most 4 requests per instance.
- [x] An unauthenticated request to TTS is refused; the gateway's request succeeds (D-45).
- [x] The gateway has a `TextToSpeech` Protocol, an HTTP adapter and a fake; tests cover
      request and response handling.
- [x] The deployed gateway reaches TTS with its own identity: `GET /voices` on the public
      gateway lists the five voices (0.5 s warm). Synthesis on Cloud Run, timed directly:
      a 10-word sentence (3.9 s of audio) takes 3.0–3.3 s end to end, of which about 0.5 s
      is the network from this Mac, so roughly 2.5–2.8 s of synthesis on 2 vCPU, about
      2.5 times slower than the Mac. The gateway's own synthesis calls start in M1.11.

### M1.11 Turn pipeline, baseline mode

- [x] One turn: audio in → STT → LLM (streamed, full reply collected) → TTS on the whole
      reply → audio out. This is experiment 1's baseline.
- [x] The browser can send `{"type": "set_voice", "voice": ...}`; the voice is checked
      against TTS's list and used for every later turn (D-49).
- [x] Each turn has a `turn_id`. The gateway records `audio_received`, `stt_done`,
      `llm_first_token`, `first_sentence_ready` and `tts_first_byte` on a monotonic clock.
- [x] Per turn, one structured log line holds all server marks, and the marks are sent to
      the browser.
- [x] The current session's recent turns go to the LLM as context (in memory for now).
- [x] Each turn keeps a list of its tool results, empty for now (room for the optional
      grounding check).
- [x] A failure in any stage sends an error message to the client; the socket stays open.
- [x] Tests with fakes cover a full turn, the order of the marks and a failing stage.
- [x] Checked locally with real Groq and Kokoro: the spoken demo question was
      transcribed, answered and spoken. Baseline server marks for two turns: STT done at
      862/742 ms, first LLM token 1049/921 ms, whole reply 1199/953 ms, whole reply
      spoken 3426/2353 ms. TTS on the whole reply dominates, which is what sentence
      streaming (M3.5) attacks. The same run showed the prompt narrowing Sarjy to Dubai;
      fixed.

### M1.12 Frontend voice loop

- [x] Sarjy's audio plays through Web Audio.
- [x] The user's transcript and Sarjy's reply appear as text.
- [x] A simple state shows listening, thinking or speaking.
- [x] The browser records `speech_end` (button release) and `playback_start` (first sample
      scheduled) with `performance.now()`, and sends both with the `turn_id` (D-54).
- [x] TTFA per turn is visible: shown under the reply, since the code standards allow only
      `console.warn` and `console.error`, and on a phone there is no console anyway. The
      gateway logs it too. The panel comes in M3.2.
- [x] Checked locally with a synthesized spoken question standing in for the microphone:
      transcript, reply and speech came back, the page showed "First audio after 4.4 s",
      and the gateway logged the same turn's server marks and `ttfa_ms` 4419.5.

### M1.13 Deploy the voice loop

- [x] Merged and deployed through CI (revision `gateway-00013-jt9`, 8 Oct).
- [x] On the deployed URL, "Hi Sarjy, what can I do in Dubai this weekend?" gets a spoken
      answer, on a laptop (Chrome on a Mac) and on a phone (Chrome on an iPhone).
- [x] Provider keys come from Secret Manager: both Groq keys from `groq-api-key`.
- [x] Cloud Logging shows the per-turn marks line: `completed` with the server marks and
      `played` with the browser's TTFA.
- [x] The first TTFA numbers from a few turns go into the day-one update. Browser turns:
      4.7, 3.7 and 7.3 s on the laptop, 4.5 s on the phone. Three scripted turns of the
      demo question: whole-reply speech took 6.4 to 7.1 s on Cloud Run's 2 vCPU (about
      2.7 s on a Mac), so audio arrived after about 8 s. TTS dominates, as locally.
- Found while testing: a cold TTS took 11 s on the phone's first turn, the page was
  reloaded meanwhile, and the gateway logged an unhandled `WebSocketDisconnect` when it
  sent the audio to the closed socket. Every merge also redeploys TTS, so the first
  turn after a merge is cold. Experiment 6 (warm vs cold) covers the cold start; the
  disconnect is fixed in M1.14.

### M1.14 Fixes from live testing

Added on 8 Oct after testing the deployed loop on a laptop and a phone.

- [x] A press with no speech is not sent: the browser cancels presses shorter than 0.3 s
      or quieter than -45 dBFS at their loudest, with a `turn_cancel` message, and says
      it heard no words. Whisper had been answering silence with "Thank you." (D-55).
- [x] The gateway logs one info line, not an unhandled exception, when the page leaves
      mid-turn. A test covers it.
- [x] An idle socket that closes (a sleeping phone, a deploy) shows no error; the next
      press reconnects. A close mid-turn still says the connection was lost.
- [x] Sarjy's reply text appears when its voice starts, together with the TTFA line; if
      the voice fails, the text appears with the error.
- [x] Checked locally in the browser pane with a stand-in microphone: a tap, a silent
      hold and a room-noise hold were each cancelled with no call to Groq; a real
      question after them was answered; an idle close showed nothing and the next press
      worked; a close while thinking showed the error and the gateway logged "browser
      left mid-turn".
- [ ] On the deployed URL, with real microphones on the laptop and the phone: a tap and a
      silent hold are cancelled, and soft speech still goes through (checks -45 dBFS).

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

- [x] The public endpoints for listing, detail, filtering and FAQs are written down in
      `DECISIONS.md`: base URL, parameters, auth, rate limits (D-56, was O-17).
- [x] Sample responses are saved as test fixtures for the adapter: twelve live responses
      in `gateway/tests/fixtures/saytech/`, including each error code.
- [x] Known data quirks are listed: missing prices, slugs with spaces, inconsistent
      destinations, and search not filtering by age (D-56).
- [x] Decision recorded: a new SayTech endpoint was needed. The 8 Oct spike found the
      website's public API couldn't search by category or return prices, so three
      read-only assistant endpoints were built in the SayTech repo with your go, and are
      live.

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

- [x] Each tool's arguments are a Pydantic model; the JSON schema sent to the LLM is
      generated from it.
- [x] The pipeline collects tool-call deltas, validates the arguments (invalid ones go back
      to the model as an error result, not a crash), runs the tools (several at once if
      asked) and returns the results, up to a fixed number of rounds (3, then one round
      with no tools; D-57).
- [x] Each turn's tool results are stored on the turn.
- [x] What `llm_first_token` means when tools run first is decided and written down for
      `LATENCY.md`: the first word of the spoken answer, after any tool rounds (D-57).
- [x] Tests with a fake LLM and fake tools: one call, two calls, invalid arguments, a
      failing tool, too many rounds; plus an unknown tool, broken JSON and a timeout.
- [x] Checked against the real Groq model with a stand-in weather tool: one call, then
      two calls in one round, each answered from the tool's numbers. The first spoken
      word came after about 1.0 to 1.2 s with a tool round, against 0.3 s without one.
      The toolbox is empty in production until M2.6, M2.10 and M2.11 add real tools.

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

- [x] A `Catalogue` Protocol, an HTTP adapter and a fake.
- [x] The three endpoints of D-56. Responses are parsed into Pydantic models (unknown
      fields ignored), then mapped to lean results: name, price or "on request", city,
      link.
- [x] `on_request: true` becomes "price on request", never zero.
- [x] A 400 with a code (unknown city, unknown category) becomes a result the model can
      act on, with the known values; a 404 is "not found"; a 429, a 5xx or a timeout is
      a SayTech error.
- [x] Slugs containing spaces are URL-encoded before any request.
- [x] Destinations pass through as they are; known inconsistencies are noted in tests, not
      silently "fixed".
- [x] Requests have timeouts (3 s, `SARJY_SAYTECH_TIMEOUT_SECONDS`). Tests use the M2.1
      fixtures and cover each rule above.
- [x] Checked against production with `gateway/scripts/saytech.py`: right prices and
      "price on request" for the buggy. From a Mac, calls on a reused connection took
      about 160 to 200 ms; a new connection adds about 0.5 s. `context/` took 0.3 to
      0.75 s on SayTech's side and one run saw 1.4 to 2.2 s spikes, which M2.9's cache
      and last-known-good copy absorb. Lean results are 0.4 to 5.4 KB.

### M2.9 SayTech cache and last-known-good

- [x] Responses are cached in the process for a configurable few minutes: 5 by default,
      `SARJY_SAYTECH_CACHE_SECONDS` (D-58, settles O-23 for SayTech).
- [x] If SayTech fails or times out, the last good copy is served and a warning is logged.
      Refusals such as an unknown city pass through; at most 256 copies per cache.
- [x] Tests use a fake clock and a failing fake client.

### M2.10 `search_tours` and `get_tour` tools

- [x] `search_tours(query, city, max_price_aed, category, accessible)` returns up to 5
      products; `query` is SayTech's name search (`q`).
- [x] `get_tour(slug, product_type)` returns one product's details: tickets with adult and
      child prices, and the children and cancellation policies, stated once when every
      ticket shares them. The site's FAQs come from `context/` in the prompt instead
      (M2.12). The argument is not called `type` (D-59).
- [x] Argument validation is tested.
- [x] Locally, demo scenarios 1 and 4 work, and the prices match the Magic Experience
      website: Ferrari World and Warner Bros. World 345, Qasr Al Watan 30, teamLab 55,
      and the buggy on request, as on its page. Checked with `gateway/scripts/ask.py`
      against real Groq and SayTech: scenario 4 said "price on request" in three runs
      out of three, with the first word after 1.5 s (search only) or 2.7 to 2.9 s (search
      and details). Scenario 1 named real products and prices, but also the Louvre's
      18-and-over ticket for a family with kids, in a long reply; both go to M2.12.

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
- [ ] SayTech's `context/` (cities, categories, FAQs) is in the prompt; a product's own
      policies beat the generic FAQs; availability questions get "I can't check live
      dates" and the product link (D-56).
- [ ] The prompt lives in one file.
- [ ] A dev script that sends text turns through the pipeline (skipping STT) shows the
      expected behaviour for: an off-topic request, price bait, a missing price, and a
      booking request. The script is `gateway/scripts/ask.py` (added in M2.10).
- [ ] When children are mentioned, a tour's children's policy is checked before it is
      recommended: scenario 1 must not suggest the Louvre's 18-and-over ticket.
- [ ] A search result that already answers the question gets no `get_tour` call: each
      extra round costs about 1.3 s and resends every token (O-27).

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
- [ ] `docs/LATENCY.md` exists with the mark definitions and how each gap is computed,
      including what `llm_first_token` means when tools run first (D-57).

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
| M4.9 | Voice picker | 1 h | M4.1, M1.11 | no |

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

- [ ] The domain serves the app over HTTPS. Cloud Run domain mapping is not available in
      `me-central1` (D-44), so this needs a global external load balancer: decide whether
      it is worth the cost before starting.
- [ ] You add the DNS record in DigitalOcean.
- [ ] The mic and the WebSocket work on the custom domain.

### M4.8 Accessibility and motion pass

- [ ] The talk control works from the keyboard (hold Space) and has an accessible name.
- [ ] Focus is visible; the token palette passes WCAG AA contrast.
- [ ] Nothing moves under `prefers-reduced-motion`.

### M4.9 Voice picker

- [ ] A small shadcn `Select` beside the talk control lists the voices from TTS with
      friendly names; `af_heart` is preselected (D-49).
- [ ] Changing it sends `set_voice`; the next reply uses the new voice.
- [ ] The choice is saved as one of the user's facts, so a returning visitor hears the
      voice they picked (needs M2.6).

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
