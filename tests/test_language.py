"""Choosing Italian or English from Whisper's guesses on windows spread over a recording."""

from parola.asr.language import choose, window_starts


def test_windows_start_on_speech_spread_over_the_recording():
    regions = [(float(i), i + 0.5) for i in range(0, 100, 10)]  # ten regions, 0 s to 90 s
    assert window_starts(regions) == [0.0, 20.0, 40.0, 60.0, 90.0]


def test_few_regions_give_fewer_windows_and_none_gives_none():
    assert window_starts([(3.0, 4.0)]) == [3.0]
    assert window_starts([(1.0, 2.0), (8.0, 9.0)]) == [1.0, 8.0]
    assert window_starts([]) == []


def test_the_average_decides_not_the_first_window():
    # en-001: the first window leans Italian, the rest of the hour is English.
    guesses = [{"it": 0.50, "en": 0.43}] + [{"en": 0.97, "it": 0.02}] * 4
    assert choose(guesses) == "en"


def test_only_italian_and_english_are_candidates():
    # Spanish wins the window, but the transcript only knows it/en: the larger of those two.
    assert choose([{"es": 0.6, "it": 0.3, "en": 0.1}]) == "it"
    assert choose([{"es": 0.6, "en": 0.3, "it": 0.1}]) == "en"


def test_a_tie_is_italian():
    assert choose([{"it": 0.5, "en": 0.5}]) == "it"
