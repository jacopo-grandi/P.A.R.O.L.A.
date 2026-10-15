"""Common interface for ASR backends."""

from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

from ilat.schema import Segment


@dataclass
class ASRResult:
    segments: list[Segment]
    language: str | None


class ASRBackend(Protocol):
    name: str
    model: str

    def transcribe(self, wav_path: Path, language: str | None = None) -> ASRResult:
        """Transcribe a 16 kHz mono wav. ``language=None`` means automatic detection."""
        ...
