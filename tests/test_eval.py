"""Hand-built cases for the evaluation metrics: every number here is computed by hand."""

from datetime import UTC, datetime

import pytest

from parola.eval.metrics import (
    Counts,
    SegmentScore,
    align,
    assign_words,
    bootstrap_ci,
    disfluency_counts,
    score_transcript,
    wer_of,
)
from parola.eval.normalize import number_to_words, split_word, tokenize
from parola.schema import Metadata, Segment, Transcript, Word


def W(text, *tags, lang="it", start=None, end=None):
    return Word(text=text, tags=list(tags), lang=lang, start=start, end=end)


def H(text, start=None, end=None):
    """Hypothesis word: no tags, no lang."""
    return Word(text=text, start=start, end=end)


def texts(tokens):
    return [t.text for t in tokens]


def transcript(*segments, kind="asr"):
    return Transcript(
        metadata=Metadata(
            kind=kind,
            audio_file="x.m4a",
            duration=100,
            created_at=datetime(2026, 10, 15, tzinfo=UTC),
            parola_version="0",
        ),
        segments=list(segments),
    )


def seg(start, end, *words, lang="it", **kw):
    return Segment(
        start=start, end=end, lang=lang, text=" ".join(w.text for w in words),
        words=list(words), **kw,
    )  # fmt: skip


# ----------------------------------------------------------------------- normalisation


@pytest.mark.parametrize(
    ("text", "lang", "expected"),
    [
        ("Ciao,", "it", ["ciao"]),
        ("l'info", "it", ["l'", "info"]),
        ("dell'80%", "it", ["dell'", "ottanta", "per", "cento"]),
        ("d\u2019accordo?", "it", ["d'", "accordo"]),
        ("'sta", "it", ["'sta"]),
        ("propo-", "it", ["propo-"]),
        ("Bye-bye.", "en", ["bye-bye"]),
        ("«ok»", "it", ["ok"]),
        ("...", "it", []),
        ("3,000", "en", ["three", "thousand"]),
        ("3.000", "it", ["tremila"]),
        ("9.3", "it", ["nove", "virgola", "tre"]),
        ("Okay,", "en", ["ok"]),
        ("O.K.", "en", ["ok"]),
        ("perchè", "it", ["perché"]),
    ],
)
def test_split_word(text, lang, expected):
    assert split_word(text, lang) == expected


def test_number_to_words_leaves_non_numbers():
    assert number_to_words("GPT-4", "en") == ["GPT-4"]


REF = [
    W("Ehm,", "filler"),
    W("il,", "repetition"),
    W("il"),
    W("propo-", "truncated"),
    W("progetto"),
    W("lunedì,", "false_start"),
    W("no,", "edit_term"),
    W("martedì"),
    W("[risata]", "nonverbal", lang=None),
    W("sì,", "reduplication"),
    W("sì"),
    W("[inaudibile]", lang=None),
]


def test_tokenize_ref_literal():
    assert texts(tokenize(REF, "it", "literal", "ref")) == [
        "il", "il", "propo-", "progetto", "lunedì", "no", "martedì", "sì", "sì",
    ]  # fmt: skip


def test_tokenize_ref_fidelity():
    # Tagged disfluencies dropped, then immediate repeats collapsed ("sì sì" -> "sì").
    assert texts(tokenize(REF, "it", "fidelity", "ref")) == ["il", "progetto", "martedì", "sì"]


def test_tokenize_ref_verbatim():
    toks = tokenize(REF, "it", "verbatim", "ref")
    assert texts(toks)[:2] == ["ehm", "il"]
    assert toks[0].is_filler and toks[0].word_index == 0
    assert len(toks) == 10


def test_tokenize_hyp_recognises_fillers_and_truncations():
    hyp = [H("Uhm,"), H("il"), H("propo-"), H("progetto"), H("eh?"), H("[Music]"), H("Mmm.")]
    assert texts(tokenize(hyp, "it", "literal", "hyp")) == ["il", "propo-", "progetto", "eh"]
    assert texts(tokenize(hyp, "it", "fidelity", "hyp")) == ["il", "progetto", "eh"]
    verbatim = tokenize(hyp, "it", "verbatim", "hyp")
    assert texts(verbatim) == ["ehm", "il", "propo-", "progetto", "eh", "mh"]
    assert [t.is_filler for t in verbatim] == [True, False, False, False, False, True]


