from datetime import UTC, datetime

import pytest

from parola.annotate import AnnotationError, from_annotation, merge_segments, to_annotation
from parola.schema import Metadata, Segment, Transcript, Word
from parola.schema.lint import lint

HEADER = "# parola-annotation 1\n# status: reviewed\n# audio_file: call.m4a\n# duration: 60.000\n\n"


def parse(body: str) -> Transcript:
    return from_annotation(HEADER + body)


def words(t: Transcript, i: int = 0):
    return [(w.text, w.lang, w.tags) for w in t.segments[i].words]


def test_metadata_and_segment_header():
    t = parse("[00:00:01.000 - 00:00:04.500] lang=it channel=system speaker=A overlap\nciao\n")
    assert t.metadata.kind == "reference"
    assert t.metadata.audio_file == "call.m4a"
    assert t.metadata.duration == 60.0
    s = t.segments[0]
    assert (s.start, s.end, s.lang, s.channel, s.speaker, s.overlap) == (
        1.0, 4.5, "it", "system", "A", True,
    )  # fmt: skip


def test_codes_and_punctuation():
    t = parse(
        "[00:00:00.000 - 00:00:05.000] lang=it\n"
        "Ci vediamo lunedì,|fs no|ed martedì per la call|en.\n"
    )
    assert words(t) == [
        ("Ci", "it", []),
        ("vediamo", "it", []),
        ("lunedì,", "it", ["false_start"]),
        ("no", "it", ["edit_term"]),
        ("martedì", "it", []),
        ("per", "it", []),
        ("la", "it", []),
        ("call.", "en", []),
    ]
    assert t.segments[0].text == "Ci vediamo lunedì, no martedì per la call."


def test_code_after_punctuation_is_equivalent():
    a = parse("[00:00:00.000 - 00:00:01.000] lang=it\nlunedì,|fs martedì\n")
    b = parse("[00:00:00.000 - 00:00:01.000] lang=it\nlunedì|fs, martedì\n")
    assert words(a) == words(b)


def test_brace_group():
    t = parse("[00:00:00.000 - 00:00:03.000] lang=it\n{Perché noi abbiamo}|fs... il cliente\n")
    assert words(t)[:3] == [
        ("Perché", "it", ["false_start"]),
        ("noi", "it", ["false_start"]),
        ("abbiamo...", "it", ["false_start"]),
    ]


def test_automatic_tags():
    t = parse(
        "[00:00:00.000 - 00:00:05.000] lang=it\n"
        "Ehm, la propo- la proposta [risata] (Le Chat?)|en, [inaudibile] eh? ah\n"
    )
    assert words(t) == [
        ("Ehm,", "it", ["filler"]),
        ("la", "it", []),
        ("propo-", "it", ["truncated"]),
        ("la", "it", []),
        ("proposta", "it", []),
        ("[risata]", None, ["nonverbal"]),
        ("Le", "en", ["uncertain"]),
        ("Chat,", "en", ["uncertain"]),
        ("[inaudibile]", None, []),
        ("eh?", "it", []),  # interrogative: not a filler
        ("ah", "it", []),  # ah/oh are never automatic fillers
    ]


def test_explicit_and_cancelled_filler():
    t = parse("[00:00:00.000 - 00:00:01.000] lang=it\nah|f eh|-f\n")
    assert words(t) == [("ah", "it", ["filler"]), ("eh", "it", [])]


def test_backchannel_segment_disables_auto_filler():
    t = parse("[00:00:00.000 - 00:00:01.000] lang=it bc\nmh mh\n")
    assert words(t) == [("mh", "it", ["backchannel"]), ("mh", "it", ["backchannel"])]


def test_multiline_text_and_sorting():
    t = parse(
        "[00:00:05.000 - 00:00:06.000] lang=en\nsecond\n\n"
        "[00:00:00.000 - 00:00:02.000] lang=it\nprima\nriga\n"
    )
    assert [s.text for s in t.segments] == ["prima riga", "second"]


@pytest.mark.parametrize(
    "body,message",
    [
        ("ciao\n", "before the first segment"),
        ("[00:00:00.000 - 00:00:01.000] lang=fr\nbonjour\n", "unknown segment attribute"),
        ("[00:00:02.000 - 00:00:01.000] lang=it\nciao\n", "end is before start"),
        ("[00:00:00.000 - 00:00:01.000] lang=it\n\n", "has no text"),
        ("[00:00:00.000 - 00:00:01.000] lang=it\nciao|xx\n", "unknown code"),
        ("[00:00:00.000 - 00:00:01.000] lang=it\nciao) mondo\n", "cannot parse"),
        ("[0:00 - 00:00:01.000] lang=it\nciao\n", "invalid timestamp"),
    ],
)
def test_errors(body, message):
    with pytest.raises(AnnotationError, match=message):
        parse(body)


