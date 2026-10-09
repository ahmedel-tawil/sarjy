import pytest
from sarjy_gateway.latency import ClientMarks, ServerMarks, TurnGaps, TurnTiming, gaps, percentile, summarise, table


def timing(*, tts_first_byte: float = 6000.0, ttfa: float = 6800.0) -> TurnTiming:
    return TurnTiming(
        run="baseline",
        turn_id="0199c3a4b5d67e8f9a0b1c2d3e4f5a6b",
        server=ServerMarks(
            audio_received=0.0,
            stt_done=800.0,
            llm_first_token=3000.0,
            first_sentence_ready=3600.0,
            tts_first_byte=tts_first_byte,
        ),
        client=ClientMarks(speech_end=10_000.0, playback_start=10_000.0 + ttfa),
    )


def test_stages_use_the_gateway_clock_and_ttfa_the_browsers() -> None:
    assert gaps(timing()) == TurnGaps(
        stt=800.0,
        llm_first_word=2200.0,
        first_sentence=600.0,
        tts=2400.0,
        server_total=6000.0,
        network_and_browser=800.0,
        ttfa=6800.0,
    )


@pytest.mark.parametrize(
    ("values", "p", "expected"),
    [
        ([float(n) for n in range(1, 21)], 50, 10.0),
        ([float(n) for n in range(1, 21)], 95, 19.0),
        ([3.0, 1.0, 2.0], 50, 2.0),
        ([3.0, 1.0, 2.0], 95, 3.0),
        ([7.5], 95, 7.5),
    ],
    ids=["p50 of 20", "p95 of 20", "unsorted p50", "unsorted p95", "one value"],
)
def test_percentiles_are_nearest_rank_so_each_is_a_measured_value(
    values: list[float], p: float, expected: float
) -> None:
    assert percentile(values, p) == expected


def test_no_values_have_no_percentile() -> None:
    with pytest.raises(ValueError, match="no values"):
        percentile([], 50)


def test_a_run_is_summarised_per_gap() -> None:
    run = [timing(ttfa=6800.0), timing(ttfa=5200.0), timing(ttfa=9100.0)]

    summary = {gap.gap: gap for gap in summarise(run)}

    assert list(summary) == ["stt", "llm_first_word", "first_sentence", "tts", "server_total", "network_and_browser", "ttfa"]
    assert (summary["ttfa"].turns, summary["ttfa"].p50_ms, summary["ttfa"].p95_ms) == (3, 6800.0, 9100.0)
    assert summary["network_and_browser"].p50_ms == pytest.approx(800.0)


def test_a_run_file_line_is_one_turn() -> None:
    line = timing().model_dump_json()

    assert TurnTiming.model_validate_json(line) == timing()


def test_the_table_has_a_header_and_one_line_per_gap() -> None:
    lines = table([timing(), timing(ttfa=5200.0)])

    assert lines[0].split() == ["gap", "p50", "ms", "p95", "ms"]
    assert lines[-1].split() == ["ttfa", "5200", "6800"]
    assert len(lines) == 8
