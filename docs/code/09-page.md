# 9. The page

The page is React, Vite, TypeScript, Tailwind and shadcn/ui. It is built into the gateway's
image and served from the same origin as the socket, so there is no CORS and the microphone
works under the same HTTPS ([D-13](../DECISIONS.md#d-13-frontend-react-served-by-the-gateway)). The voice logic lives in
[`frontend/src/lib/`](../../frontend/src/lib/), plain TypeScript with no React in it; the
components only draw what it reports. This chapter follows a turn from the page's side,
then looks at voice mode, the view every visit opens in ([D-87](../DECISIONS.md#d-87-every-visit-opens-in-voice-mode-the-full-view-sits-behind-its-close-button)).

## The parts

| File | Role |
| --- | --- |
| [`voice-session.ts`](../../frontend/src/lib/voice-session.ts) | The client side of a turn: press and release, the socket's messages, the player, the marks. Reports through callbacks such as `onSpeak` and `onActivity` |
| [`voice-socket.ts`](../../frontend/src/lib/voice-socket.ts) | The WebSocket to `/ws`, with a queue while connecting and reconnection with back-off |
| [`protocol.ts`](../../frontend/src/lib/protocol.ts) | The zod schemas of every server message, and the client messages ([chapter 2](02-api.md)) |
| [`recorder.ts`](../../frontend/src/lib/recorder.ts), [`level-meter.ts`](../../frontend/src/lib/level-meter.ts) | The microphone, opened for each question, and its level |
| [`player.ts`](../../frontend/src/lib/player.ts) | Clips played back to back on the audio clock |
| [`stages-of.ts`](../../frontend/src/lib/stages-of.ts) | A turn's waterfall stages from both clocks |

[`app.tsx`](../../frontend/src/app.tsx#L193) creates one `VoiceSession` for the page, with
the socket's URL built from the page's own host, and connects it as soon as the page
loads ([line 210](../../frontend/src/app.tsx#L210)).

## A turn, from the page's side

**Press.** [`press()`](../../frontend/src/lib/voice-session.ts#L159) does nothing unless
the session is idle and the microphone isn't already opening: one turn at a time, so each
`speech_end` pairs with its own reply ([D-54](../DECISIONS.md#d-54-browser-marks-go-back-over-the-voice-socket-one-turn-at-a-time)).
[`#startRecording`](../../frontend/src/lib/voice-session.ts#L368) first starts the audio
output inside the gesture, which Safari requires, then opens the microphone. If the
traveller let go while it was opening, or while the browser's permission prompt was
showing, nothing was recorded, so it closes again and shows the "no words" hint.
Otherwise the recorder starts and every chunk goes straight to the socket.

**Release.** [`release()`](../../frontend/src/lib/voice-session.ts#L186) starts a
`TurnInFlight` whose `speechEnd` is `performance.now()`, the turn's first mark, and stops
the recorder. [`heardSpeech`](../../frontend/src/lib/voice-session.ts#L390) then decides:
a press shorter than 0.3 s, or whose loudest moment stayed below -45 dBFS, is cancelled
with `turn_cancel` and never reaches Whisper, which would have turned the silence into
words. If the level couldn't be measured, the turn goes through rather than lose real
speech ([D-55](../DECISIONS.md#d-55-the-browser-drops-presses-with-no-speech-before-they-reach-whisper)). Otherwise the page sends `turn_end`.

**Answer.** [`#receive`](../../frontend/src/lib/voice-session.ts#L275) handles the
gateway's messages:

- `transcript` and `activity` go straight to the screen.
- `audio` names the turn and the words of the clip that comes next. The binary frame
  after it goes to the player.
- When the first clip starts playing,
  [`#clipStarted`](../../frontend/src/lib/voice-session.ts#L200) sets the status to
  speaking, takes `playback_start`, works out TTFA, sends `browser_marks`, and shows the
  reply if it has arrived. Every clip then hands its words and duration to `onSpeak`.
- `reply` is held until the first clip plays, so the words and the voice appear together.
- `marks` is the turn's last message. The page computes the stages, and the turn ends
  when the last clip has finished playing.
- `error` goes to `#report`, which closes the microphone, shows the reply in writing if
  its voice never came, and returns to idle.

If the socket closes mid-turn, a turn still listening or thinking has lost its answer and
reports `connection_lost`. A reply already playing finishes what it has.

## The socket

[`VoiceSocket`](../../frontend/src/lib/voice-socket.ts#L34) opens as the page loads, so
the memory panel fills before the first question ([D-68](../DECISIONS.md#d-68-memory-panel-the-whole-list-over-the-socket-opened-with-the-page)). Messages sent while it is still
connecting wait in a queue and go out on open, so the first words of a turn are kept.
Binary frames arrive as `ArrayBuffer`s; text frames are parsed with
`ServerMessageSchema.safeParse`, and a message that fails the schema is dropped.

After an unexpected close it reconnects after 1, 2 and 4 seconds, then every 10 seconds,
but only while the tab is visible, and at once when the tab comes back into view
([`#reconnectLater`](../../frontend/src/lib/voice-socket.ts#L124)). An open socket is an
active request on Cloud Run, so a forgotten tab shouldn't hold one all night ([D-90](../DECISIONS.md#d-90-tour-links-beside-the-reply-a-remembered-voice-and-reconnecting)). Each
new socket is a new visit for the gateway, with its own `memory` and `history`.

## Microphone and level

[`Recorder`](../../frontend/src/lib/recorder.ts#L40) records Opus in WebM where the browser
can (Chrome) and AAC in MP4 otherwise (Safari), in 250 ms chunks, so the upload overlaps
the speech. The microphone opens for each question and closes at its end, stopping its
tracks, so the browser, macOS and iOS show it in use only while Sarjy listens ([D-86](../DECISIONS.md#d-86-the-microphone-is-open-only-while-sarjy-listens)). In
Safari, the Audio Session API is set to `auto` while the microphone is open and to
`playback` after, so an iPhone's silent switch doesn't mute Sarjy's voice.

[`LevelMeter`](../../frontend/src/lib/level-meter.ts#L32) puts an analyser on the
microphone's stream, sharing the player's audio context. Every 50 ms it keeps the loudest
RMS so far, which `stop()` returns in dBFS for the speech check above, and `current()`
gives the level from 0 to 1 that the orb and the glow follow.

## The player

[`Player`](../../frontend/src/lib/player.ts#L49) plays a reply's clips back to back
([D-77](../DECISIONS.md#d-77-the-page-plays-sentence-clips-back-to-back-sentence-mode-by-default)):

- [`enqueue`](../../frontend/src/lib/player.ts#L60) waits for the previous clip to be
  scheduled, so clips keep their arrival order even if a later one decodes faster.
- [`#schedule`](../../frontend/src/lib/player.ts#L119) decodes the WAV and starts it on
  the audio context's clock at the later of now and the moment the previous clip ends.
  Sentences join with no gap and never overlap, which starting each clip on the previous
  one's `ended` event could not promise.
- A timer set for that start moment calls `onStart`, which is where `playback_start` and
  `onSpeak` come from.
- [`finished()`](../../frontend/src/lib/player.ts#L75) resolves when every queued clip has
  ended, and `level()` reads an analyser on the output.

Browsers only start audio from a gesture. The player creates its audio context on the
first press, or the first clip if that comes sooner, then resumes it on every key press, pointer lift, touch end and return to the
page whenever it isn't running, including iOS's `interrupted` state after a lock or a
call. It doesn't wait for the resume, so a recording never waits on the audio ([D-85](../DECISIONS.md#d-85-sarjys-audio-wakes-on-every-gesture-a-microphone-ios-silenced-is-asked-for-again)).

## The waterfall

[`stagesOf`](../../frontend/src/lib/stages-of.ts#L15) computes the same gaps as
`docs/LATENCY.md`: speech to text, first word, first sentence and voice from the gateway's
marks, and the network as TTFA minus the gateway's own time, never below zero. It runs
once both the marks and the TTFA are in, and returns nothing if a mark is missing. The
"How fast Sarjy answered" card draws the last five turns on one 6-second scale ([D-79](../DECISIONS.md#d-79-the-waterfall-each-turns-stages-from-both-clocks-in-the-latency-card)).

## Voice mode

Every visit opens in [`VoiceMode`](../../frontend/src/components/voice-mode.tsx#L59)
([D-87](../DECISIONS.md#d-87-every-visit-opens-in-voice-mode-the-full-view-sits-behind-its-close-button)). The full view, with the conversation, earlier visits and replays, is behind its
close button.

- **The top bar:** "Remembers N", a popover with the facts and "Forget me", and the last
  turn's TTFA, a popover with the waterfall.
- **The middle:** the orb, drawn large; the line under it, which says what Sarjy is doing
  and is `aria-live`; and the captions.
- **The bottom:** problem cards, the tour links once the answer is over, and the settings,
  microphone and close buttons.

[`Captions`](../../frontend/src/components/voice-mode.tsx#L202) show the traveller's own
words in quotes while Sarjy thinks, then Sarjy's current sentence with the one before it
faded above. The glow at the bottom edge follows the microphone while listening and
Sarjy's voice while speaking, one animation frame at a time
([`useGlow`](../../frontend/src/components/voice-mode.tsx#L231)).

[`TalkOrb`](../../frontend/src/components/talk-orb.tsx#L26) is a button holding a canvas.
[`OrbRenderer`](../../frontend/src/components/orb-renderer.ts) draws a sphere of dots with
plain Canvas 2D, with no new dependency: it turns at rest, ripples with the microphone
while listening, sweeps a band of light while thinking and pulses with the voice while
speaking ([D-80](../DECISIONS.md#d-80-sarjys-identity-a-voice-trail-mark-a-talk-orb-three-palettes)). Its colours come from the stylesheet's tokens. The button is described
by the line under it, so a screen reader hears "Listening…" or what Sarjy is doing, and
declares Space as its shortcut. [`useTalkControls`](../../frontend/src/components/use-talk-controls.ts#L22)
handles both talk modes: hold to talk, the default, or tap to start and tap again to send, chosen in the settings and kept in the browser ([D-83](../DECISIONS.md#d-83-settings-with-a-tap-to-talk-mode-the-orb-and-the-welcome-for-keyboards-and-readers)).

[`SpokenWords`](../../frontend/src/components/spoken-words.tsx#L32) lights each word as it
is said. Kokoro gives no word timings, so
[`timeWords`](../../frontend/src/components/spoken-words.tsx#L61) spreads a clip's words
across its duration by their letters. Each word gets its moment as CSS variables, and a
CSS animation reveals it then, with no timers. The moment is counted from when the clip
started, so switching views mid-answer shows the words where the voice is. Under
reduced motion the orb and the glow hold still and words show whole ([D-87](../DECISIONS.md#d-87-every-visit-opens-in-voice-mode-the-full-view-sits-behind-its-close-button)).

## When something fails

Every problem the page can hear has a kind, in one table,
[`problems.ts`](../../frontend/src/components/problems.ts), and shows where it can be acted
on ([D-81](../DECISIONS.md#d-81-problems-shown-where-they-belong-links-and-a-dropped-connection-on-screen)). A slip of the hand, such as no speech, is a quiet hint under the orb. A question
heard but not answered gets a note on that turn. A denied microphone and a full visit get
a card above the orb. A dropped connection disables the orb until the socket is back:
voice mode says "Waiting for the connection…" under it, and the full view's header says
"Reconnecting…".

## How it is tested

The page has no unit tests; adding Vitest is still an open decision, for when the client
grows logic worth it (O-25). What checks it:

- TypeScript 6, which is strict by default, run by `npm run build` (`tsc -b`), and ESLint and React
  Doctor through the code standards ([chapter 10](10-shipping.md));
- zod at the socket's boundary, so a message that doesn't match is dropped, not misread;
- `?rehearse` in development, which plays scripted turns with no gateway or microphone,
  and `?rehearse=problems`, which plays a sample of failures one after another
  ([`rehearsal-session.ts`](../../frontend/src/components/rehearsal-session.ts));
- the four demo scenarios, spoken on the deployed URL in Chrome and Safari on a MacBook and
  Safari on an iPhone (the README's tested devices).

The gateway's side of the same protocol is tested in
[`test_voice.py`](../../gateway/tests/test_voice.py) ([chapter 2](02-api.md)).
