"""Common interface for ASR backends."""

from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

from parola.schema import Segment


@dataclass
class ASRResult:
    segments: list[Segment]
    language: str | None


# Called with the share of the audio done so far (0..1), for a progress bar.
Progress = Callable[[float], None]


class ASRBackend(Protocol):
    name: str
    model: str
    # Optional: set by the caller before transcribe(); backends that can report progress call it.
    on_progress: Progress | None

    def transcribe(self, wav_path: Path, language: str | None = None) -> ASRResult:
        """Transcribe a 16 kHz mono wav. ``language=None`` means automatic detection."""
        ...
