from datetime import UTC, datetime

import pytest

from ilat.annotate import AnnotationError, from_annotation, to_annotation
from ilat.schema import Metadata, Segment, Transcript, Word
from ilat.schema.lint import lint

HEADER = "# ilat-annotation 1\n# status: reviewed\n# audio_file: call.m4a\n# duration: 60.000\n\n"


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
            created_at=datetime(2026, 10, 15, tzinfo=UTC), ilat_version="0",
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
