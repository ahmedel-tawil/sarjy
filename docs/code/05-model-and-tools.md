# 5. The model and its tools

Sarjy knows no tours and no prices of its own. The prompt tells the model to take every
price, availability and forecast from a tool result in the same conversation ([D-20](../DECISIONS.md#d-20-light-practical-conversation-guardrails)); no
code checks the spoken words yet, which was left to the optional guardrail milestone. This chapter covers the
loop that lets the model call tools, the prompt that tells it to, the two model providers
behind one interface, and the tools themselves.

## The tool loop: `_converse`

[`_converse`](../../gateway/src/sarjy_gateway/turn.py#L316) runs the model's rounds for one
turn ([D-57](../DECISIONS.md#d-57-the-tool-loop-and-what-llm_first_token-means-with-tools)). It builds the messages once:

1. the shared part of the system prompt, marked as a cache point;
2. this turn's part of the system prompt;
3. the recent turns from `conversation.history`;
4. the traveller's question.

The toolbox is the shared tools plus this visit's memory tools
([line 332](../../gateway/src/sarjy_gateway/turn.py#L332)). Then, for each round:

1. **Ask.** [`_ask`](../../gateway/src/sarjy_gateway/turn.py#L361) streams one request.
   [`_read`](../../gateway/src/sarjy_gateway/turn.py#L372) collects the text, hands each
   piece to the speaker when there is one, and gathers the pieces of tool calls, which
   [`assemble_tool_calls`](../../gateway/src/sarjy_gateway/llm.py#L353) rebuilds into whole
   calls. The provider's token counts are logged for the round ([D-91](../DECISIONS.md#d-91-token-counts-logged-per-round-lean-tool-payloads-stay)).
2. **End the round.** The speaker flushes any unfinished sentence ([chapter 4](04-turn.md)).
3. **No tool calls?** Then this round is the answer, and the loop returns.
4. **Announce.** For each call, [`activity_of`](../../gateway/src/sarjy_gateway/activity.py#L28)
   makes a line such as "Looking for tours in Dubai" from fixed templates and the call's
   arguments, and the page gets it as an `activity` message before the tools run ([D-94](../DECISIONS.md#d-94-activity-status-from-fixed-templates-sent-before-each-tool-runs)).
   The model never writes these words, so they can't promise anything.
5. **Run the tools** with [`Toolbox.run_all`](../../gateway/src/sarjy_gateway/tools.py#L59).
6. **Stop if the round answered while saving facts**, the first guard below.
7. **Append** the model's message with its tool calls, then one `tool` message per result,
   then, with sentence streaming, the second guard's note, and go round again.

### Tools side by side, with a timeout each

`run_all` starts every call of a round at once with `asyncio.gather`, and returns the
results in the order of the calls. Each call gets 5 seconds
([`TOOL_TIMEOUT_SECONDS`](../../gateway/src/sarjy_gateway/tools.py#L17)). A bad call never
fails the turn: an unknown tool, arguments that don't validate, a `ToolError` or a
timeout each become a result such as `{"error": "get_weather took longer than 5 seconds."}`
([`_run`](../../gateway/src/sarjy_gateway/tools.py#L71)). The model reads it and answers in
words ("I can't check the weather right now"). Each tool validates its arguments with a
Pydantic model whose JSON schema is also what the model is shown in its
[`ToolSpec`](../../gateway/src/sarjy_gateway/llm.py#L39), so the two can't drift apart.

### The two guards

On 10 Oct a greeting came out twice: Claude answered and saved the name in one round, then
answered again when given the save's result, and sentence streaming spoke both. Two guards
followed ([D-95](../DECISIONS.md#d-95-a-turn-never-says-its-answer-twice)).

- [`answered_while_saving`](../../gateway/src/sarjy_gateway/turn.py#L409): a round that
  wrote words and whose only calls were `remember_fact` or `forget_fact`, all successful,
  is the whole answer. The facts are saved and the model is not asked again. A failed
  save still goes back to the model, so it can say so.
- [`already_heard`](../../gateway/src/sarjy_gateway/turn.py#L419): with sentence streaming,
  when a round wrote words before other tool calls, the next round gets a system note
  quoting what the traveller already heard and asking the model to carry on without
  repeating, greeting or thanking again. This makes repeats rarer, not impossible.

### The round limit

Up to [`MAX_TOOL_ROUNDS`](../../gateway/src/sarjy_gateway/turn.py#L44), 3, rounds offer
the tools. One more round offers none, so the model has to answer with what it has. If it
still asks for tools, the loop ends and the turn fails with `llm_failed`
([line 359](../../gateway/src/sarjy_gateway/turn.py#L359)). The check comes after the
loop, so that round's calls still run first, and a round that wrote words and only saved
facts still ends the turn as its answer.

## What the next turn remembers: `Conversation.remember`

After a turn succeeds, [`remember`](../../gateway/src/sarjy_gateway/turn.py#L98) stores it
as messages: the question, then, if tools were called, one assistant message with all the
turn's tool calls and one `tool` message per result, then the reply. Only the last 6 turns
are kept, and a turn is dropped whole, so a tool call never loses its result.

Keeping the results is [D-100](../DECISIONS.md#d-100-a-turns-history-keeps-its-tool-calls-and-results): without them, a later turn saw prices in Sarjy's earlier
replies with no search behind them and took them back as made up. The cost is a few
thousand tokens per visit, after the cache point.

## The prompt

[`prompts.py`](../../gateway/src/sarjy_gateway/prompts.py) holds the rules, version 1.4.
After a short paragraph on who Sarjy is, and that travellers mean Dubai unless they name
another city, comes the most important rule: you know no tours and no prices of your own,
so call `search_tours` before naming any ([D-62](../DECISIONS.md#d-62-prompt-v1-the-no-guessing-rule-first-defaults-in-code-context-during-stt)). Then how to speak (under fifty words, no lists or
web addresses, [D-71](../DECISIONS.md#d-71-prompt-v11-names-weather-only-from-the-tool-under-fifty-words)), what Sarjy covers, how to use each tool (before a tool, nothing or one short
sentence to the traveller, never the plan, [D-105](../DECISIONS.md#d-105-before-a-tool-one-short-sentence-to-the-traveller-never-the-plan); `get_tour` only for details, "price on request" said as such, a cooler time
when it is 35 degrees or hotter, weather only from `get_weather`, availability checked
whenever a date comes up, [D-99](../DECISIONS.md#d-99-live-availability-from-saytech-never-cached-unknown-said-honestly)), and how to use memory.

[`system_prompt`](../../gateway/src/sarjy_gateway/prompts.py#L98) returns a
[`Prompt`](../../gateway/src/sarjy_gateway/prompts.py#L89) in two parts ([D-93](../DECISIONS.md#d-93-claude-caches-the-shared-part-of-the-prompt)):

| Part | Contents | Changes |
| --- | --- | --- |
| `shared` | The rules, then SayTech's catalogue: cities with their tour counts, the categories to search by, the general FAQ answers | Only when SayTech's context changes |
| `this_turn` | The traveller's facts with their keys, today's date (also as `YYYY-MM-DD`) and the time in the UAE | Every turn |
| `today` | The UAE date given to the model | Not sent; the activity wording counts days from it |

The shared part is the same for every traveller and turn, so Claude can cache it; the facts
and the time come after it, so they never change the cached bytes. The facts' keys let
"actually, it's blue" reuse `favourite_colour` ([D-67](../DECISIONS.md#d-67-memory-facts-per-user-tools-per-visit-the-prompt-kept-current-in-memory)).

**Caching.** The shared message carries `cache_point=True`
([`turn.py` line 327](../../gateway/src/sarjy_gateway/turn.py#L327)). The Claude adapter
turns that into a `cache_control` mark on that system block
([`claude.py` line 129](../../gateway/src/sarjy_gateway/claude.py#L129)), so Claude caches
the tools and the shared prompt together, for 5 minutes after their last use, across
travellers. A round's input then bills at about a third. The first word came no sooner, so
caching is a cost decision, not a latency one ([D-93](../DECISIONS.md#d-93-claude-caches-the-shared-part-of-the-prompt)).

## One interface, two adapters, a fallback

Every model sits behind [`ChatModel`](../../gateway/src/sarjy_gateway/llm.py#L89): one
method, `stream(messages, tools)`, used as `async with model.stream(...) as events:`. The
events are the gateway's own: `TextDelta`, `ToolCallDelta`, `Finished` and `Usage`. The
HTTP response stays open exactly as long as the `async with` block.

| | [`ClaudeChatModel`](../../gateway/src/sarjy_gateway/claude.py#L50) | [`OpenAiCompatibleChatModel`](../../gateway/src/sarjy_gateway/llm.py#L154) |
| --- | --- | --- |
| Provider | Claude Haiku 5.5, first on Cloud Run ([D-69](../DECISIONS.md#d-69-claude-answers-first-for-now), [D-96](../DECISIONS.md#d-96-claude-haiku-55-first-gpt-oss-120b-as-the-fallback)) | Groq's `openai/gpt-oss-120b`, the fallback ([D-96](../DECISIONS.md#d-96-claude-haiku-55-first-gpt-oss-120b-as-the-fallback)) |
| Client | Anthropic's SDK, retries off ([D-63](../DECISIONS.md#d-63-groq-and-claude-haiku-55-switchable-each-the-others-fallback)) | `httpx2`, reading the server-sent events itself: about thirty lines ([D-53](../DECISIONS.md#d-53-one-hand-written-client-for-openai-compatible-chat-apis)) |
| Options | Thinking off, effort `low`, no temperature (Haiku 5.5 only takes its default), at most 300 tokens | Temperature 0.5, reasoning effort `low`, at most 300 tokens |
| Translation | [`claude_request`](../../gateway/src/sarjy_gateway/claude.py#L115): system messages become the `system` blocks, a round's tool results go in one user message, tool calls become `tool_use` blocks | [`wire_message`](../../gateway/src/sarjy_gateway/llm.py#L264): the OpenAI shape, almost as is |
| Errors | `RateLimitError` becomes `ChatRateLimitedError`; status and connection errors become `ChatModelError` | 429 becomes `ChatRateLimitedError`; other HTTP errors, network errors, or an error sent inside the stream become `ChatModelError` |

One detail of `claude_request`: every system message goes into Claude's `system` list,
wherever it sits, so the `already_heard` note becomes a third system block for Claude, while
Groq gets it in place, after the tool results.

[`FallbackChatModel`](../../gateway/src/sarjy_gateway/llm.py#L199) asks the first model, and
if opening its stream fails with a `ChatModelError` (a rate limit, a refused key, a server
or network error), sends the same request to the second. Once a stream is open nothing
switches over: words may already have been spoken. Which model answers is logged.
[`build_chat_model`](../../gateway/src/sarjy_gateway/services.py#L116) only builds the
fallback when both keys are set.

## The tools

| Tool | Arguments | Calls | Returns |
| --- | --- | --- | --- |
| [`search_tours`](../../gateway/src/sarjy_gateway/tour_tools.py#L77) | `query`, `city`, `max_price_aed`, `category`, `accessible` | SayTech search, through the cache | Up to 5 tours: name, type, slug, city, price in words, accessible, link; and the total |
| [`get_tour`](../../gateway/src/sarjy_gateway/tour_tools.py#L94) | `slug`, `product_type` | SayTech detail, through the cache | Summary, duration, tickets with adult and child prices, policies, restrictions and notes |
| [`check_availability`](../../gateway/src/sarjy_gateway/tour_tools.py#L112) | `slug`, `product_type`, `date`, `days` (1 to 7), `adults`, `children`, `infants` | SayTech availability, never cached ([D-99](../DECISIONS.md#d-99-live-availability-from-saytech-never-cached-unknown-said-honestly)) | Each day's and ticket's status and places left; for one day, departures, price and SayTech's own total for the party |
| [`get_weather`](../../gateway/src/sarjy_gateway/weather_tool.py#L32) | `city` (default Dubai), `date` | Open-Meteo | Conditions, high, low, chance of rain, and the temperature at 6, 9, 12, 15, 18 and 21 o'clock |
| `remember_fact`, `forget_fact` | `key`, `value`; `key` | Postgres | [Chapter 6](06-memory-and-storage.md) |

### SayTech: `catalogue.py` and `catalogue_cache.py`

[`SayTechCatalogue`](../../gateway/src/sarjy_gateway/catalogue.py#L316) calls SayTech's
read-only assistant API, built for Sarjy ([D-56](../DECISIONS.md#d-56-saytech-a-read-only-assistant-api-built-for-sarjy)), with a 3-second timeout. It reads the
answers into `Api*` models, which ignore fields Sarjy doesn't use, then maps them to lean
models for the model to read ([D-18](../DECISIONS.md#d-18-five-tools-with-small-typed-results), [D-59](../DECISIONS.md#d-59-tool-results-and-arguments-shaped-for-the-model-and-for-groq)). The data is cleaned in this one place ([D-19](../DECISIONS.md#d-19-saytech-adapter-rules)):

- [`price_text`](../../gateway/src/sarjy_gateway/catalogue.py#L511): no price becomes
  "price on request", never zero. Prices are words before the model sees them.
- [`tour_path`](../../gateway/src/sarjy_gateway/catalogue.py#L402): slugs keep their spaces
  and typos ("DUNE- BUGGY") and are percent-encoded, slash included, so a slug can never
  reach another path.
- [`shared_policies`](../../gateway/src/sarjy_gateway/catalogue.py#L460): when every ticket
  has the same children's and cancellation policies, they are stated once, as
  `every_ticket`. The buggy's details went from 5.3 KB to 2.1 KB.
- [`answer_from`](../../gateway/src/sarjy_gateway/tour_tools.py#L185) leaves out null
  fields, since every request of a turn sends every result again.

A 400 or 404 is a
[`CatalogueQueryError`](../../gateway/src/sarjy_gateway/catalogue.py#L286): SayTech said no,
and its message ("Known cities: …") goes to the model so it can try again. A timeout, a
network error, any other error status, a refusal not in SayTech's error shape, or an answer
off the contract is a
[`CatalogueUnavailableError`](../../gateway/src/sarjy_gateway/catalogue.py#L292), which
the model hears as "The tour catalogue can't be reached right now."

[`LastGoodCache`](../../gateway/src/sarjy_gateway/catalogue_cache.py#L37) keeps the
context, each search and each tour for 5 minutes, as SayTech's `Cache-Control` allows, and
keeps older copies too. If SayTech is unavailable, the last good copy is served at any age,
with a warning, so the demo survives an outage. A refusal is SayTech's real answer, so it
is never cached or hidden behind an old copy. Each cache holds at most 256 answers ([D-58](../DECISIONS.md#d-58-saytech-answers-are-cached-in-the-gateway-with-a-last-known-good-copy)).

Availability goes straight to SayTech, past the cache, because it changes as people book;
a stale "available" is worse than a slower answer ([D-99](../DECISIONS.md#d-99-live-availability-from-saytech-never-cached-unknown-said-honestly)). For a range of days, Sarjy drops
the departure times and SayTech sends no prices, which keeps the answer short.
`SARJY_TOOL_PAYLOAD=raw` swaps the search and detail tools for ones that pass SayTech's
answers on untouched, for experiment 5 ([`tour_tools()`](../../gateway/src/sarjy_gateway/app.py#L120)).

### Weather: `weather.py` and `weather_tool.py`

[`GetWeatherTool`](../../gateway/src/sarjy_gateway/weather_tool.py#L32) finds the city in a
fixed table of eight UAE places, matching letters only ("abu-dhabi" is "Abu Dhabi"), so no
geocoding call is needed. `city` defaults to Dubai in code as well as in the prompt: told
to assume Dubai, the model still picked Abu Dhabi. The tool checks the date itself, today
to 15 days ahead in UAE time, a fixed UTC+4
([`UAE_TIME`](../../gateway/src/sarjy_gateway/weather.py#L11)), and explains a bad one in
words without a request ([D-60](../DECISIONS.md#d-60-weather-open-meteo-a-fixed-table-of-uae-cities-days-in-uae-time)). [`OpenMeteoWeather`](../../gateway/src/sarjy_gateway/weather.py#L123)
asks Open-Meteo, which needs no key, for that one day.

### Links: `links.py`

Sarjy never says a web address, but the page shows the pages of the tours a reply names
([D-90](../DECISIONS.md#d-90-tour-links-beside-the-reply-a-remembered-voice-and-reconnecting)). [`tour_links`](../../gateway/src/sarjy_gateway/links.py#L61) looks only at this
turn's tool results, so a link is never invented. A tour counts as named when the reply
contains two of its distinctive words, or its only one ("Louvre"); words such as "tour" or
"Abu Dhabi" don't count, so "World" alone doesn't link Ferrari World.

## How it is tested

- [`test_turn.py`](../../gateway/tests/test_turn.py): the loop with scripted
  `FakeChatModel` rounds, the round limit and both guards.
- [`test_tools.py`](../../gateway/tests/test_tools.py): bad calls become error results,
  calls run side by side, the timeout.
- [`test_llm.py`](../../gateway/tests/test_llm.py) and
  [`test_claude.py`](../../gateway/tests/test_claude.py): recorded Groq and Claude streams,
  the request shapes, cache marks, and the fallback.
- [`test_prompts.py`](../../gateway/tests/test_prompts.py): the shared part is the same for
  every traveller and time.
- [`test_catalogue.py`](../../gateway/tests/test_catalogue.py),
  [`test_catalogue_cache.py`](../../gateway/tests/test_catalogue_cache.py),
  [`test_tour_tools.py`](../../gateway/tests/test_tour_tools.py) and
  [`test_availability.py`](../../gateway/tests/test_availability.py): recorded SayTech
  answers, the cleaning rules, refusals, the last good copy, availability.
- [`test_weather.py`](../../gateway/tests/test_weather.py),
  [`test_weather_tool.py`](../../gateway/tests/test_weather_tool.py),
  [`test_activity.py`](../../gateway/tests/test_activity.py) and
  [`test_links.py`](../../gateway/tests/test_links.py): the forecast, the activity wording
  and the links.
