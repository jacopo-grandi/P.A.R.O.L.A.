"""Dataset manifests: one JSON record per audio file (``data/manifests/*.jsonl``).

Manifests are versioned in git, so they must never contain personal data: no names of
participants, only a short description of the source.
"""

from __future__ import annotations

import json
from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path, PurePosixPath
from typing import Literal

from pydantic import BaseModel, Field, ValidationError, field_validator, model_validator

from ilat.schema import Transcript
from ilat.schema.lint import has_errors, lint

PRIVATE_DIR = PurePosixPath("data/private")

# "gold": every word and tag checked by listening to the whole audio.
# "silver": words checked by a human, but disfluency tags not fully verified (for instance,
# fillers proposed by a model and checked only by sampling).
# "adjudicated": every disagreement between two independent systems decided by listening
# (between silver and gold: words where both systems agree are not listened to).
# Both count for every metric (decision 0005, amended 2026-10-15); reports state the
# quality of the references behind each number.
ReferenceQuality = Literal["gold", "adjudicated", "silver"]

# Sources whose outputs carry a non-commercial license into anything derived from them
# (decision 0009). Data marked with any of these must never train ilat-free.
NON_FREE_SOURCES = {
    "crisperwhisper": "nyra health Non-Commercial Research License (weights and Outputs)",
    "kiparla": "CC BY-NC-SA 4.0 and KIParla terms of use",
}
# Tolerance between the manifest duration and the reference metadata duration.
DURATION_TOLERANCE = 1.0


class ManifestRecord(BaseModel):
    id: str = Field(min_length=1)
    audio: str = Field(min_length=1, description="path relative to the repository root")
    reference: str | None = Field(default=None, description="reference transcript JSON")
    reference_quality: ReferenceQuality | None = None
    # Systems or corpora whose outputs went into this record (see NON_FREE_SOURCES).
    derived_from: list[str] = Field(default_factory=list)
    lang: Literal["it", "en", "mixed"]
    duration: float = Field(gt=0)
    source: str = Field(min_length=1)
    license: str = Field(min_length=1)
    consent: bool
    notes: str | None = None

    @field_validator("audio", "reference")
    @classmethod
    def _relative_posix(cls, v: str | None) -> str | None:
        if v is not None and (v.startswith("/") or "\\" in v or ".." in PurePosixPath(v).parts):
            raise ValueError(f"path must be relative to the repository root: {v!r}")
        return v

    @model_validator(mode="after")
    def _quality_with_reference(self) -> ManifestRecord:
        if (self.reference is None) != (self.reference_quality is None):
            raise ValueError("reference and reference_quality must be set together")
        return self

    @property
    def counts_for_disfluency_metrics(self) -> bool:
        return self.reference_quality in ("gold", "adjudicated", "silver")

    @property
    def is_private(self) -> bool:
        return PurePosixPath(self.audio).is_relative_to(PRIVATE_DIR)


@dataclass
class ManifestReport:
    records: list[ManifestRecord] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    def hours_by_lang(self) -> dict[str, float]:
        hours: dict[str, float] = defaultdict(float)
        for r in self.records:
            hours[r.lang] += r.duration / 3600
        return dict(hours)

    def summary(self) -> str:
        quality: dict[str, int] = defaultdict(int)
        for r in self.records:
            quality[r.reference_quality or "none"] += 1
        refs = ", ".join(
            f"{quality[q]} {q}" for q in ("gold", "adjudicated", "silver", "none") if quality[q]
        )
        by_lang = ", ".join(f"{k} {v:.2f} h" for k, v in sorted(self.hours_by_lang().items()))
        return f"{len(self.records)} records (references: {refs})" + (
            f"; {by_lang}" if by_lang else ""
        )


def check_free_training_sources(records: list[ManifestRecord]) -> list[str]:
    """Errors for records that must not train ilat-free (decision 0009)."""
    return [
        f"{r.id}: derived from {src} ({NON_FREE_SOURCES[src]}): not allowed for ilat-free"
        for r in records
        for src in r.derived_from
        if src in NON_FREE_SOURCES
    ]


def check_manifest(path: Path, root: Path, check_files: bool = False) -> ManifestReport:
    """Validate every record; with ``check_files`` also open audio and references."""
    report = ManifestReport()
    seen: set[str] = set()
    for n, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        if not line.strip():
            continue
        try:
            record = ManifestRecord.model_validate(json.loads(line))
        except (json.JSONDecodeError, ValidationError) as e:
            report.errors.append(f"line {n}: {e}")
            continue
        if record.id in seen:
            report.errors.append(f"line {n}: duplicate id {record.id!r}")
        seen.add(record.id)
        if record.is_private and not record.consent:
            report.errors.append(f"line {n}: private recording {record.id!r} without consent")
        if check_files:
            _check_files(n, record, root, report)
        report.records.append(record)
    return report


def _check_files(n: int, record: ManifestRecord, root: Path, report: ManifestReport) -> None:
    if not (root / record.audio).is_file():
        report.errors.append(f"line {n}: audio not found: {record.audio}")
    if record.reference is None:
        report.warnings.append(f"line {n}: {record.id!r} has no reference yet")
        return
    ref_path = root / record.reference
    if not ref_path.is_file():
        report.errors.append(f"line {n}: reference not found: {record.reference}")
        return
    try:
        ref = Transcript.load(ref_path)
    except ValidationError as e:
        report.errors.append(f"line {n}: invalid reference {record.reference}: {e}")
        return
    if ref.metadata.kind != "reference":
        report.errors.append(f"line {n}: {record.reference} is not a reference transcript")
    issues = lint(ref)
    if has_errors(issues):
        n_err = sum(i.severity == "error" for i in issues)
        report.errors.append(f"line {n}: {record.reference} has {n_err} convention errors")
    if abs(ref.metadata.duration - record.duration) > DURATION_TOLERANCE:
        report.errors.append(
            f"line {n}: duration {record.duration} differs from reference "
            f"({ref.metadata.duration:.1f} s)"
        )
