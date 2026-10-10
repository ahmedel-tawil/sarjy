# 7. The voice

Sarjy speaks with Kokoro-82M, an open text-to-speech model, run by our own service on
Cloud Run rather than a hosted TTS. That gives full control over latency and caching, lets
TTS scale and be measured on its own, and costs compute time instead of a per-character
bill ([D-11](../DECISIONS.md#d-11-text-to-speech-kokoro-82m-as-my-own-service), [D-70](../DECISIONS.md#d-70-tts-on-8-vcpu-still-scaling-to-zero); the numbers are in [`docs/COST.md`](../COST.md)). This chapter covers the
service in `tts/`, then the gateway's side: the client that calls it with an ID token, and
the cache of sentences already spoken.

## The TTS service

### Start-up

[`main()`](../../tts/src/sarjy_tts/__main__.py#L15) reads the settings (`SARJY_*` and
`PORT`, as in the gateway), loads the model, checks that the default voice, `af_heart`,
is among the voices, and synthesises "Hello." once before serving, because an ONNX Runtime
session's first run is slower than the rest. Only then does uvicorn start, so Cloud Run
sends no traffic to a cold model.

[`load_synthesizer`](../../tts/src/sarjy_tts/loading.py#L16) opens the model with ONNX
Runtime on the CPU provider only, so local numbers match Cloud Run, with
`intra_op_num_threads` set from `SARJY_THREADS`: 8 on Cloud Run, the vCPUs paid for ([D-70](../DECISIONS.md#d-70-tts-on-8-vcpu-still-scaling-to-zero)).
It loads every voice file and the vocabulary from the model's own `tokenizer.json`.

### Our own text front end

Kokoro needs a front end that turns text into the model's inputs. Sarjy has its own,
instead of the `kokoro-onnx` library, because that library caps itself below Python 3.14,
which Sarj's standards require ([D-30](../DECISIONS.md#d-30-python-314-for-both-services), [D-38](../DECISIONS.md#d-38-our-own-kokoro-front-end-instead-of-kokoro-onnx)). The front end is small enough to explain line
by line, and owning it gives direct control of ONNX Runtime's options and the warm-up.

[`KokoroSynthesizer.synthesize`](../../tts/src/sarjy_tts/synthesizer.py#L56) goes from text
to audio samples in four steps, and the `/synthesize` route then wraps them as WAV:

1. **Phonemes.** [`EspeakPhonemes`](../../tts/src/sarjy_tts/phonemes.py#L19) runs espeak-ng
   through `phonemizer`, in American English, keeping punctuation and stress marks. Numbers
   come out spelled ("250" becomes "two hundred fifty"). `espeakng-loader` ships the
   espeak-ng library and its data, so nothing is installed on the machine or in the image.
2. **Token ids.** [`Vocabulary.encode`](../../tts/src/sarjy_tts/vocabulary.py#L32) maps each
   phoneme symbol to the model's id from `tokenizer.json`. A symbol the model doesn't know
   is dropped, with a warning.
3. **Chunks.** The model reads at most 512 tokens, two of which are padding, so
   [`split_tokens`](../../tts/src/sarjy_tts/chunks.py#L10) cuts longer input after the last
   clause end that fits (`.!?;:,—…`), or else at the last space, so a chunk ends mid-word
   only when the input has no spaces at all. The gateway sends one sentence at a time, so
   this is normally one chunk.
4. **Run the model.** [`_run`](../../tts/src/sarjy_tts/synthesizer.py#L66) feeds
   `input_ids` padded with 0 at both ends, the voice's `style`, and `speed`. A voice file
   holds one 256-number style per input length, and
   [`Voice.style_for`](../../tts/src/sarjy_tts/voices.py#L28) picks the row for this
   chunk's token count, as the model card documents ([D-48](../DECISIONS.md#d-48-kokoro-model-files-come-from-one-pinned-checksummed-revision)).
Then [`to_wav`](../../tts/src/sarjy_tts/synthesizer.py#L89) clips the float samples to
the range -1 to 1, scales them to 16-bit, and writes a WAV header: mono, 24 kHz. WAV
describes itself, so the gateway and the browser decode it with no other information
([D-50](../DECISIONS.md#d-50-tts-returns-wav-full-precision-for-now-voices-and-languages)).

The trade-off: Kokoro was trained on phonemes from its own library, misaki, and espeak-ng
may pronounce some words differently. espeak-ng is far lighter ([D-48](../DECISIONS.md#d-48-kokoro-model-files-come-from-one-pinned-checksummed-revision)).

### The model files

Nothing from the model is committed. [`tts/model-files.sha256`](../../tts/model-files.sha256)
lists each file with its SHA-256, and
[`download-model.sh`](../../tts/scripts/download-model.sh) fetches them from one pinned
revision of `onnx-community/Kokoro-82M-v1.0-ONNX` on Hugging Face and checks every
checksum, so a changed or corrupted file is a hard failure ([D-48](../DECISIONS.md#d-48-kokoro-model-files-come-from-one-pinned-checksummed-revision)). The
[`Dockerfile`](../../tts/Dockerfile#L13) downloads only what the service uses: the
full-precision `model.onnx`, `tokenizer.json`, and the five voices `af_heart`, `af_bella`,
`af_sarah`, `am_michael` and `am_adam` ([D-49](../DECISIONS.md#d-49-selectable-voices-af_heart-by-default), [D-50](../DECISIONS.md#d-50-tts-returns-wav-full-precision-for-now-voices-and-languages)).

### The API

| Endpoint | Request | Answer |
| --- | --- | --- |
| `GET /voices` | none | `{"voices": [...], "default": "af_heart"}` |
| `POST /synthesize` | `{"text": "...", "voice": "af_heart", "speed": 1.0}`; `voice` and `speed` optional | A WAV file, `audio/wav`; 422 for empty text, text over 1,000 characters, an unknown voice, or a speed outside 0.5 to 2 |
| `GET /health` | none | `{"status": "ok"}` |

The routes are in [`api.py`](../../tts/src/sarjy_tts/api.py#L40). Synthesis is CPU work,
so it runs in a worker thread with `asyncio.to_thread`, which keeps the event loop free to
answer `/health`.

On Cloud Run the service has 8 vCPU and 4 GiB, at most one instance taking up to four
requests at once, and one instance kept warm for the review week ([D-70](../DECISIONS.md#d-70-tts-on-8-vcpu-still-scaling-to-zero), [D-72](../DECISIONS.md#d-72-turn-limits-in-memory-per-user-and-per-ip-counted-per-instance), [D-78](../DECISIONS.md#d-78-cold-starts-tts-woken-when-a-visit-opens-warm-instances-a-setting)). It has
no public access: only the gateway's service account may call it ([D-45](../DECISIONS.md#d-45-tts-is-private-the-gateway-calls-it-with-its-own-identity), [chapter 10](10-shipping.md)).

## The gateway's side: `tts.py`

[`HttpTextToSpeech`](../../gateway/src/sarjy_gateway/tts.py#L65) implements the gateway's
[`TextToSpeech`](../../gateway/src/sarjy_gateway/tts.py#L30) Protocol: `voices()` calls
`GET /voices`, and `synthesize(text, voice)` posts the text, adds the voice when there is
one, and returns the WAV bytes. Any HTTP or network error, including a 4xx or 5xx, becomes a
`TextToSpeechError`. The shared HTTP client allows 30 seconds, since synthesis is seconds of
CPU work and a cold start adds model loading on top.

Because TTS is private, every call carries a Google ID token
([`_request`](../../gateway/src/sarjy_gateway/tts.py#L84)).
[`MetadataIdToken`](../../gateway/src/sarjy_gateway/tts.py#L45) asks Cloud Run's metadata
server for a token for the gateway's own identity, with the TTS URL as the audience, and
reuses it for 50 minutes, well inside its one-hour life. Cloud Run checks the token before
our code runs. There is no shared secret to create, store or rotate ([D-45](../DECISIONS.md#d-45-tts-is-private-the-gateway-calls-it-with-its-own-identity)). Locally,
`SARJY_TTS_AUTH=none` uses [`NoToken`](../../gateway/src/sarjy_gateway/tts.py#L40) and
sends no header.

## The cache: `tts_cache.py`

[`CachedTextToSpeech`](../../gateway/src/sarjy_gateway/tts_cache.py#L33) wraps the client
and keeps the audio of each sentence in the gateway's memory, keyed by its text and voice
([D-97](../DECISIONS.md#d-97-a-tts-cache-in-the-gateways-memory-settles-o-23)). A hit skips both the hop to TTS and the synthesis: a turn that opens with a cached
sentence starts speaking about 1.3 s sooner (experiment 3).

- It is an `OrderedDict` used as a least-recently-used list: a hit moves the clip to the
  end, and once the clips pass `SARJY_TTS_CACHE_BYTES` (32 MB, about 11 minutes of speech)
  the oldest go first. 0 turns the cache off, and then no wrapper is built at all.
- Speed is always the default, and every deploy starts a new gateway, so a clip never
  outlives the model that made it. Neither needs to be in the key.
- At start-up, [`warm`](../../gateway/src/sarjy_gateway/tts_cache.py#L61) makes six common
  phrases ([`WARM_PHRASES`](../../gateway/src/sarjy_gateway/tts_cache.py#L18)) in the
  default voice, in the background. If TTS is down it stops quietly.
- The key holds the voice as the turn sends it, which is `None` until a traveller picks a
  voice. The warm phrases are stored under `None`, so they serve travellers who never
  picked one.
- A replay of an answer this gateway has just spoken normally finds its sentences already
  there, as long as the voice is the same and the reply splits the same way again.
- Every lookup logs a hit or a miss with the running counts.

## When something fails

- **TTS is cold.** A visit wakes it as it opens ([chapter 3](03-visit.md)), and one instance stays warm
  for the review week ([D-78](../DECISIONS.md#d-78-cold-starts-tts-woken-when-a-visit-opens-warm-instances-a-setting)).
- **A synthesis fails mid-turn.** `TextToSpeechError` becomes `tts_failed` ([chapter 4](04-turn.md)).
  Clips already sent have played.
- **TTS can't list its voices.** `GET /voices` on the gateway answers 503, the page hides
  its voice picker, and `set_voice` answers `tts_failed`.
- **The service can't start.** A missing default voice raises at start-up, before serving,
  so Cloud Run never routes traffic to it.

## How it is tested

The TTS tests need no model files. [`test_synthesizer.py`](../../tts/tests/test_synthesizer.py)
uses fixed phonemes and a recording session in place of ONNX Runtime: it checks the padded
ids, the style row and the speed fed to the model, long input run per chunk, and 16-bit
scaling. [`test_api.py`](../../tts/tests/test_api.py) uses a fake synthesizer for the WAV
format and the refused requests. [`test_chunks.py`](../../tts/tests/test_chunks.py),
[`test_voices.py`](../../tts/tests/test_voices.py) and
[`test_vocabulary.py`](../../tts/tests/test_vocabulary.py) cover the pieces;
[`test_phonemes.py`](../../tts/tests/test_phonemes.py) runs the real espeak-ng, which ships
with the package. On the gateway, [`test_tts.py`](../../gateway/tests/test_tts.py) checks
the request, the ID token and its reuse until close to expiry, and every failure;
[`test_tts_cache.py`](../../gateway/tests/test_tts_cache.py) checks that the same words in
the same voice are made once, the least recently used clip goes first, warmed phrases are
hits, and warming stops quietly when TTS is down.
[`tts/scripts/benchmark.py`](../../tts/scripts/benchmark.py) times the model per thread
count on the machine it runs on and writes voice samples. The 8-vCPU choice came from
timing the deployed service at 2, 4 and 8 vCPU ([D-70](../DECISIONS.md#d-70-tts-on-8-vcpu-still-scaling-to-zero)).