def test_tokenize_word_lang_overrides_segment():
    toks = tokenize([W("um", "filler", lang="en")], "it", "verbatim", "ref")
    assert texts(toks) == ["um"]


# --------------------------------------------------------------------------- alignment


def tok(*words):
    return tokenize([H(w) for w in words], "it", "literal", "hyp")


def test_align_counts():
    counts, pairs = align(tok("a", "b", "c", "d"), tok("a", "x", "c", "d", "e"))
    assert counts == Counts(hits=3, substitutions=1, deletions=0, insertions=1)
    assert counts.ref_words == 4 and counts.errors == 2
    assert ("substitute", 1, 1) in pairs and ("insert", -1, 4) in pairs


def test_align_empty_sides():
    assert align([], tok("a", "b"))[0] == Counts(insertions=2)
    assert align(tok("a"), [])[0] == Counts(deletions=1)
    assert align([], [])[0] == Counts()


# ------------------------------------------------------------------------- disfluency


def test_repetition_recall_ignores_which_occurrence_is_aligned():
    ref = tokenize([W("il,", "repetition"), W("il,", "repetition"), W("il"), W("progetto")],
                   "it", "verbatim", "ref")  # fmt: skip
    for hyp_words, kept in [(["il", "progetto"], 0), (["il", "il", "progetto"], 1),
                            (["il", "il", "il", "il", "progetto"], 2)]:  # fmt: skip
        hyp = tokenize([H(w) for w in hyp_words], "it", "verbatim", "hyp")
        assert disfluency_counts(ref, hyp).kept.get("repetition", 0) == kept


def test_sequence_repetition_recall():
    ref = tokenize([W("se", "repetition"), W("vuoi,", "repetition"), W("se"), W("vuoi")],
                   "it", "verbatim", "ref")  # fmt: skip
    kept = disfluency_counts(ref, tokenize([H("se"), H("vuoi")], "it", "verbatim", "hyp")).kept
    assert kept.get("repetition", 0) == 0
    full = tokenize([H("se"), H("vuoi"), H("se"), H("vuoi")], "it", "verbatim", "hyp")
    assert disfluency_counts(ref, full).kept["repetition"] == 2


def test_disfluency_counts():
    ref = tokenize(
        [W("ehm", "filler"), W("il,", "repetition"), W("il"), W("propo-", "truncated"),
         W("proposta"), W("eh", "filler"), W("ok")],
        "it", "verbatim", "ref",
    )  # fmt: skip
    # Keeps the first filler (as "eh"), drops the repetition and the second filler,
    # keeps the truncation, invents one filler at the end.
    hyp = tokenize(
        [H("eh"), H("il"), H("propo-"), H("proposta"), H("ok"), H("uhm")], "it", "verbatim", "hyp"
    )
    d = disfluency_counts(ref, hyp)
    assert d.ref == {"filler": 2, "repetition": 1, "truncated": 1}
    assert d.kept == {"filler": 1, "truncated": 1}
    assert d.hyp_fillers == 2
    assert d.invented_fillers == 1


# ------------------------------------------------------------------ segments and scoring


def test_assign_words_by_midpoint_and_nearest():
    ref = transcript(seg(0, 2, W("a")), seg(5, 8, W("b")), kind="reference")
    hyp = transcript(
        seg(0, 9, H("x", 0.5, 1.0), H("y", 2.5, 3.0), H("z", 4.0, 4.6), H("w", 9.0, 9.5),
            lang=None),
    )  # fmt: skip
    groups = assign_words(ref, hyp)
    # y (2.75) is nearer to segment 0, z (4.3) to segment 1.
    assert [[w.text for w in g] for g in groups] == [["x", "y"], ["z", "w"]]


def test_assign_words_without_timestamps_spreads_evenly():
    ref = transcript(seg(0, 5, W("a")), seg(5, 10, W("b")), kind="reference")
    hyp = transcript(seg(0, 10, H("p"), H("q"), H("r"), H("s"), lang="it"))
    assert [[w.text for w in g] for g in assign_words(ref, hyp)] == [["p", "q"], ["r", "s"]]


