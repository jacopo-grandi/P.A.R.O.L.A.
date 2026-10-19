"""How loud each channel of a call is, measured once, for playback normalization.

In a recorded call the mic channel can sit 30 dB under the system channel (a headset mic at
-49 LUFS next to the others at -16): reviewing it means straining or riding the volume. The
player raises quiet channels at playback time; the stored audio is never touched (it is the
source of truth and future training data, decision 0037).

This module only measures: integrated loudness (EBU R 128) per channel file. The gating of
R 128 matters here — most of a call's mic track is silence while the others talk, so a plain
RMS would call the mic far quieter than its speech is and over-raise it. The gain itself is
the player's business (static/helpers.js, playbackGain), so the policy lives in one place.

Values are kept in ``.playback/loudness.json`` next to the calls, keyed by the file's name,
mtime and size: a call compressed to FLAC or recorded again under the same name is measured
anew, everything else is measured exactly once (about a second per half hour of call).
"""

from __future__ import annotations

import json
import math
import re
import subprocess
import threading
from pathlib import Path

from parola.audio.playback import CACHE

LOUDNESS = "loudness.json"
# The summary's "I: -49.4 LUFS" line; the per-frame lines are kept off the report by
# framelog=verbose, so the summary's is the only match.
_INTEGRATED = re.compile(r"^\s*I:\s*(-?[0-9.]+|-?inf)\s+LUFS\s*$", re.MULTILINE)
_lock = threading.Lock()


def integrated(report: str) -> float | None:
    """The integrated loudness (LUFS) in ffmpeg's ebur128 output, None when there is none."""
    found = _INTEGRATED.findall(report)
    if not found or not math.isfinite(float(found[-1])):  # "-inf": no sound at all
        return None
    return float(found[-1])


def measure(path: Path) -> float | None:
    """Integrated loudness of ``path`` in LUFS, or None when it cannot be measured."""
    try:
        result = subprocess.run(
            ["ffmpeg", "-nostdin", "-hide_banner", "-i", str(path), "-map", "0:a",
             "-filter:a", "ebur128=framelog=verbose", "-f", "null", "-"],
            capture_output=True, text=True, check=False,
        )  # fmt: skip
    except OSError:  # no ffmpeg on this machine: the player plays as recorded
        return None
    if result.returncode != 0:
        return None
    return integrated(result.stderr)


def channel_loudness(folder: Path, files: dict[str, Path]) -> dict[str, float]:
    """Each channel's loudness, ``{channel: LUFS}``, measured once per file.

    A channel that cannot be measured is left out (the player then changes nothing), and the
    failure is remembered too: a broken file is not re-read on every open.
    """
    store = folder / CACHE / LOUDNESS
    with _lock:
        try:
            cache = json.loads(store.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            cache = {}
        measured = False
        out = {}
        for channel, path in files.items():
            key = _key(path)
            if key not in cache:
                cache[key] = measure(path)
                measured = True
            if isinstance(cache[key], (int, float)):
                out[channel] = cache[key]
        if measured:
            # Entries of deleted, compressed or re-recorded files go; the file stays small.
            kept = {k: v for k, v in cache.items() if _current(folder, k)}
            store.parent.mkdir(exist_ok=True)
            store.write_text(json.dumps(kept, sort_keys=True), encoding="utf-8")
    return out


def _key(path: Path) -> str:
    stat = path.stat()
    return f"{path.name}:{stat.st_mtime_ns}:{stat.st_size}"


def _current(folder: Path, key: str) -> bool:
    name = key.rsplit(":", 2)[0]
    try:
        return _key(folder / name) == key
    except OSError:
        return False
