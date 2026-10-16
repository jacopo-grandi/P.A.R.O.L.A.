"""The audio the app plays: a WAV copy of a call's FLAC, decoded when the call is opened.

WebKit, which draws the native app's window, cannot jump inside a FLAC file. Measured on an
hour-long test file with a beep on every minute: after a jump the beep came tens of seconds
late or never, with or without a SEEKTABLE, while in a WAV it came where asked. Chrome is
exact on both (results/2026-10-16-flac-seeking.md). So calls stay FLAC on disk (decision 0024)
and the player gets a WAV, decoded once (about a second per hour of call) into ``.playback/``
in the calls folder. Only the ``KEEP`` most recently opened are kept (about 115 MB per hour of
call each), and a deleted call's copy goes at once.
"""

from __future__ import annotations

import os
import subprocess
import threading
from pathlib import Path

from parola.audio.extract import FFmpegError

CACHE = ".playback"
KEEP = 3
_lock = threading.Lock()


def playable(folder: Path, source: Path) -> Path:
    """A file the player can seek in: ``source`` itself unless it is FLAC."""
    if source.suffix != ".flac":
        return source
    cache = folder / CACHE
    stat = source.stat()
    # The source's size and time in the name: a call recorded again under the same name, or
    # compressed anew, never plays an old copy.
    out = cache / f"{source.stem}.{stat.st_mtime_ns}-{stat.st_size}.wav"
    with _lock:
        if out.exists():
            os.utime(out)  # just opened: the last to go
            return out
        cache.mkdir(exist_ok=True)
        part = out.with_name(out.name + ".part")
        result = subprocess.run(
            ["ffmpeg", "-nostdin", "-loglevel", "error", "-y", "-i", str(source),
             "-c:a", "pcm_s16le", "-f", "wav", str(part)],
            capture_output=True, text=True, check=False,
        )  # fmt: skip
        if result.returncode != 0:
            part.unlink(missing_ok=True)
            raise FFmpegError(f"ffmpeg could not decode {source.name}: {result.stderr.strip()}")
        part.replace(out)
        _prune(cache)
    return out


def _prune(cache: Path) -> None:
    copies = sorted(cache.glob("*.wav"), key=lambda p: p.stat().st_mtime, reverse=True)
    for old in copies[KEEP:]:
        old.unlink(missing_ok=True)


def forget(folder: Path, name: str, channels: tuple[str, ...]) -> None:
    """Remove the copies of a call's channels (when the call is deleted)."""
    cache = folder / CACHE
    with _lock:
        for channel in channels:
            for copy in cache.glob(f"{name}.{channel}.*.wav"):
                copy.unlink(missing_ok=True)
