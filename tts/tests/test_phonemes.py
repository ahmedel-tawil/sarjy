from sarjy_tts.phonemes import EspeakPhonemes


def test_espeak_turns_english_and_numbers_into_ipa() -> None:
    phonemes = EspeakPhonemes().to_phonemes("It costs 250 dirhams.")

    assert "tˈuː" in phonemes
    assert phonemes.endswith(".")
