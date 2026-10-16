"""Hand-built cases for every rule in docs/conventions.md checked by the linter."""

from datetime import UTC, datetime

import pytest

from parola.schema import Metadata, Segment, Transcript, Word
from parola.schema.lint import has_errors, lint


def W(text, *tags, lang="it", **kw):
    return Word(text=text, tags=list(tags), lang=lang, **kw)


def seg(*words, lang="it", start=0.0, end=5.0, **kw):
    return Segment(
        start=start, end=end, lang=lang, text=" ".join(w.text for w in words), words=list(words),
        **kw,
    )  # fmt: skip


def ref(*segments):
    return Transcript(
        metadata=Metadata(
            kind="reference",
            audio_file="x.m4a",
            duration=60,
            created_at=datetime(2026, 10, 15, tzinfo=UTC),
            parola_version="0",
        ),
        segments=list(segments),
    )


def messages(t):
    return [i.message for i in lint(t) if i.severity == "error"]


def test_valid_reference_has_no_issues():
    t = ref(
        seg(
            W("Ehm,", "filler"),
            W("ci"),
            W("vediamo"),
            W("lunedì,", "false_start"),
            W("no,", "edit_term"),
            W("martedì"),
            W("per"),
            W("la"),
            W("call", lang="en"),
            W("[risata]", "nonverbal", lang=None),
            W("propo-", "truncated"),
            W("proposta"),
            W("[inaudibile]", lang=None),
            W("Chat", "uncertain"),
        ),
        seg(W("sì,", "reduplication"), W("sì.", "backchannel"), start=5.0, end=6.0),
    )
    assert lint(t) == []


def test_segment_without_lang():
    assert "segment has no lang" in messages(ref(seg(W("ciao"), lang=None)))


def test_word_without_lang():
    assert "word has no lang" in messages(ref(seg(W("ciao", lang=None))))


def test_segment_too_long():
    errs = messages(ref(seg(W("ciao"), start=0, end=31)))
    assert any("max 30 s" in e for e in errs)


def test_text_must_match_words():
    s = seg(W("ciao"))
    s.text = "ciao ciao"
    assert any("does not match" in e for e in messages(ref(s)))


@pytest.mark.parametrize(
    "text", ["perchè", "okay", "Okay,", "OK", "vabbe'", "vabbé", "be'", "poichè"]
)
def test_forbidden_spellings(text):
    errs = messages(ref(seg(W(text))))
    assert any("is not allowed" in e for e in errs), errs


@pytest.mark.parametrize("text", ["perché", "ok", "Ok,", "vabbè", "beh", "'sta", "c'ho"])
def test_allowed_spellings(text):
    assert lint(ref(seg(W(text)))) == []


def test_va_be_split_spelling():
    errs = messages(ref(seg(W("va"), W("be'"))))
    assert any("va be'" in e for e in errs)


def test_digits_are_a_warning():
    issues = lint(ref(seg(W("4000"))))
    assert [i.severity for i in issues] == ["warning"]


@pytest.mark.parametrize("text,lang", [("ehm", "it"), ("Eh,", "it"), ("um", "en"), ("ah", "it")])
def test_filler_inventory_ok(text, lang):
    assert lint(ref(seg(W(text, "filler", lang=lang), lang=lang))) == []


@pytest.mark.parametrize(
    "text,lang", [("ehmm", "it"), ("um", "it"), ("ehm", "en"), ("allora", "it")]
)
def test_filler_outside_inventory(text, lang):
    errs = messages(ref(seg(W(text, "filler", lang=lang), lang=lang)))
    assert any("filler inventory" in e for e in errs)


def test_truncated_needs_hyphen_and_tag():
    assert any("must end with '-'" in e for e in messages(ref(seg(W("propo", "truncated")))))
    assert any("must have the tag 'truncated'" in e for e in messages(ref(seg(W("propo-")))))
    assert lint(ref(seg(W("propo-,", "truncated")))) == []


def test_nonverbal_rules():
    assert any("exactly the tag" in e for e in messages(ref(seg(W("[risata]", lang=None)))))
    assert any("only for" in e for e in messages(ref(seg(W("ciao", "nonverbal")))))
    assert any("must not have a lang" in e for e in messages(
        ref(seg(W("[tosse]", "nonverbal", lang="it")))
    ))  # fmt: skip
    assert any("unknown bracketed" in e for e in messages(ref(seg(W("[ride]", lang=None)))))


def test_inaudible_takes_no_tags():
    errs = messages(ref(seg(W("[inaudibile]", "uncertain", lang=None))))
    assert any("takes no tags" in e for e in errs)


def test_uncertain_without_parentheses():
    errs = messages(ref(seg(W("(Chat?)", "uncertain"))))
    assert any("without parentheses" in e for e in errs)


def test_repetition_needs_later_occurrence():
    ok = ref(seg(W("il,", "repetition"), W("il"), W("progetto")))
    assert lint(ok) == []
    bad = ref(seg(W("il"), W("progetto", "repetition")))
    assert any("no later occurrence" in e for e in messages(bad))


def test_word_timestamps_inside_segment_and_ordered():
    outside = ref(seg(W("ciao", start=6.0, end=6.5), start=0, end=5))
    assert any("outside the segment" in e for e in messages(outside))
    unordered = ref(seg(W("a", start=2.0, end=2.5), W("b", start=1.0, end=1.5)))
    assert any("not in order" in e for e in messages(unordered))


def test_has_errors():
    assert not has_errors(lint(ref(seg(W("4000")))))
    assert has_errors(lint(ref(seg(W("okay")))))


def test_untagged_repetition_is_a_warning():
    issues = lint(ref(seg(W("il"), W("il"), W("progetto"))))
    assert [(i.severity, i.word) for i in issues] == [("warning", 0)]
    assert "tag it 'rep' or 'red'" in issues[0].message


@pytest.mark.parametrize(
    "words",
    [
        [W("il,", "repetition"), W("il")],
        [W("sì,", "reduplication"), W("sì")],
        [W("eh", "filler"), W("eh", "filler")],
        [W("mh", "backchannel"), W("mh", "backchannel")],
        [W("[risata]", "nonverbal", lang=None), W("[risata]", "nonverbal", lang=None)],
    ],
)
def test_tagged_or_exempt_repetitions_pass(words):
    assert lint(ref(seg(*words))) == []


def test_glued_truncation_is_a_warning():
    issues = lint(ref(seg(W("fi-fissi"))))
    assert [i.severity for i in issues] == ["warning"]
    assert "'fi- fissi'" in issues[0].message
    assert lint(ref(seg(W("e-mail")))) == []
    assert lint(ref(seg(W("Bye-bye.", lang="en"), lang="en"))) == []
