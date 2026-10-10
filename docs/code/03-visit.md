# 3. A visit opens

A visit is one WebSocket connection, normally one page load. The page opens its socket as
soon as it loads, before the traveller asks anything, so the memory panel is full by the
first question and the handshake is not part of the first turn's wait ([D-68](../DECISIONS.md#d-68-memory-panel-the-whole-list-over-the-socket-opened-with-the-page)). Everything
about the visit lives in [`VoiceRouter`](../../gateway/src/sarjy_gateway/voice.py#L109),
in `voice.py`. This chapter follows it from the handshake to the loop that reads the
page's messages, and then looks at the turn limits.

## Connecting

The socket's handler is [`voice()`](../../gateway/src/sarjy_gateway/voice.py#L137). In
order, it:

1. **Reads the identity cookie.**
   [`user_id_from`](../../gateway/src/sarjy_gateway/identity.py#L28) parses the
   `sarjy_user` cookie into a `UserId`. Without a valid one, the socket is closed before it
   is accepted ([chapter 2](02-api.md)). `UserId`, `SessionId` and `TurnId` are separate `NewType`s, so
   the type checker stops one being passed where another is expected ([D-67](../DECISIONS.md#d-67-memory-facts-per-user-tools-per-visit-the-prompt-kept-current-in-memory)).
2. **Accepts the socket.**
3. **Wakes TTS.** [`_wake_tts`](../../gateway/src/sarjy_gateway/voice.py#L211) starts a
   background task that asks TTS for its voices. When TTS has scaled to zero, that request
   starts an instance, which takes about 6 s, while the traveller is still reading and
   speaking instead of during their first turn ([D-78](../DECISIONS.md#d-78-cold-starts-tts-woken-when-a-visit-opens-warm-instances-a-setting)). A failure is only logged. The
   router keeps the task in a set, because asyncio holds only a weak reference to a task
   and could otherwise lose it before it finishes
   ([line 130](../../gateway/src/sarjy_gateway/voice.py#L130)).
4. **Works out the visitor's IP**, for the limits below.
5. **Serves the visit** in [`_serve`](../../gateway/src/sarjy_gateway/voice.py#L156).

`_serve` sets up the visit's state before reading any message:

- a [`TurnAudio`](../../gateway/src/sarjy_gateway/turn_audio.py#L1) buffer for the audio
  chunks of the turn being spoken;
- a [`Conversation`](../../gateway/src/sarjy_gateway/turn.py#L72), the visit's memory;
- the session, stored by
  [`_start_session`](../../gateway/src/sarjy_gateway/voice.py#L223): the user is upserted
  and a new session row added, in one transaction ([chapter 6](06-memory-and-storage.md));
- the user's facts, loaded once by
  [`_load_facts`](../../gateway/src/sarjy_gateway/voice.py#L232);
- the voice, taken from the `voice` fact if the user picked one on an earlier visit
  ([D-90](../DECISIONS.md#d-90-tour-links-beside-the-reply-a-remembered-voice-and-reconnecting));
- a [`SocketListener`](../../gateway/src/sarjy_gateway/voice.py#L64), the one object that
  turns the pipeline's events into socket messages;
- this visit's memory tools, `RememberFactTool` and `ForgetFactTool`, built for this user,
  this conversation and this listener ([D-67](../DECISIONS.md#d-67-memory-facts-per-user-tools-per-visit-the-prompt-kept-current-in-memory), [chapter 6](06-memory-and-storage.md)).

Then it sends `memory` with every fact, and `history` with the user's earlier visits
([line 169](../../gateway/src/sarjy_gateway/voice.py#L169)).

## The `Conversation`

[`Conversation`](../../gateway/src/sarjy_gateway/turn.py#L72) is a plain dataclass that
lives as long as the socket. It is the visit's whole state:

| Field | What it holds |
| --- | --- |
| `recent` | The last 6 turns, each as its messages: question, tool calls, tool results, reply ([D-100](../DECISIONS.md#d-100-a-turns-history-keeps-its-tool-calls-and-results), [chapter 5](05-model-and-tools.md)) |
| `facts` | The user's facts, kept current by the memory tools, so no turn reads them from the database ([D-67](../DECISIONS.md#d-67-memory-facts-per-user-tools-per-visit-the-prompt-kept-current-in-memory)) |
| `tools` | The visit's own tools, added to the shared ones for every turn |
| `voice` | The voice for the next reply, or `None` for TTS's default |
| `user_id`, `session_id` | Who is talking, and the stored visit; `session_id` is `None` when the database was unavailable |
| `client_ip`, `turns_taken` | What the limits count |

Nothing a turn reads comes from the database. Apart from the memory tools, which write
by `user_id`, only `session_id` ties the visit to Postgres.

## The message loop

The loop on [line 171](../../gateway/src/sarjy_gateway/voice.py#L171) reads one frame at a
time. A disconnect ends the visit. A binary frame is added to the turn's audio. A text
frame goes to [`_control`](../../gateway/src/sarjy_gateway/voice.py#L181), which parses it
as a `ClientMessage` and dispatches on its type with a `match`:

| Message | Handler |
| --- | --- |
| `turn_end` | [`_end_turn`](../../gateway/src/sarjy_gateway/voice.py#L307): checks, then runs the turn |
| `turn_cancel` | `audio.take()`, which empties the buffer |
| `set_voice` | [`_set_voice`](../../gateway/src/sarjy_gateway/voice.py#L285) |
| `replay` | [`_replay`](../../gateway/src/sarjy_gateway/voice.py#L249) |
| `forget_me` | [`_forget_me`](../../gateway/src/sarjy_gateway/voice.py#L275) |
| `browser_marks` | Logs the TTFA and stores the two marks |

Each handler finishes before the next frame is read. During a turn the gateway reads
nothing else from the page, which is fine: the page allows one turn at a time ([D-54](../DECISIONS.md#d-54-browser-marks-go-back-over-the-voice-socket-one-turn-at-a-time)).

**`TurnAudio`.** [`add`](../../gateway/src/sarjy_gateway/turn_audio.py#L7) appends each
chunk. If the turn goes over `SARJY_MAX_TURN_AUDIO_BYTES`, it throws away everything so
far and remembers it was too long, since a cut recording would not decode as a valid file.
[`take`](../../gateway/src/sarjy_gateway/turn_audio.py#L21) returns the clip and resets
the buffer for the next turn.

**`_end_turn`.** It refuses the turn if the audio was too long, if there is none, if the
visit has taken 100 turns, or if the limits say no. Otherwise it counts the turn, runs
[`TurnPipeline.run`](../../gateway/src/sarjy_gateway/turn.py#L238) ([chapter 4](04-turn.md)), sends
`marks`, and only then saves the turn and its marks. Saving last means the database never
delays a reply ([D-66](../DECISIONS.md#d-66-identity-by-cookie-one-session-per-visit-turns-saved-after-they-are-spoken)). A `TurnError` from the pipeline becomes an `error` message with its
code and the turn's id, and the visit carries on.

**`_set_voice`.** It asks TTS for its voices, refuses one it doesn't offer, sets
`conversation.voice`, and saves the choice as the `voice` fact, which also sends a new
`memory` list.

**`_replay`.** It checks the limits, then fetches the stored reply with
[`reply_of`](../../gateway/src/sarjy_gateway/conversation_store.py#L203), whose SQL only
finds a turn of this user's own visits. It splits the reply with
[`sentences_of`](../../gateway/src/sarjy_gateway/sentences.py#L80), the same splitting
as a live turn, synthesises each sentence in the visit's current voice, sends each as
`audio` plus a WAV frame, and ends with `replay_done`. A replay sends no marks and is not
saved as a turn ([D-92](../DECISIONS.md#d-92-earlier-visits-sent-with-the-visit-replays-re-synthesised)).

**`_forget_me`.** It deletes every fact of the user, empties the visit's copy and sends an
empty `memory`. Sessions and turns stay ([D-68](../DECISIONS.md#d-68-memory-panel-the-whole-list-over-the-socket-opened-with-the-page)). The `voice` fact goes with the rest, so the
next visit starts with the default voice; this visit keeps the voice it has.

## The turn limits

[`limits.py`](../../gateway/src/sarjy_gateway/limits.py) protects the public URL and the
budget ([D-21](../DECISIONS.md#d-21-protecting-the-public-url-and-the-budget), [D-72](../DECISIONS.md#d-72-turn-limits-in-memory-per-user-and-per-ip-counted-per-instance)).

[`SlidingWindow`](../../gateway/src/sarjy_gateway/limits.py#L19) keeps, for each key, a
queue of the times its turns started.
[`has_room`](../../gateway/src/sarjy_gateway/limits.py#L30) drops the times older than the
window, then compares what is left with the limit.
[`record`](../../gateway/src/sarjy_gateway/limits.py#L39) adds the current time. A
sliding window was chosen over a fixed one-minute window, where a burst on either side of
the boundary would get twice the limit ([D-72](../DECISIONS.md#d-72-turn-limits-in-memory-per-user-and-per-ip-counted-per-instance)).

[`TurnLimits.allow`](../../gateway/src/sarjy_gateway/limits.py#L57) asks both windows,
the user's (30 in 10 minutes) and the IP's (90 in 10 minutes), and records the turn in
both only when both have room. A refused turn uses up neither.

A bot that changes its cookie on every turn would leave keys that never come back. So when
a new key would take the count past
[`MAX_KEYS`](../../gateway/src/sarjy_gateway/limits.py#L13), 10,000, the keys with no turn
inside the window are dropped first.

The counts live in the instance's memory. That needs no table and no extra round trip
on the turn path, but they reset when an instance restarts or a deploy rolls out, and a
visitor whose tabs reach both gateway instances gets up to twice the limit ([D-72](../DECISIONS.md#d-72-turn-limits-in-memory-per-user-and-per-ip-counted-per-instance)).

## When something fails

- **Database unavailable when the visit opens.** No session is stored, so the visit's
  turns are spoken but not saved; facts start empty and there are no earlier visits. Each
  is logged as a warning, and the conversation works ([D-66](../DECISIONS.md#d-66-identity-by-cookie-one-session-per-visit-turns-saved-after-they-are-spoken)).
- **TTS unreachable on the wake-up.** Logged at info level. The visit carries on; the
  first turn will find out for itself.
- **The page closes mid-turn.** The pipeline keeps going until it next sends something,
  which raises `WebSocketDisconnect`. [`voice()`](../../gateway/src/sarjy_gateway/voice.py#L149)
  catches it and logs "browser left mid-turn". The turn is not saved.
- **A deploy.** Cloud Run retires the old revision within about a minute and closes its
  sockets. The page reconnects by itself, which starts a new visit with its own `memory`
  and `history`, but a question asked at that moment is lost ([D-102](../DECISIONS.md#d-102-a-deploy-drops-the-visits-in-progress-so-merges-wait-for-quiet-times)).

## How it is tested

[`test_voice.py`](../../gateway/tests/test_voice.py) runs the router with fakes behind
it. Tests named for what they prove cover the start of a visit
(`test_a_visit_starts_knowing_the_users_facts_and_with_memory_tools`,
`test_a_visit_opens_with_the_users_earlier_visits_newest_first`), the wake-up
(`test_opening_a_visit_wakes_tts_before_the_first_question`,
`test_a_failed_wake_up_does_not_stop_the_visit`), a visit without the database
(`test_without_the_database_the_turn_is_still_answered`), the voice, replay, forgetting,
and a browser that leaves mid-turn.
[`test_limits.py`](../../gateway/tests/test_limits.py) uses a `ManualClock` to move time
by hand: a user waits for the window, a new cookie doesn't escape the IP limit, a refused
turn uses up neither limit, idle keys are dropped, and the visitor's IP is the last
forwarded address.
