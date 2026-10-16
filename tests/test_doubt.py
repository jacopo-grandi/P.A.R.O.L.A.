from datetime import UTC, datetime

import pytest

from ilat import doubt
from ilat.schema import Metadata, Segment, Transcript, Word


def t(*segments, kind="asr"):
    return Transcript(
        metadata=Metadata(kind=kind, audio_file="x.wav", duration=60,
                          created_at=datetime(2026, 10, 16, tzinfo=UTC), ilat_version="0"),
        segments=[Segment(start=k * 10, end=k * 10 + 9, lang="it", text=s,
                          words=[Word(text=w, lang="it" if kind == "reference" else None)
                                 for w in s.split()]) for k, s in enumerate(segments)],
    )  # fmt: skip


PRIMARY = t("ci vediamo lunedì per il progetto", "va bene grazie")
#            0  1       2      3   4  5           6  7    8


def test_disputed_words():
    other = t("ci vediamo martedì per progetto", "va bene allora grazie")
    # lunedì substituted (2), "il" missing in other (4), extra "allora" between 7 and 8.
    assert doubt.doubtful_words(PRIMARY, other) == {2, 4, 7, 8}


def test_fillers_and_repetitions_do_not_raise_doubts():
    other = t("ehm ci ci vediamo lunedì per il progetto", "va bene grazie")
    assert doubt.doubtful_words(PRIMARY, other) == set()


def test_window_widens_flags_within_bounds():
    other = t("ci vediamo lunedì per il progetto", "va bene grazie mille")
    assert doubt.doubtful_words(PRIMARY, other) == {8}
    assert doubt.doubtful_words(PRIMARY, other, window=1) == {7, 8}


def test_error_words_and_evaluate():
    ref = t("ci vediamo martedì per il progetto", "va bene grazie", kind="reference")
    assert doubt.error_words(PRIMARY, ref) == {2}
    flagged = doubt.doubtful_words(
        PRIMARY, t("ci vediamo martedì per il progetto", "va male grazie")
    )
    score = doubt.evaluate(PRIMARY, flagged, ref)
    assert (score.words, score.errors, score.flagged, score.caught) == (9, 1, 2, 1)
    assert score.recall == 1.0 and score.precision == 0.5
    assert score.burden == pytest.approx(2 / 9) and score.base_rate == pytest.approx(1 / 9)
    total = score + score
    assert total.recall == 1.0 and total.words == 18
