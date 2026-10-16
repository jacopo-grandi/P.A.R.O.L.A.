"""Transcript data model (schema 1.0).

Structural validation lives here. Rules from docs/conventions.md that only apply to
hand-made references (filler inventory, spellings, ...) are checked by ``ilat.schema.lint``.
"""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, Field, field_validator, model_validator

SCHEMA_VERSION = "1.0"

Lang = Literal["it", "en"]
Channel = Literal["mic", "system", "mixed"]
WordTag = Literal[
    "filler",
    "truncated",
    "repetition",
    "reduplication",
    "false_start",
    "edit_term",
    "backchannel",
    "nonverbal",
    "uncertain",
]


def _check_interval(start: float | None, end: float | None) -> None:
    if (start is None) != (end is None):
        raise ValueError("start and end must be both set or both missing")
    if start is not None and end is not None and end < start:
        raise ValueError(f"end ({end}) is before start ({start})")


class Word(BaseModel):
    text: str = Field(min_length=1)
    # Optional: hand-made references usually have segment-level timestamps only.
    start: float | None = Field(default=None, ge=0)
    end: float | None = Field(default=None, ge=0)
    # None means "same as the segment" (ASR output); references set it on every spoken word.
    lang: Lang | None = None
    probability: float | None = None
    tags: list[WordTag] = Field(default_factory=list)
    # ASR output only: a second transcription disagrees here, the word is worth checking
    # (ilat.doubt, decision 0014). Not a disfluency tag.
    doubtful: bool = False

    @field_validator("text")
    @classmethod
    def _no_whitespace(cls, v: str) -> str:
        if v != v.strip() or any(c.isspace() for c in v):
            raise ValueError(f"word text must not contain whitespace: {v!r}")
        return v

    @field_validator("tags")
    @classmethod
    def _unique_tags(cls, v: list[WordTag]) -> list[WordTag]:
        if len(set(v)) != len(v):
            raise ValueError(f"duplicate tags: {v}")
        return v

    @model_validator(mode="after")
    def _interval(self) -> Word:
        _check_interval(self.start, self.end)
        return self


class Segment(BaseModel):
    start: float = Field(ge=0)
    end: float = Field(ge=0)
    text: str
    lang: Lang | None = None
    channel: Channel | None = None
    speaker: str | None = None
    # §2.14: overlapping speech on the same channel.
    overlap: bool = False
    words: list[Word] = Field(default_factory=list)

    @model_validator(mode="after")
    def _interval(self) -> Segment:
        _check_interval(self.start, self.end)
        return self


class Metadata(BaseModel):
    kind: Literal["asr", "reference"] = "asr"
    audio_file: str
    duration: float = Field(ge=0)
    backend: str | None = None
    model: str | None = None
    language_requested: str | None = None
    language_detected: str | None = None
    annotator: str | None = None
    created_at: datetime
    ilat_version: str


class Transcript(BaseModel):
    schema_version: str = SCHEMA_VERSION
    metadata: Metadata
    segments: list[Segment] = Field(default_factory=list)

    @field_validator("schema_version")
    @classmethod
    def _known_version(cls, v: str) -> str:
        if v != SCHEMA_VERSION:
            raise ValueError(f"unsupported schema_version {v!r} (expected {SCHEMA_VERSION})")
        return v

    @model_validator(mode="after")
    def _sorted_segments(self) -> Transcript:
        starts = [s.start for s in self.segments]
        if starts != sorted(starts):
            raise ValueError("segments must be sorted by start time")
        return self

    def to_json(self) -> str:
        return self.model_dump_json(indent=2)

    @classmethod
    def from_json(cls, data: str) -> Transcript:
        return cls.model_validate_json(data)

    @classmethod
    def load(cls, path: Path) -> Transcript:
        return cls.from_json(path.read_text(encoding="utf-8"))

    def save(self, path: Path) -> None:
        path.write_text(self.to_json() + "\n", encoding="utf-8")
