"""Output conversion of the optional baseline backends (no model needed)."""

from types import SimpleNamespace as NS

import pytest

from ilat.asr.crisper_backend import normalize_word, words_to_segments
from ilat.asr.parakeet_backend import convert_result, tokens_to_words
from ilat.eval.normalize import tokenize
from ilat.eval.systems import SYSTEMS


def tok(text, start, end, confidence=0.9):
    return NS(text=text, start=start, end=end, confidence=confidence)


def test_parakeet_tokens_to_words():
    tokens = [tok(" Em", 0.0, 0.1), tok(",", 0.4, 0.5), tok(" all", 0.5, 0.8, 0.6),
              tok("ora", 0.8, 0.9), tok(",", 0.9, 1.0), tok(" il", 1.1, 1.3)]  # fmt: skip
    words = tokens_to_words(tokens)
    assert [w.text for w in words] == ["Em,", "allora,", "il"]
    assert (words[1].start, words[1].end, words[1].probability) == (0.5, 1.0, 0.6)


def test_parakeet_convert_result_keeps_segments_sorted():
    result = NS(sentences=[
        NS(tokens=[tok(" Ciao", 1.0, 1.4), tok(".", 1.4, 1.5)]),
        NS(tokens=[tok(" poi", 0.8, 1.0)]),  # chunk merge glitch: starts earlier
        NS(tokens=[tok(" ", 2.0, 2.1)]),  # empty sentence is dropped
    ])  # fmt: skip
    asr = convert_result(result)
    assert [s.text for s in asr.segments] == ["Ciao.", "poi"]
    assert asr.segments[1].start == 1.0
    assert asr.language is None


@pytest.mark.parametrize(
    ("raw", "expected"),
    [("[UM]", "um"), ("[uh],", "uh,"), ("[laughter]", "[laughter]"), ("meeting.", "meeting.")],
)
def test_crisper_normalize_word(raw, expected):
    assert normalize_word(raw) == expected


def test_crisper_fillers_count_as_fillers_in_metrics():
    [seg] = words_to_segments([NS(word="[UM]", start=0.0, end=0.3), NS(word="so", start=0.5,
                                                                        end=0.8)])  # fmt: skip
    toks = tokenize(seg.words, "en", "verbatim", "hyp")
    assert [(t.text, t.is_filler) for t in toks] == [("um", True), ("so", False)]
    assert [t.text for t in tokenize(seg.words, "en", "literal", "hyp")] == ["so"]


def test_crisper_words_to_segments_splits_on_gaps_and_length():
    raw = [
        NS(word="a", start=0.0, end=0.5),
        NS(word="b", start=0.6, end=1.0),
        NS(word="c", start=2.5, end=3.0),  # gap of 1.5 s
        NS(word="d", start=3.1, end=33.5),
    ]  # would exceed 30 s
    segs = words_to_segments(raw)  # fmt: skip
    assert [s.text for s in segs] == ["a b", "c", "d"]


def test_crisper_words_to_segments_monotonic_times():
    raw = [NS(word="a", start=1.0, end=2.0), NS(word="b", start=1.5, end=1.8)]
    [seg] = words_to_segments(raw)
    assert [(w.start, w.end) for w in seg.words] == [(1.0, 2.0), (2.0, 2.0)]


def test_baseline_systems_registered():
    assert SYSTEMS["parakeet-v3"].kind == "parakeet"
    crisper = SYSTEMS["crisper-turbo-lang"]
    assert crisper.kind == "crisper" and crisper.language("it") == "it"