def test_missing_metadata_header():
    with pytest.raises(AnnotationError, match="audio_file"):
        from_annotation("# status: reviewed\n[00:00:00.000 - 00:00:01.000] lang=it\nciao\n")


def test_roundtrip_reference():
    src = (
        "[00:00:00.000 - 00:00:05.000] lang=it channel=mic\n"
        "Ehm, il,|rep il progetto lunedì,|fs no|ed martedì per la call|en ah|f eh|-f\n\n"
        "[00:00:05.000 - 00:00:06.000] lang=it bc\nsì,|red sì.\n\n"
        "[00:00:06.000 - 00:00:08.000] lang=en speaker=B overlap\n"
        "So (Le Chat?)|it, [tosse] [inaudibile] prop- proper.\n"
    )
    first = parse(src)
    assert lint(first) == []
    second = from_annotation(to_annotation(first))
    assert second.segments == first.segments
    assert second.metadata.audio_file == first.metadata.audio_file


def test_draft_from_asr_output():
    asr = Transcript(
        metadata=Metadata(
            audio_file="call.m4a", duration=12.0, backend="mlx-whisper", model="m",
            created_at=datetime(2026, 10, 15, tzinfo=UTC), parola_version="0",
        ),
        segments=[
            Segment(start=0, end=2, text="Ehm, okay.", lang="it", words=[
                Word(text="Ehm,", start=0, end=0.5), Word(text="okay.", start=0.6, end=1),
            ]),
        ],
    )  # fmt: skip
    draft = to_annotation(asr, draft=True)
    assert "[00:00:00.000 - 00:00:02.000] lang=it\nEhm, okay.\n" in draft
    assert "|" not in draft.split("[00:00:00.000")[1]
    # A draft cannot be imported until it is marked as reviewed.
    with pytest.raises(AnnotationError, match="status"):
        from_annotation(draft)
    imported = from_annotation(draft.replace("# status: draft", "# status: reviewed"))
    assert imported.segments[0].words[0].tags == ["filler"]
    assert any("'okay'" in i.message for i in lint(imported))


def _asr(*segments: Segment) -> Transcript:
    return Transcript(
        metadata=Metadata(
            audio_file="call.m4a",
            duration=100.0,
            created_at=datetime(2026, 10, 15, tzinfo=UTC),
            parola_version="0",
        ),
        segments=list(segments),
    )


def _seg(start, end, text, **kw):
    return Segment(
        start=start, end=end, text=text, lang=kw.pop("lang", "it"),
        words=[Word(text=t) for t in text.split()], **kw,
    )  # fmt: skip


def test_merge_joins_short_gaps():
    t = merge_segments(_asr(_seg(0, 1, "ciao"), _seg(1.5, 2, "a tutti"), _seg(2.8, 3, "oggi")))
    [s] = t.segments
    assert (s.start, s.end, s.text) == (0, 3, "ciao a tutti oggi")
    assert [w.text for w in s.words] == ["ciao", "a", "tutti", "oggi"]


def test_merge_gap_threshold_is_inclusive():
    t = merge_segments(_asr(_seg(0, 1, "a"), _seg(2.0, 3, "b"), _seg(4.01, 5, "c")))
    assert [s.text for s in t.segments] == ["a b", "c"]


def test_merge_respects_max_duration():
    t = merge_segments(_asr(_seg(0, 20, "a"), _seg(20.5, 29.5, "b"), _seg(30, 31, "c")))
    assert [s.text for s in t.segments] == ["a b", "c"]


def test_merge_keeps_different_lang_channel_speaker_and_overlap_apart():
    t = merge_segments(
        _asr(
            _seg(0, 1, "uno"),
            _seg(1.1, 2, "two", lang="en"),
            _seg(2.1, 3, "tre", channel="mic"),
            _seg(3.1, 4, "quattro", channel="mic", speaker="B"),
            _seg(4.1, 5, "cinque", channel="mic", speaker="B", overlap=True),
        )
    )
    assert len(t.segments) == 5


def test_merge_keeps_text_of_unaligned_segments_in_draft():
    t = merge_segments(
        _asr(_seg(0, 1, "creare"), Segment(start=1, end=1.5, text="tutti i token", lang="it"))
    )
    [s] = t.segments
    assert s.text == "creare tutti i token"
    assert "creare tutti i token\n" in to_annotation(t, draft=True)


def test_merge_does_not_modify_input():
    original = _asr(_seg(0, 1, "a"), _seg(1.2, 2, "b"))
    merge_segments(original)
    assert len(original.segments) == 2
