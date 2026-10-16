import json
import wave
from datetime import UTC, datetime
from pathlib import Path

from parola.audio import extract_audio
from parola.eval import audit
from parola.schema import Metadata, Segment, Transcript, Word
from tests.conftest import requires_ffmpeg


def transcript(*segments, kind="asr"):
    return Transcript(
        metadata=Metadata(kind=kind, audio_file="x.m4a", duration=60,
                          created_at=datetime(2026, 10, 15, tzinfo=UTC), parola_version="0"),
        segments=list(segments),
    )  # fmt: skip


def test_find_insertions_categories_and_context():
    ref = transcript(
        Segment(start=0, end=10, lang="en", text="so we need the meeting",
                words=[Word(text=t, lang="en") for t in ["so", "we", "need", "the", "meeting"]]),
        kind="reference",
    )  # fmt: skip
    hyp_words = ["um", "so", "we", "we", "need", "th-", "the", "big", "meeting"]
    hyp = transcript(Segment(start=0, end=10, lang="en", text=" ".join(hyp_words), words=[
        Word(text=t, start=k, end=k + 0.5) for k, t in enumerate(hyp_words)]))  # fmt: skip
    found = audit.find_insertions("en-002", ref, hyp)
    assert [(i.word, i.category) for i in found] == [
        ("um", "filler"), ("we", "repetition"), ("th-", "truncated"), ("big", "other"),
    ]  # fmt: skip
    big = found[-1]
    assert (big.start, big.end) == (7, 7.5)
    assert "⟦big⟧" in big.hyp_context and "meeting" in big.ref_context


def test_sample_respects_quotas_and_is_reproducible():
    pool = [
        audit.Insertion("f", cat, "w", float(k), k + 0.5, "", "")
        for k, cat in enumerate(["repetition"] * 20 + ["filler"] * 3 + ["other"] * 9)
    ]
    a = audit.sample(pool, {"repetition": 5, "filler": 8, "other": 2}, seed=1)  # fmt: skip
    b = audit.sample(pool, {"repetition": 5, "filler": 8, "other": 2}, seed=1)
    cats = [i.category for i in a]
    assert cats.count("repetition") == 5 and cats.count("filler") == 3 and cats.count("other") == 2
    assert [(i.item_id, i.start) for i in a] == [(i.item_id, i.start) for i in b]
    assert [i.item_id for i in a] == [f"A{k:02d}" for k in range(1, 11)]
    assert [i.start for i in a] == sorted(i.start for i in a)


def test_write_page_and_summarize(tmp_path):
    items = [audit.Insertion("en-002", "repetition", "we", 1.0, 1.2, "we ⟦we⟧ need", "we need",
                             "A01")]  # fmt: skip
    page = audit.write_page(items, "crisper-turbo-lang", tmp_path).read_text()
    assert "<mark>we</mark>" in page and 'src="clips/A01.m4a"' in page  # clip not cut yet
    (tmp_path / "clips").mkdir()
    (tmp_path / "clips" / "A01.m4a").write_bytes(b"\x00\x01")
    page = audit.write_page(items, "crisper-turbo-lang", tmp_path).read_text()
    assert 'src="data:audio/mp4;base64,AAE="' in page
    assert "http" not in page.split("<script>")[1]  # no network
    assert json.loads((tmp_path / "items.json").read_text())[0]["item_id"] == "A01"

    answers = {"system": "x", "items": [
        {"category": "repetition", "answer": "vero"}, {"category": "repetition", "answer": "vero"},
        {"category": "repetition", "answer": "falso"}, {"category": "filler", "answer": "non so"},
        {"category": "other", "answer": None},
    ]}  # fmt: skip
    text = audit.summarize(answers)
    assert "| repetition | 2 | 1 | 0 | 0 | 67% |" in text
    assert "| filler | 0 | 0 | 1 | 0 | — |" in text
    assert "| totale | 2 | 1 | 1 | 1 | 67% |" in text


@requires_ffmpeg
def test_cut_clip(tone_m4a: Path, tmp_path: Path):
    out = tmp_path / "A01.m4a"
    audit.cut_clip(tone_m4a, 0.5, 0.7, out)
    wav = extract_audio(out, tmp_path / "clip.wav")
    with wave.open(str(wav)) as f:
        # 2 s padding before (clamped at 0) and after: from 0.0 to 2.0 (end of the tone).
        assert 1.5 < f.getnframes() / f.getframerate() <= 2.1
