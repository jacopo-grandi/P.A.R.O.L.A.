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

from pydantic import BaseModel, Field, ValidationError, field_validator

from ilat.schema import Transcript
from ilat.schema.lint import has_errors, lint

PRIVATE_DIR = PurePosixPath("data/private")
# Tolerance between the manifest duration and the reference metadata duration.
DURATION_TOLERANCE = 1.0


class ManifestRecord(BaseModel):
    id: str = Field(min_length=1)
    audio: str = Field(min_length=1, description="path relative to the repository root")
    reference: str | None = Field(default=None, description="reference transcript JSON")
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
        with_ref = sum(r.reference is not None for r in self.records)
        by_lang = ", ".join(f"{k} {v:.2f} h" for k, v in sorted(self.hours_by_lang().items()))
        return f"{len(self.records)} records ({with_ref} with reference)" + (
            f": {by_lang}" if by_lang else ""
        )


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
