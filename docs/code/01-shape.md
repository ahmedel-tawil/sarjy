# 1. The shape

The gateway is one FastAPI app. It is the only part of Sarjy that talks to the providers
(Groq, Anthropic, the TTS service, SayTech, Open-Meteo, Postgres), so the keys stay on the
server and every stage of a turn can be timed in one place ([D-06](../DECISIONS.md#d-06-one-gateway-owns-each-turn)). This chapter shows how
the app is put together before any traveller connects: the settings, the services built
from them, and the pattern that lets every test run without the network.

## Start-up, in four steps

1. [`main()`](../../gateway/src/sarjy_gateway/__main__.py#L9) reads the settings, sets up
   JSON logging, builds the services, creates the app and hands it to uvicorn. uvicorn
   runs with `log_config=None`, so its own lines use the same JSON format, and with its
   access log off, because Cloud Run already logs every request ([D-42](../DECISIONS.md#d-42-logs-are-json-lines-from-the-standard-library)).
2. [`build_services()`](../../gateway/src/sarjy_gateway/services.py#L70) turns the
   settings into a frozen [`Services`](../../gateway/src/sarjy_gateway/services.py#L52)
   record: one object per provider. STT, Groq, TTS, SayTech and the weather share one
   `httpx2.AsyncClient`, so they share one connection pool. Anthropic's SDK keeps its own
   client, built with `max_retries=0` so that a failure goes to the fallback model at once
   instead of being retried while the traveller waits
   ([`build_anthropic_client`](../../gateway/src/sarjy_gateway/services.py#L106)).
3. [`create_app()`](../../gateway/src/sarjy_gateway/app.py#L44) wires everything:
   - the tools every visit shares, from [`tour_tools()`](../../gateway/src/sarjy_gateway/app.py#L120)
     plus `GetWeatherTool`, inside one
     [`Toolbox`](../../gateway/src/sarjy_gateway/app.py#L77);
   - the [`TurnPipeline`](../../gateway/src/sarjy_gateway/app.py#L78), given STT, the
     chat model, TTS, the toolbox, a function that builds the system prompt, and a clock;
   - the routers: `/health` and `/ready`, `/voices`, the identity-cookie middleware, and
     the WebSocket router with its turn limits;
   - the built page, mounted last at `/`
     ([line 111](../../gateway/src/sarjy_gateway/app.py#L111)), so the API routes above
     win over static files.
4. The [`lifespan`](../../gateway/src/sarjy_gateway/app.py#L45) runs when the server starts
   and stops. It opens the database pool without waiting for a connection, applies any
   pending migrations, and starts warming the TTS cache in the background ([D-97](../DECISIONS.md#d-97-a-tts-cache-in-the-gateways-memory-settles-o-23)). On
   shutdown it cancels the warming and closes the pool and both HTTP clients.

## Settings

Every setting is an environment variable named `SARJY_*`, read once at start-up by
[`Settings`](../../gateway/src/sarjy_gateway/settings.py#L7), a pydantic-settings class.
Its configuration on [line 13](../../gateway/src/sarjy_gateway/settings.py#L13) carries
the important choices:

- `env_prefix="SARJY_"`: the field `tts_url` is read from `SARJY_TTS_URL`.
- `env_file=".env"`: locally, the git-ignored `.env` fills the gaps. On Cloud Run the
  variables come from Terraform and Secret Manager ([chapter 10](10-shipping.md)).
- `env_ignore_empty=True`: an empty value counts as unset, so the default applies.
  [`.env.example`](../../.env.example) lists every name with an empty value, so a copy of
  it works with only the keys filled in.
- `frozen=True`: nothing changes a setting after start-up.

`PORT` is the one variable without the prefix, because Cloud Run sets it
([line 19](../../gateway/src/sarjy_gateway/settings.py#L19)). Keys and the database URL
are `SecretStr`, which keeps them out of logs and error messages. Limits are checked by
Pydantic (`gt=0`, `ge=0`), so a bad value stops the gateway at start-up rather than
mid-turn.

The settings fall into a few groups:

| Group | Settings and defaults |
| --- | --- |
| Experiments | `pipeline_mode` = `sentence` ([D-76](../DECISIONS.md#d-76-sentence-streaming-every-written-sentence-spoken-in-order-tools-first), [D-77](../DECISIONS.md#d-77-the-page-plays-sentence-clips-back-to-back-sentence-mode-by-default)); `tool_payload` = `lean` ([D-91](../DECISIONS.md#d-91-token-counts-logged-per-round-lean-tool-payloads-stay)) |
| Turn limits | `turn_window_seconds` = 600, `turns_per_user` = 30, `turns_per_ip` = 90, `max_turns_per_visit` = 100 ([D-72](../DECISIONS.md#d-72-turn-limits-in-memory-per-user-and-per-ip-counted-per-instance)); `max_turn_audio_bytes` = 1,000,000; `max_history_turns` = 6 |
| Speech to text | `groq_api_key`, `stt_model` = `whisper-large-v3-turbo` ([D-51](../DECISIONS.md#d-51-stt-groq-whisper-large-v3-turbo-one-clip-per-turn)) |
| Chat models | `llm_primary` = `groq`; Groq: `llm_api_key`, `llm_model` = `openai/gpt-oss-120b`, `llm_reasoning_effort` = `low`, `llm_temperature` = 0.5, `llm_max_tokens` = 300 ([D-96](../DECISIONS.md#d-96-claude-haiku-55-first-gpt-oss-120b-as-the-fallback)); Claude: `anthropic_api_key`, `claude_model` = `claude-haiku-5-5`, `claude_effort` = `low`, `claude_prompt_cache` = true ([D-63](../DECISIONS.md#d-63-groq-and-claude-haiku-55-switchable-each-the-others-fallback), [D-93](../DECISIONS.md#d-93-claude-caches-the-shared-part-of-the-prompt)) |
| TTS | `tts_url`, `tts_auth` = `none` (`id_token` on Cloud Run, [D-45](../DECISIONS.md#d-45-tts-is-private-the-gateway-calls-it-with-its-own-identity)), `tts_cache_bytes` = 32,000,000 ([D-97](../DECISIONS.md#d-97-a-tts-cache-in-the-gateways-memory-settles-o-23)) |
| SayTech and weather | `saytech_base_url`, `saytech_timeout_seconds` = 3, `saytech_cache_seconds` = 300 ([D-58](../DECISIONS.md#d-58-saytech-answers-are-cached-in-the-gateway-with-a-last-known-good-copy)); `weather_url`, `weather_timeout_seconds` = 3 |
| Database and cookie | `database_url`, `database_pool_max` = 4 ([D-64](../DECISIONS.md#d-64-postgres-18-on-the-smallest-cloud-sql-tier-reached-through-cloud-runs-socket)); `cookie_secure` = true |

`llm_primary` defaults to `groq` in code, but Terraform sets it to `claude` on Cloud Run
([`variables.tf` line 19](../../infra/variables.tf#L19)) and
[`compose.yaml`](../../compose.yaml) does the same, so Claude Haiku answers first in
production and in the local stack ([D-69](../DECISIONS.md#d-69-claude-answers-first-for-now), [D-96](../DECISIONS.md#d-96-claude-haiku-55-first-gpt-oss-120b-as-the-fallback)). Run the gateway on its own and it is Groq,
unless `.env` says otherwise.

## One Protocol, one adapter

Each external service sits behind a small `typing.Protocol` with one real adapter ([D-24](../DECISIONS.md#d-24-every-external-service-behind-an-interface)).
The rest of the gateway only knows the Protocol, and every dependency is passed in, never
imported and called directly.

| Service | Protocol | Real adapter | Stand-in without config | Fake in tests |
| --- | --- | --- | --- | --- |
| Speech to text | [`SpeechToText`](../../gateway/src/sarjy_gateway/stt.py#L38) | `GroqSpeechToText` | `MissingSpeechToText` | `FakeSpeechToText` |
| Chat model | [`ChatModel`](../../gateway/src/sarjy_gateway/llm.py#L89) | `ClaudeChatModel`, `OpenAiCompatibleChatModel` | `MissingChatModel` | `FakeChatModel` |
| Text to speech | [`TextToSpeech`](../../gateway/src/sarjy_gateway/tts.py#L30) | `HttpTextToSpeech` | `MissingTextToSpeech` | `FakeTextToSpeech` |
| SayTech | [`Catalogue`](../../gateway/src/sarjy_gateway/catalogue.py#L296) | `SayTechCatalogue` | none needed: the API is public | `FakeCatalogue` |
| Weather | [`Weather`](../../gateway/src/sarjy_gateway/weather.py#L98) | `OpenMeteoWeather` | none needed: no key | `FakeWeather` |
| Database ping | [`Database`](../../gateway/src/sarjy_gateway/database.py#L23) | `PostgresDatabase` | `MissingDatabase` | `FakeDatabase` |
| Visits and turns | [`ConversationStore`](../../gateway/src/sarjy_gateway/conversation_store.py#L83) | `PostgresConversationStore` | `MissingConversationStore` | `FakeConversationStore` |
| Facts | [`FactStore`](../../gateway/src/sarjy_gateway/memory.py#L34) | `PostgresFactStore` | `MissingFactStore` | `FakeFactStore` |
| A tool | [`Tool`](../../gateway/src/sarjy_gateway/tools.py#L23) | one class per tool | none | `FakeWeatherTool`, `FakeFactTool` |

Two things are worth knowing about this table.

**The `Missing*` stand-ins.** Without a key or URL, `build_services` puts in an object that
fails every call with a message naming the missing variable, for example
"SARJY_TTS_URL is not set". The gateway still starts, which is how the page can be worked
on alone, and the pipeline treats the failure like any provider failure: the turn ends
with an error code, not a crash.

**Wrappers are adapters too.** Three classes take an object of a Protocol and are one
themselves: [`CachedTextToSpeech`](../../gateway/src/sarjy_gateway/tts_cache.py#L33) keeps
spoken sentences ([D-97](../DECISIONS.md#d-97-a-tts-cache-in-the-gateways-memory-settles-o-23)), [`CachedCatalogue`](../../gateway/src/sarjy_gateway/catalogue_cache.py#L73)
keeps SayTech's answers ([D-58](../DECISIONS.md#d-58-saytech-answers-are-cached-in-the-gateway-with-a-last-known-good-copy)), and
[`FallbackChatModel`](../../gateway/src/sarjy_gateway/llm.py#L199) asks a second model when
the first fails ([D-63](../DECISIONS.md#d-63-groq-and-claude-haiku-55-switchable-each-the-others-fallback)). The pipeline can't tell a wrapper from the real thing, so caching
and fallback added no code to it.

Clocks are injected the same way. Timings use `time.monotonic`, which never jumps;
`GetWeatherTool` gets `time.time`, because it needs today's date. Tests pass a
`ManualClock` that only moves when told, or a `TickingClock` that adds 10 ms per reading,
so marks are predictable ([`fakes.py` line 183](../../gateway/tests/fakes.py#L183) and
[line 192](../../gateway/tests/fakes.py#L192)).

## Logging

[`JsonFormatter`](../../gateway/src/sarjy_gateway/logs.py#L7) writes one JSON line per
event with `severity`, `message`, `logger` and `time`, which Cloud Logging reads ([D-42](../DECISIONS.md#d-42-logs-are-json-lines-from-the-standard-library)).
The code logs with a mapping as the only argument, for example
`logger.info("turn %(turn_id)s completed", {"turn_id": ..., "marks": ...})`. The standard
library keeps that mapping as `record.args`, and the formatter copies it into the line as
searchable fields ([line 18](../../gateway/src/sarjy_gateway/logs.py#L18)). There is no
`print` in application code.

## When something fails at start-up

- **No database URL.** The `Missing*` stores stand in. Voice works; memory, history and
  timings are not kept, and `GET /ready` answers 503 with the reason.
- **Database unreachable or a migration fails.** The pool opens without waiting, and
  [`MigrationError`](../../gateway/src/sarjy_gateway/app.py#L53) is logged as "starting
  without an up-to-date database". Voice carries on ([D-64](../DECISIONS.md#d-64-postgres-18-on-the-smallest-cloud-sql-tier-reached-through-cloud-runs-socket), [D-65](../DECISIONS.md#d-65-schema-migrations-at-startup-and-tests-on-a-real-postgres)).
- **TTS down while the cache warms.** Warming stops quietly; those phrases are made the
  first time they are said instead.
- **A setting with a bad value.** Pydantic raises when `Settings()` is built, and the
  process stops before it serves anything.

## How it is tested

The tests never touch the network. They come in two layers.

- **Logic, with fakes.** [`gateway/tests/fakes.py`](../../gateway/tests/fakes.py) has one
  fake per service Protocol. Each records what it was asked (`FakeChatModel.requests`,
  `FakeCatalogue.queries`) and can be told to raise an `error`. `FakeChatModel` plays
  scripted rounds of events, repeating the last, which is how the tool loop is tested;
  `FakeWeatherTool` can sleep for `seconds`, which is how the tool timeout is tested.
  [`test_app.py`](../../gateway/tests/test_app.py#L28) builds the whole app from
  `Missing*` providers and fakes, with no HTTP client.
- **Adapters, over a mock transport.** Each adapter test sends its requests through
  `httpx2.MockTransport`, so no request leaves the machine. The chat, SayTech and weather
  tests answer with real responses saved in
  [`gateway/tests/fixtures/`](../../gateway/tests/fixtures/) (Groq's and Claude's event
  streams, SayTech's JSON, Open-Meteo's JSON), so the parsing is checked against what the
  providers really send.

[`test_settings.py`](../../gateway/tests/test_settings.py) checks that `PORT` is read,
that a bad value fails at start-up and that an empty value keeps its default.
[`test_services.py`](../../gateway/tests/test_services.py) checks which chat model is
built for each combination of keys. The database tests run on a real Postgres, never a
fake: the [`database_url`](../../gateway/tests/conftest.py#L17) fixture skips them locally
without `SARJY_TEST_DATABASE_URL`, and fails them in CI, where a skip would hide missing
coverage ([D-65](../DECISIONS.md#d-65-schema-migrations-at-startup-and-tests-on-a-real-postgres)).
