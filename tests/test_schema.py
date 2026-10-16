from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from parola.schema import (
    CleanSentence,
    CleanTranscript,
    Metadata,
    Segment,
    Transcript,
    Word,
    WordRef,
    format_timestamp,
    parse_timestamp,
    to_text,
)


def make_metadata(**kw) -> Metadata:
    base = dict(
        audio_file="call.m4a",
        duration=12.5,
        backend="fake",
        model="fake-model",
        language_detected="it",
        created_at=datetime(2026, 10, 15, 9, 0, tzinfo=UTC),
        parola_version="0.1.0",
    )
    return Metadata(**{**base, **kw})


def make_transcript() -> Transcript:
    return Transcript(
        metadata=make_metadata(),
        segments=[
            Segment(
                text="Ehm, allora, iniziamo.",
                start=0.0,
                end=2.4,
                lang="it",
                words=[
                    Word(text="Ehm,", start=0.0, end=0.5, tags=["filler"]),
                    Word(text="allora,", start=0.6, end=1.2),
                    Word(text="iniziamo.", start=1.3, end=2.4),
                ],
            ),
            Segment(text="Let's go.", start=3661.0, end=3662.25, lang="en"),
        ],
    )


def test_json_roundtrip():
    t = make_transcript()
    assert Transcript.from_json(t.to_json()) == t


def test_files_from_before_the_rename_still_load():
    data = make_transcript().model_dump(mode="json")
    data["metadata"]["ilat_version"] = data["metadata"].pop("parola_version")
    t = Transcript.model_validate(data)
    assert t.metadata.parola_version == "0.1.0"
    assert '"parola_version"' in t.to_json() and "ilat_version" not in t.to_json()


def test_defaults():
    w = make_transcript().segments[0].words[1]
    assert w.tags == []
    assert w.lang is None
    assert make_transcript().metadata.kind == "asr"


def test_word_without_timestamps():
    w = Word(text="ciao")
    assert w.start is None and w.end is None


def test_word_with_only_one_timestamp_rejected():
    with pytest.raises(ValidationError):
        Word(text="ciao", start=1.0)


def test_end_before_start_rejected():
    with pytest.raises(ValidationError):
        Word(text="x", start=2.0, end=1.0)
    with pytest.raises(ValidationError):
        Segment(text="x", start=2.0, end=1.0)


def test_negative_time_rejected():
    with pytest.raises(ValidationError):
        Segment(text="x", start=-0.1, end=1.0)


def test_unknown_tag_rejected():
    with pytest.raises(ValidationError):
        Word(text="ehm", tags=["hesitation"])


def test_duplicate_tags_rejected():
    with pytest.raises(ValidationError):
        Word(text="ehm", tags=["filler", "filler"])


@pytest.mark.parametrize("text", ["", "due parole", " ciao"])
def test_word_text_must_be_one_token(text):
    with pytest.raises(ValidationError):
        Word(text=text)


def test_unknown_lang_rejected():
    with pytest.raises(ValidationError):
        Word(text="hola", lang="es")


def test_unsorted_segments_rejected():
    with pytest.raises(ValidationError):
        Transcript(
            metadata=make_metadata(),
            segments=[Segment(text="b", start=5, end=6), Segment(text="a", start=1, end=2)],
        )


def test_overlapping_segments_allowed():
    Transcript(
        metadata=make_metadata(),
        segments=[
            Segment(text="a", start=1, end=4, overlap=True),
            Segment(text="b", start=2, end=3, overlap=True),
        ],
    )


def test_wrong_schema_version_rejected():
    data = make_transcript().model_dump(mode="json")
    data["schema_version"] = "0.1"
    with pytest.raises(ValidationError):
        Transcript.model_validate(data)


@pytest.mark.parametrize(
    ("seconds", "expected"),
    [
        (0, "00:00:00.000"),
        (1.2345, "00:00:01.234"),
        (59.9996, "00:01:00.000"),
        (3661.25, "01:01:01.250"),
    ],
)
def test_format_timestamp(seconds, expected):
    assert format_timestamp(seconds) == expected


@pytest.mark.parametrize("seconds", [0, 1.234, 60, 3661.25, 362.304])
def test_parse_timestamp_inverts_format(seconds):
    assert parse_timestamp(format_timestamp(seconds)) == pytest.approx(seconds)


@pytest.mark.parametrize("value", ["1:2:3", "00:61:00.000", "00:00:00", "abc"])
def test_parse_timestamp_invalid(value):
    with pytest.raises(ValueError):
        parse_timestamp(value)


def test_to_text():
    assert to_text(make_transcript()) == (
        "[00:00:00.000 - 00:00:02.400] Ehm, allora, iniziamo.\n"
        "[01:01:01.000 - 01:01:02.250] Let's go.\n"
    )


def test_to_text_empty():
    t = make_transcript()
    t.segments = []
    assert to_text(t) == ""


def test_clean_refs():
    verbatim = make_transcript()
    clean = CleanTranscript(
        verbatim_file="call.ref.json",
        sentences=[
            CleanSentence(text="Allora, iniziamo.", source=[WordRef(segment=0, word=1),
                                                            WordRef(segment=0, word=2)]),
            CleanSentence(text="Boh.", source=[WordRef(segment=1, word=0)]),
        ],
    )  # fmt: skip
    assert clean.check_refs(verbatim) == ["sentence 1: no word 0 in segment 1"]


def test_clean_sentence_needs_source():
    with pytest.raises(ValidationError):
        CleanSentence(text="Inventata.", source=[])
