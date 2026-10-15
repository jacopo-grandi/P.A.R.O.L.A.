from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from ilat.schema import Metadata, Segment, Transcript, Word, format_timestamp, to_text


def make_transcript() -> Transcript:
    return Transcript(
        metadata=Metadata(
            audio_file="call.m4a",
            duration=12.5,
            backend="fake",
            model="fake-model",
            language_requested=None,
            language_detected="it",
            created_at=datetime(2026, 10, 15, 9, 0, tzinfo=UTC),
            ilat_version="0.1.0",
        ),
        segments=[
            Segment(
                text="Ehm, allora, iniziamo.",
                start=0.0,
                end=2.4,
                lang="it",
                words=[
                    Word(text="Ehm,", start=0.0, end=0.5),
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


def test_tags_default_empty():
    assert make_transcript().segments[0].words[0].tags == []


def test_end_before_start_rejected():
    with pytest.raises(ValidationError):
        Word(text="x", start=2.0, end=1.0)


def test_negative_time_rejected():
    with pytest.raises(ValidationError):
        Segment(text="x", start=-0.1, end=1.0)


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


def test_to_text():
    assert to_text(make_transcript()) == (
        "[00:00:00.000 - 00:00:02.400] Ehm, allora, iniziamo.\n"
        "[01:01:01.000 - 01:01:02.250] Let's go.\n"
    )


def test_to_text_empty():
    t = make_transcript()
    t.segments = []
    assert to_text(t) == ""
