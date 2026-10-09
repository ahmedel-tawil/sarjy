# Sarjy: guide for coding agents

Sarjy is a voice concierge for Magic Experience, a Dubai tour operator. It is a take-home
for Sarj AI's Full Stack Engineer role. The full plan is in `docs/PRD.md`. Read it before
any task, and treat it as the source of truth for scope.

## Non-negotiables

1. **The owner must be able to explain every line.** Ahmed will walk reviewers through
   this code live. Prefer simple, explicit code over clever code. No magic, no
   unnecessary abstraction.
2. **Written from scratch.** Do not copy code from other projects.
3. **One task at a time.** For each task: restate it, plan it, wait for approval, then
   implement. Never start the next task without being asked.
4. **Ask before adding any dependency**, and say why it is needed.
5. **Never push, deploy, or run destructive commands** (`git push`, `terraform apply`,
   `terraform destroy`, `gcloud ... delete`, dropping tables) without explicit approval.
6. **No secrets in code or git.** Configuration comes from environment variables.
   `.env` is git-ignored; `.env.example` lists variable names only.
7. **Don't widen scope.** If something outside `docs/PRD.md` seems worth doing, propose
   it; don't build it.

## Working loop for every task

1. Restate the task and its acceptance criteria from `docs/TASKS.md`.
2. Plan: files to touch, interfaces, tests. Wait for "go".
3. Implement with tests.
4. Run lint, type check and tests; all must pass.
5. Explain the change in plain English: what changed, why, anything non-obvious,
   and what to verify manually.
6. Propose a Conventional Commit message (`feat:`, `fix:`, `test:`, `docs:`,
   `refactor:`, `chore:`). Small, focused commits.

## Stack

- **Backend:** Python, uv, FastAPI, Pydantic v2, asyncio, psycopg 3 with raw SQL (no ORM),
  PostgreSQL. Python 3.14, as Sarj's standards require (D-30 in `docs/DECISIONS.md`).
