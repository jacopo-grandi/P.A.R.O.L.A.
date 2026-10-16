"""The diarization error rate on hand-built cases, before trusting any number from it."""

import pytest

from parola.eval.diarization import der, read_rttm


def test_perfect_with_other_names_is_zero():
    ref = [(0, 10, "A"), (10, 20, "B")]
    hyp = [(0, 10, "s1"), (10, 20, "s0")]
    d = der(ref, hyp)
    assert d.rate == 0 and d.total == pytest.approx(20)


def test_missed_and_false_alarm():
    ref = [(0, 10, "A")]
    assert der(ref, [(0, 5, "x")]).missed == pytest.approx(5)
    d = der(ref, [(0, 10, "x"), (10, 14, "x")])
    assert d.false_alarm == pytest.approx(4) and d.rate == pytest.approx(0.4)


def test_confusion_when_one_speaker_is_split_wrongly():
    # A talks 0-10 and B 10-20, the system thinks one voice talked throughout.
    d = der([(0, 10, "A"), (10, 20, "B")], [(0, 20, "x")])
    assert d.confusion == pytest.approx(10) and d.rate == pytest.approx(0.5)


def test_overlapping_speech_counts_both_speakers():
    ref = [(0, 10, "A"), (5, 10, "B")]  # 5 s of overlap: 15 s of speaker time
    d = der(ref, [(0, 10, "x")])
    assert d.total == pytest.approx(15) and d.missed == pytest.approx(5) and d.confusion == 0


def test_mapping_is_one_to_one_and_the_best_one():
    # Two hypothesis speakers both lie mostly on A: only one can be A.
    ref = [(0, 10, "A"), (10, 12, "B")]
    hyp = [(0, 6, "x"), (6, 12, "y")]
    d = der(ref, hyp)
    # x->A (6 s), y->B (2 s): 4 s of A wrongly given to y.
    assert d.confusion == pytest.approx(4) and d.rate == pytest.approx(4 / 12)


def test_read_rttm(tmp_path):
    f = tmp_path / "m.rttm"
    f.write_text(
        "SPEAKER m 1 1.50 2.00 <NA> <NA> FEE013 <NA> <NA>\nSPEAKER m 1 4 1 <NA> <NA> B <NA> <NA>\n"
    )
    assert read_rttm(f) == [(1.5, 3.5, "FEE013"), (4.0, 5.0, "B")]
