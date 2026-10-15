"""Transcript data model.

Provisional schema (version 0.1): it will be fixed and fully validated in Phase 1.
Word ``tags`` (filler, truncated, repetition, false_start) are always empty for now.
"""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, Field, model_validator

SCHEMA_VERSION = "0.1"

Channel = Literal["mic", "system", "mixed"]


class _Timed(BaseModel):
    start: float = Field(ge=0)
    end: float = Field(ge=0)

    @model_validator(mode="after")
    def _end_after_start(self) -> _Timed:
        if self.end < self.start:
            raise ValueError(f"end ({self.end}) is before start ({self.start})")
        return self


class Word(_Timed):
    text: str
    probability: float | None = None
    tags: list[str] = Field(default_factory=list)


class Segment(_Timed):
    text: str
    lang: str | None = None
    channel: Channel | None = None
    words: list[Word] = Field(default_factory=list)


class Metadata(BaseModel):
    audio_file: str
    duration: float = Field(ge=0)
    backend: str
    model: str
    language_requested: str | None = None
    language_detected: str | None = None
    created_at: datetime
    ilat_version: str


class Transcript(BaseModel):
    schema_version: str = SCHEMA_VERSION
    metadata: Metadata
    segments: list[Segment] = Field(default_factory=list)

    def to_json(self) -> str:
        return self.model_dump_json(indent=2)

    @classmethod
    def from_json(cls, data: str) -> Transcript:
        return cls.model_validate_json(data)

    def save(self, path: Path) -> None:
        path.write_text(self.to_json() + "\n", encoding="utf-8")
