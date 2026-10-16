"""Human-readable renderings of a transcript."""

import re

from parola.schema.transcript import Transcript


def format_timestamp(seconds: float) -> str:
    """Format seconds as ``HH:MM:SS.mmm``."""
    millis = round(seconds * 1000)
    hours, millis = divmod(millis, 3_600_000)
    minutes, millis = divmod(millis, 60_000)
    secs, millis = divmod(millis, 1000)
    return f"{hours:02d}:{minutes:02d}:{secs:02d}.{millis:03d}"


_TIMESTAMP = re.compile(r"^(\d+):([0-5]\d):([0-5]\d)\.(\d{3})$")


def parse_timestamp(value: str) -> float:
    """Inverse of ``format_timestamp``."""
    m = _TIMESTAMP.match(value)
    if not m:
        raise ValueError(f"invalid timestamp {value!r} (expected HH:MM:SS.mmm)")
    hours, minutes, secs, millis = (int(g) for g in m.groups())
    return hours * 3600 + minutes * 60 + secs + millis / 1000


def to_text(transcript: Transcript) -> str:
    """One line per segment: ``[start - end] text``."""
    lines = [
        f"[{format_timestamp(s.start)} - {format_timestamp(s.end)}] {s.text}"
        for s in transcript.segments
    ]
    return "\n".join(lines) + ("\n" if lines else "")