- **Frontend:** React + Vite + TypeScript + Tailwind + shadcn/ui, built and served by the gateway (one origin).
- **Voice:** hosted STT (Groq Whisper, D-51), LLM on Groq (Qwen 3.8 27B) and Claude
  (Haiku 5.5 through Anthropic's SDK), switchable, each the other's fallback (D-63),
  TTS with the Kokoro-82M ONNX model on onnxruntime, through our own text front end
  (no kokoro-onnx, D-38), as a separate service.
- **Infra:** GCP Cloud Run, Cloud SQL, Artifact Registry, Secret Manager; Terraform;
  GitHub Actions with Workload Identity Federation. DNS stays in DigitalOcean.

## Sarj standards (enforced from the first commit)

This repo adopts Sarj's public tooling: https://code-standards.sarj.ai and
https://repo-standards.sarj.ai. The first task sets it up:

```
uv tool install --python 3.14 code-standards
code-standards setup
code-standards doctor
code-standards check
```

- The pre-commit hooks and the generated CI workflow must pass. **Never bypass them**
  (no `--no-verify`, no disabling hooks).
- Use `code-standards fix` for safe automatic fixes, then fix the rest by hand.
- If a rule genuinely doesn't fit, ask first. An approved exception goes through
  `code-standards exclude`, with the reason written in `docs/DECISIONS.md`.
  Never silence a rule inline without approval.
- Commit messages and pull-request size follow their policy, so keep changes small.

## Code style (aligned with Sarj's public code standards)

- ruff for lint and format; strict type checking (basedpyright strict).
- Every external service sits behind a small `Protocol` interface with one adapter.
  Dependencies are injected; tests use fakes, never real network calls.
- Pydantic models at every boundary: HTTP, WebSocket messages, tool arguments,
  external JSON.
- SQL: explicit transactions, `ON CONFLICT` on inserts that can repeat, no `SELECT *`.
- Specific exceptions only; never a bare `except`.
- No `print` in application code; use structured logging.
- Comments explain *why*, never restate *what*.

## Frontend principles (inspired by Sarj's public design lab, written for Sarjy)

- Build only what `docs/PRD.md` describes: no invented screens, fields or panels.
- Tailwind + shadcn/ui primitives; never hand-roll a component that already exists.
- Colours come from design tokens defined once in CSS; no hex or ad-hoc colour classes.
- One icon set (HugeIcons).
- Flat and calm: motion is purposeful, at most 300 ms, and respects
  `prefers-reduced-motion`.
- No generic "AI app" look: every element must earn its place.
- Sarjy has its own visual identity. Do not copy Sarj's brand assets, tokens or
  components; their repos inform principles only.

## Latency instrumentation (the deep dive)

Every turn has a `turn_id`. Marks: `speech_end`, `audio_received`, `stt_done`,
`llm_first_token`, `first_sentence_ready`, `tts_first_byte`, `playback_start`.
Never remove or rename a mark without updating `docs/LATENCY.md`. Any change that
could affect latency must say so in its summary.

## Optional work

`.context/optional-deep-dive.md` describes an optional second deep dive. In
`docs/TASKS.md`, put its tasks in a separate final milestone marked optional, never on
the critical path, and never start them without an explicit go. Do follow its
"design for it now" notes in the core code, since they cost little and avoid rewrites.

## Repo layout

Each folder is created by the first task that puts something in it.

```
gateway/     voice gateway (FastAPI), Python package sarjy_gateway
tts/         Kokoro TTS service, Python package sarjy_tts
frontend/    React app
infra/       Terraform
docs/        PRD.md, TASKS.md, DECISIONS.md, LATENCY.md
.context/    assignment brief and FAQ (git-ignored, never committed)
```

## Commands

Fill in as they are created: install, run locally, lint, type check, test, build, deploy.

```
uv sync --all-packages   # install the Python workspace (gateway and tts) into .venv
uv run pytest    # run every Python test
```

Gateway (settings are `SARJY_*` environment variables, listed in `.env.example`):

```
uv run python -m sarjy_gateway                             # API only, on 127.0.0.1:8080
SARJY_FRONTEND_DIST=frontend/dist uv run python -m sarjy_gateway   # also serve a built frontend
docker build -f gateway/Dockerfile -t sarjy-gateway .      # production image, from the repo root
docker run --rm -p 8080:8080 -e PORT=8080 sarjy-gateway    # then open http://localhost:8080
```

TTS model (from the repo root; about 420 MB, git-ignored):

```
tts/scripts/download-model.sh tts/models      # pinned revision, every SHA-256 verified
uv run python tts/scripts/benchmark.py        # timings per model and thread count, plus voice samples
PORT=8081 uv run python -m sarjy_tts          # TTS service on 127.0.0.1:8081 (reads tts/models)
docker build -f tts/Dockerfile -t sarjy-tts . # production image; downloads its own model files
```

Speech to text (needs `SARJY_GROQ_API_KEY` in the git-ignored `.env`):

```
uv run python gateway/scripts/transcribe.py clip.webm clip.mp4   # real Groq call, with timings
uv run python gateway/scripts/chat.py "Is tomorrow good for a safari?"   # LLM time to first word (SARJY_LLM_API_KEY)
uv run python gateway/scripts/saytech.py   # the real SayTech API: demo questions, timings, result sizes (no key)
uv run python gateway/scripts/ask.py "How much is the buggy tour?"   # typed turns through the real pipeline and tools (Groq or Claude key)
```

Local Postgres 18, the same major version as Cloud SQL (D-64):

```
docker compose up -d --wait db    # Postgres on 127.0.0.1:5432; data kept in a Docker volume
SARJY_DATABASE_URL=postgresql://sarjy:sarjy@127.0.0.1:5432/sarjy uv run python -m sarjy_gateway
curl localhost:8080/ready         # 200 when SELECT 1 works, 503 with the reason otherwise
docker compose down               # stop it; add -v to delete the data too
```

Infrastructure (from `infra/`; needs `gcloud auth application-default login` once).
State lives in the `sarjy-ahmed-2026-tfstate` bucket, created by hand before the first init.

```
terraform init                    # connect to the remote state
terraform fmt -check && terraform validate
terraform plan -out=plan.tfplan   # review it; never apply without explicit approval
terraform apply plan.tfplan
terraform output                  # gateway_url, tts_url, image_repository
```

Deploys run in CI on every push to `main` (`.github/workflows/deploy.yml` calls
`scripts/deploy.sh <service>`); there is no manual deploy path.

Secret values never go through Terraform or git:
`printf %s "$VALUE" | gcloud secrets versions add <secret-id> --data-file=-`

Frontend (from `frontend/`, after `nvm use` picks Node 24 from `.nvmrc`):

```
npm ci           # install exactly what package-lock.json pins
npm run dev      # local dev server; proxies /ws and /health to a gateway on :8080
npm run build    # type check (tsc -b) and production build into dist/
```

`frontend/src/styles/shadcn.css` is generated by `shadcn eject`; don't edit it by hand.

Sarj standards (from the repo root; the hooks run the staged version on every commit):

```
uv tool install --python 3.14 code-standards   # once per machine
uv tool install shellcheck-py==0.11.0.1        # once per machine: ShellCheck for scripts/
code-standards setup                           # once per clone: installs the git hooks
code-standards check --trust-repository-code   # full gate: lint, types, docs, config; CI runs the same
code-standards fix                             # safe automatic fixes; fix the rest by hand
code-standards doctor                          # is the standards wiring healthy?
```

`--trust-repository-code` lets the check run our ESLint config, which is JavaScript. The
generated hooks and CI pass it too.
