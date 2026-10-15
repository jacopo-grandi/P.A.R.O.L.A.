"""Human-readable renderings of a transcript."""

from ilat.schema.transcript import Transcript


def format_timestamp(seconds: float) -> str:
    """Format seconds as ``HH:MM:SS.mmm``."""
    millis = round(seconds * 1000)
    hours, millis = divmod(millis, 3_600_000)
    minutes, millis = divmod(millis, 60_000)
    secs, millis = divmod(millis, 1000)
    return f"{hours:02d}:{minutes:02d}:{secs:02d}.{millis:03d}"


def to_text(transcript: Transcript) -> str:
    """One line per segment: ``[start - end] text``."""
    lines = [
        f"[{format_timestamp(s.start)} - {format_timestamp(s.end)}] {s.text}"
        for s in transcript.segments
    ]
    return "\n".join(lines) + ("\n" if lines else "")
