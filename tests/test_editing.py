from datetime import UTC, datetime

import pytest

from ilat import editing
from ilat.schema import Metadata, Segment, Transcript, Word


def make():
    words = [
        Word(text="ci", start=0.0, end=0.2),
        Word(text="Kier", start=0.3, end=0.6, doubtful=True),
        Word(text="4", start=0.6, end=0.8, doubtful=True),
        Word(text="ok", start=1.0, end=1.2),
        Word(text="tutti.", start=1.3, end=1.6, doubtful=True),
    ]
    meta = Metadata(
        audio_file="x.wav", duration=2, created_at=datetime(2026, 10, 16, tzinfo=UTC),
        ilat_version="0",
    )  # fmt: skip
    return Transcript(
        metadata=meta,
        segments=[Segment(start=0, end=2, text=" ".join(w.text for w in words), words=words)],
    )


def test_doubt_runs():
    assert editing.doubt_runs(make()) == [(0, 1, 3), (0, 4, 5)]


def test_correct_replaces_span_and_logs_original():
    t = make()
    edit = editing.correct(t, 0, 1, 3, "QX 4")
    seg = t.segments[0]
    assert seg.text == "ci QX 4 ok tutti."
    new = seg.words[1:3]
    assert [w.text for w in new] == ["QX", "4"] and all(w.checked and not w.doubtful for w in new)
    assert new[0].start == 0.3 and new[-1].end == pytest.approx(0.8)
    assert edit.kind == "correct" and [w.text for w in edit.before] == ["Kier", "4"]
    assert editing.doubt_runs(t) == [(0, 4, 5)]


def test_correct_can_change_the_number_of_words_and_delete():
    t = make()
    editing.correct(t, 0, 1, 3, "baking soda KR4")
    assert t.segments[0].text == "ci baking soda KR4 ok tutti."
    editing.correct(t, 0, 5, 6, "")
    assert t.segments[0].text == "ci baking soda KR4 ok"


def test_unchanged_text_is_a_confirmation():
    t = make()
    edit = editing.correct(t, 0, 4, 5, "tutti.")
    assert edit.kind == "confirm"
    assert t.segments[0].words[4].checked and not t.segments[0].words[4].doubtful


def test_undo_restores_the_original_words():
    t = make()
    before = t.segments[0].model_dump()
    editing.correct(t, 0, 1, 3, "baking soda KR4")
    editing.confirm(t, 0, 0, 1)
    editing.undo(t)
    editing.undo(t)
    assert t.segments[0].model_dump() == before and t.edits == []
    assert editing.undo(t) is None


@pytest.mark.parametrize("args", [(1, 0, 1), (0, 3, 2), (0, 0, 9), (0, -1, 1)])
def test_bad_spans(args):
    with pytest.raises(editing.EditError):
        editing.correct(make(), *args, "x")


def test_save_keeps_the_model_output_once(tmp_path):
    path = tmp_path / "call.json"
    t = make()
    t.save(path)
    editing.correct(t, 0, 1, 3, "QX 4")
    editing.save(t, path)
    editing.correct(t, 0, 0, 1, "Ci")
    editing.save(t, path)
    original = Transcript.load(tmp_path / "call.asr.json")
    assert original.edits == [] and original.segments[0].text == "ci Kier 4 ok tutti."
    assert len(Transcript.load(path).edits) == 2
