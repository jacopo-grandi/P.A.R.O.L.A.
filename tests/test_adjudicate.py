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
    assert text.count("<audio controls ") == 3
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


import pytest  # noqa: E402


@pytest.mark.parametrize(
    ("base_text", "other", "before", "after", "kind"),
    [
        ("", ["il"], "allora il", "progetto", "repetition"),
        ("", ["pr-"], "nel", "insomma", "truncated"),
        ("", ["um,"], "allora", "andiamo", "filler"),
        ("", ["tecnici"], "qua", "ok", "insertion"),
        ("parte", ["parte", "parte"], "il", "lunedì", "superset"),
        ("dovrei dovrei", ["dovrei"], "però", "vedere", "subset"),
        ("lunedì", ["martedì"], "parte", "e", "substitution"),
        ("tutto", [], "vediamo", "il", "deletion"),
        ("ehm,", [], "allora", "andiamo", "deleted_filler"),
        ("il", [], "il", "progetto", "deleted_repetition"),
        ("pr-", [], "nel", "insomma", "deleted_truncated"),
    ],
)
def test_classify(base_text, other, before, after, kind):
    assert adjudicate.classify(base_text, other, before, after, "it") == kind


def _region(item_id, kind):
    return adjudicate.Region(item_id, 0, 0, 0, "", ["x"], [(0.0, 1.0)], 0.0, 1.0, "", "",
                             kind=kind)  # fmt: skip


def test_policy_auto_sampled_and_listened():
    regions = ([_region(f"R{k}", "repetition") for k in range(4)]
               + [_region(f"I{k}", "insertion") for k in range(12)]
               + [_region(f"S{k}", "substitution") for k in range(3)])  # fmt: skip
    adjudicate.apply_policy(regions, seed=0)
    by = {r.item_id: r for r in regions}
    assert all(by[f"R{k}"].auto == "B" and not by[f"R{k}"].check for k in range(4))
    assert all(by[f"I{k}"].auto == "B" for k in range(12))
    assert sum(by[f"I{k}"].check for k in range(12)) == 2  # one in six
    assert all(by[f"S{k}"].auto is None for k in range(3))
    adjudicate.apply_policy(regions, listen={"insertion"})
    assert all(by[f"I{k}"].auto is None and not by[f"I{k}"].check for k in range(12))


def test_explicit_answers_override_the_rule_and_agreement():
    regions = [_region("A1", "repetition"), _region("A2", "insertion"),
               _region("A3", "substitution")]  # fmt: skip
    regions[1].auto, regions[1].check = "B", True
    regions[0].auto = "B"
    merged = adjudicate.merged_answers(regions, {"A1": {"choice": "A"}, "A3": {}})
    assert merged == {"A1": {"choice": "A"}, "A2": {"choice": "B"}}
    assert adjudicate.rule_agreement(regions, {"A2": {"choice": "A"}}) == {"insertion": (0, 1)}


def test_rebuilt_page_keeps_storage_key_and_old_answers(tmp_path):
    regions = adjudicate.find_regions(BASE, OTHER)
    adjudicate.apply_policy(regions)
    text = adjudicate.write_page(regions, "it-002", ("a", "b"), tmp_path).read_text()
    # The key uses all regions (3), not only the shown ones.
    assert '"ilat-adjudicate-" + "it-002" + "-" + 3' in text
    assert "Object.entries(state)" in text  # export includes answers to hidden items
    shown = text.count("<section ")
    assert shown == sum(1 for r in regions if r.auto is None or r.check)
    assert len(adjudicate.load_regions(tmp_path)) == 3


def test_policy_mirrored_when_base_is_the_verbatim_draft():
    regions = [_region("R1", "deleted_repetition"), _region("F1", "deleted_filler"),
               _region("D1", "deletion"), _region("S1", "superset")]  # fmt: skip
    adjudicate.apply_policy(regions, verbatim_side="A")
    by = {r.item_id: r for r in regions}
    assert by["R1"].auto == "A" and not by["R1"].check
    assert by["F1"].auto == "A" and by["F1"].check  # one in six, rounded up
    assert by["D1"].auto is None and by["S1"].auto is None
