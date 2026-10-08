class TurnAudio:
    def __init__(self, max_bytes: int) -> None:
        self._max_bytes = max_bytes
        self._audio = bytearray()
        self._too_long = False

    def add(self, chunk: bytes) -> None:
        if self._too_long:
            return
        if len(self._audio) + len(chunk) > self._max_bytes:
            # Drop what we have: a truncated recording would not decode as a valid file.
            self._too_long = True
            self._audio.clear()
            return
        self._audio.extend(chunk)

    @property
    def too_long(self) -> bool:
        return self._too_long

    def take(self) -> bytes:
        audio = bytes(self._audio)
        self._audio.clear()
        self._too_long = False
        return audio
