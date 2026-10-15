import itertools
from datetime import UTC, datetime

from ilat import adjudicate
from ilat.schema import Metadata, Segment, Transcript, Word
from ilat.schema.lint import lint


def transcript(*segments, kind):
    return Transcript(
        metadata=Metadata(kind=kind, audio_file="x.m4a", duration=60,
                          created_at=datetime(2026, 10, 15, tzinfo=UTC), ilat_version="0"),
        segments=list(segments),
    )  # fmt: skip


def ref_seg(start, end, text, lang="it"):
    words = [Word(text=t, lang=lang) for t in text.split()]
    return Segment(start=start, end=end, lang=lang, text=text, words=words)


def hyp_seg(start, end, text, lang="it"):
    toks = text.split()
    step = (end - start) / len(toks)
    words = [Word(text=t, start=start + k * step, end=start + (k + 1) * step)
             for k, t in enumerate(toks)]  # fmt: skip
    return Segment(start=start, end=end, lang=lang, text=text, words=words)


BASE = transcript(
    ref_seg(0, 10, "allora il progetto parte lunedì e poi vediamo tutto il resto domani."),
    kind="reference",
)
OTHER = transcript(
    hyp_seg(0, 10, "allora il il progetto parte martedì e poi vediamo tutto il resto ehm domani."),
    kind="asr",
)


def test_find_regions():
    regions = adjudicate.find_regions(BASE, OTHER)
    assert [(r.item_id, r.base_text, r.other_text) for r in regions] == [
        ("D001", "", "il"),  # inserted repetition
        ("D002", "lunedì", "martedì"),
        ("D003", "", "ehm"),
    ]
    first = regions[0]
    assert (first.base_lo, first.base_hi) == (2, 2)
    assert first.before.endswith("il") and first.after.startswith("progetto")
    assert first.start < first.end


def test_close_disagreements_form_one_region():
    base = transcript(ref_seg(0, 5, "a b c d e f"), kind="reference")
    other = transcript(hyp_seg(0, 5, "a x c y e f"), kind="asr")
    [r] = adjudicate.find_regions(base, other)
    assert (r.base_text, r.other_text) == ("b c d", "x c y")


def test_multi_token_word_is_never_split():
    base = transcript(ref_seg(0, 5, "parliamo dell'80% dei casi"), kind="reference")
    other = transcript(hyp_seg(0, 5, "parliamo del settanta per cento di casi"), kind="asr")
    regions = adjudicate.find_regions(base, other)
    spans = [(r.base_lo, r.base_hi) for r in regions]
    assert all(a[1] <= b[0] for a, b in itertools.pairwise(spans))


def test_apply_choices_on_reference():
    regions = adjudicate.find_regions(BASE, OTHER)
    answers = {"D001": {"choice": "B"}, "D002": {"choice": "A"},
               "D003": {"choice": "text", "text": "eh"}}  # fmt: skip
    out = adjudicate.apply(BASE, regions, answers)
    seg = out.segments[0]
    assert seg.text == "allora il il progetto parte lunedì e poi vediamo tutto il resto eh domani."
    assert [w.tags for w in seg.words if w.text == "eh"] == [["filler"]]
    assert all(w.lang == "it" for w in seg.words)
    assert BASE.segments[0].text.startswith("allora il progetto")  # input untouched
    errors = [i for i in lint(out) if i.severity == "error"]
    assert errors == []


def test_apply_unanswered_keeps_base_and_empty_text_deletes():
    regions = adjudicate.find_regions(BASE, OTHER)
    assert adjudicate.apply(BASE, regions, {}).segments == BASE.segments
    base = transcript(ref_seg(0, 5, "sì sì ok"), kind="reference")
    other = transcript(hyp_seg(0, 5, "sì ok"), kind="asr")
    [r] = adjudicate.find_regions(base, other)
    out = adjudicate.apply(base, [r], {r.item_id: {"choice": "text", "text": ""}})
    assert out.segments[0].text == "sì ok"


def test_apply_on_draft_keeps_other_times():
    draft = transcript(hyp_seg(0, 4, "we need to go"), kind="asr")
    other = transcript(hyp_seg(0, 4, "we we need to go"), kind="asr")
    [r] = adjudicate.find_regions(draft, other)
    out = adjudicate.apply(draft, [r], {r.item_id: {"choice": "B"}})
    assert out.segments[0].text == "we we need to go"
    inserted = out.segments[0].words[1]
    assert inserted.start is not None and inserted.lang is None and inserted.tags == []


def test_page_and_regions_roundtrip(tmp_path):
    regions = adjudicate.find_regions(BASE, OTHER)
    page = adjudicate.write_page(regions, "it-002", ("riferimento", "crisper"), tmp_path)
    text = page.read_text()
    assert text.count("<section ") == 3 and "<mark>martedì</mark>" in text
    loaded = adjudicate.load_regions(tmp_path)
    assert [(r.item_id, r.other_texts, r.other_times) for r in loaded] == [
        (r.item_id, r.other_texts, r.other_times) for r in regions
    ]


def test_fillers_from_other_side_follow_the_language_inventory():
    base = transcript(ref_seg(0, 5, "allora andiamo"), kind="reference")
    other = transcript(hyp_seg(0, 5, "allora um, andiamo"), kind="asr")
    [r] = adjudicate.find_regions(base, other)
    out = adjudicate.apply(base, [r], {r.item_id: {"choice": "B"}})
    assert out.segments[0].text == "allora ehm, andiamo"
    assert [i for i in lint(out) if i.severity == "error"] == []