def test_score_transcript_end_to_end():
    ref = transcript(
        seg(0, 4, W("Ehm,", "filler"), W("ci"), W("vediamo"), W("lunedì,", "false_start"),
            W("no,", "edit_term"), W("martedì.")),
        seg(4, 6, W("Ok."), overlap=True),
        seg(6, 9, W("Va"), W("bene.")),
        kind="reference",
    )  # fmt: skip
    hyp = transcript(
        seg(0, 9, H("Ci", 0.5, 0.8), H("vediamo", 0.8, 1.2), H("martedì.", 2.5, 3.5),
            H("Ok.", 4.5, 5.0), H("Va", 6.5, 7.0), H("bene", 7.0, 7.5), H("eh.", 8, 8.5),
            lang="it"),
    )  # fmt: skip
    scores = score_transcript(ref, hyp)
    assert len(scores) == 2  # the overlap segment and its hypothesis words are excluded
    # literal: ref "ci vediamo lunedì no martedì" + "va bene", hyp drops "lunedì no";
    # the hypothesis filler "eh" is removed by the literal metric.
    assert wer_of(scores, "literal") == pytest.approx(2 / 7)
    # fidelity: ref "ci vediamo martedì" + "va bene" -> perfect.
    assert wer_of(scores, "fidelity") == 0
    # verbatim: ref has 8 tokens ("ehm" + 5 + "va bene"); errors: ehm, lunedì, no
    # deleted, "eh" inserted.
    assert wer_of(scores, "verbatim") == pytest.approx(4 / 8)
    d = scores[0].disfluency + scores[1].disfluency
    assert d.ref == {"filler": 1, "false_start": 1, "edit_term": 1}
    assert sum(d.kept.values()) == 0
    assert d.invented_fillers == 1


def test_bootstrap_ci_brackets_point_estimate_and_is_reproducible():
    scores = [
        SegmentScore("it", {m: Counts(hits=9, substitutions=1) for m in
                            ("fidelity", "literal", "verbatim")}, None)
        for _ in range(5)
    ] + [
        SegmentScore("it", {m: Counts(hits=5, deletions=5) for m in
                            ("fidelity", "literal", "verbatim")}, None)
        for _ in range(5)
    ]  # fmt: skip
    point = wer_of(scores, "literal")
    assert point == pytest.approx(30 / 100)
    lo, hi = bootstrap_ci(scores, "literal", n=500)
    assert lo <= point <= hi
    assert 0.1 <= lo < hi <= 0.5
    assert bootstrap_ci(scores, "literal", n=500) == (lo, hi)


def test_bootstrap_ci_empty():
    assert bootstrap_ci([], "literal") is None
    assert wer_of([], "literal") is None


def test_score_system_and_report(tmp_path):
    from parola.eval.report import score_system, write_report
    from parola.eval.systems import SYSTEMS
    from parola.manifest import ManifestRecord

    ref = transcript(seg(0, 4, W("Ehm,", "filler"), W("ciao"), W("a"), W("tutti.")),
                     kind="reference")  # fmt: skip
    hyp = transcript(seg(0, 4, H("Ciao", 1, 1.5), H("tutti.", 2, 3), lang="it"))
    (tmp_path / "data").mkdir()
    ref.save(tmp_path / "data" / "it-001.ref.json")
    system = SYSTEMS["turbo"]
    (tmp_path / "hyp" / system.name).mkdir(parents=True)
    hyp.save(tmp_path / "hyp" / system.name / "it-001.json")
    record = ManifestRecord(
        id="it-001", audio="data/it-001.m4a", reference="data/it-001.ref.json",
        reference_quality="silver", lang="it", duration=100, source="test", license="test",
        consent=True,
    )  # fmt: skip
    rows = score_system(system, [record], tmp_path, tmp_path / "hyp", {"it-001": 5.0})
    assert [r.scope for r in rows] == ["all", "lang:it", "it-001"]
    all_row = rows[0].values
    assert all_row["literal"] == pytest.approx(1 / 3)  # "a" deleted out of ciao/a/tutti
    assert all_row["filler_ref"] == 1 and all_row["filler_kept"] == 0
    assert all_row["rtf"] == pytest.approx(0.05)
    md, csv_path = write_report(rows, [system], [record], tmp_path / "results" / "r")
    text = md.read_text()
    assert "| `turbo` | all | **33.3 [" in text  # fidelity: "a" deleted
    assert all_row["fidelity_del"] == 1 and all_row["fidelity_sub"] == 0
    assert "it-001 (it, 2 min, silver)" in text
    assert csv_path.read_text().splitlines()[0].startswith("system,scope,fidelity,")
