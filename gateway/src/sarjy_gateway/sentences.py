import re


# A sentence shorter than this joins the next one: "Sure." on its own would be a TTS call
# for half a second of audio, and Kokoro reads short fragments with odd prosody.
MIN_SENTENCE_CHARS = 12

# Words that end in a full stop without ending the sentence.
ABBREVIATIONS = frozenset({"approx", "dr", "e.g", "etc", "i.e", "jr", "mr", "mrs", "ms", "sr", "st", "vs"})

ENDINGS = ".!?…"
# What may follow the punctuation inside the same sentence, such as a closing quote.
CLOSERS = "\"')]”’"


# Splits text that arrives in pieces into sentences TTS can speak one by one (M3.5). A
# full stop only ends a sentence once the next character shows it isn't a decimal point
# or an abbreviation, so a sentence is never cut while its last word is still arriving.
class SentenceChunker:
    def __init__(self) -> None:
        self._buffer = ""
        self._short = ""

    # Adds a piece of streamed text and returns the sentences it completed, in order.
    def add(self, text: str) -> list[str]:
        self._buffer += text
        sentences: list[str] = []
        while (end := sentence_end(self._buffer)) is not None:
            sentence, self._buffer = self._buffer[:end].strip(), self._buffer[end:]
            sentences += self._keep(sentence)
        return sentences

    # The text left at the end of a model's answer, which may lack a final full stop.
    def flush(self) -> list[str]:
        rest = f"{self._short} {self._buffer}".strip()
        self._buffer, self._short = "", ""
        return [rest] if rest else []

    def _keep(self, sentence: str) -> list[str]:
        sentence = f"{self._short} {sentence}".strip()
        if len(sentence) < MIN_SENTENCE_CHARS:
            self._short = sentence
            return []
        self._short = ""
        return [sentence]


# Where the first complete sentence of `text` ends, or None while it can't be known yet.
def sentence_end(text: str) -> int | None:
    for index, character in enumerate(text):
        if character == "\n" and text[:index].strip():
            return index + 1
        if character not in ENDINGS:
            continue
        end = index + 1
        while end < len(text) and text[end] in ENDINGS + CLOSERS:
            end += 1
        if end == len(text):
            # The next piece decides: "3." may become "3.5", "e.g." may continue.
            return None
        if text[end].isspace() and not is_abbreviation(text[: index + 1]):
            return end
    return None


# True when the full stop that ends `text` belongs to a word such as "Dr." or "e.g.", or to
# an initial such as the "U." of "U.S.".
def is_abbreviation(text: str) -> bool:
    if not text.endswith("."):
        return False
    words = text[:-1].split()
    if not words:
        return False
    word = words[-1].lower().lstrip("(\"'")
    return word in ABBREVIATIONS or bool(re.fullmatch(r"(?:[a-z]\.)*[a-z]", word))


# The per-sentence step between the model and TTS, where a check of spoken facts would
# also go (M6.1). Today it removes markdown the model sometimes writes despite the prompt,
# which TTS would otherwise read out.
def speakable(sentence: str) -> str:
    text = re.sub(r"[*_#`]+", "", sentence)
    text = re.sub(r"^\s*(?:[-•]|\d+\.)\s+", "", text)
    return " ".join(text.split())
