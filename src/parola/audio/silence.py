"""Long digital silence, shortened before Whisper and given back to the timestamps.

The system side of a call is exact zeros whenever no app plays anything. Whisper reads such a
window as "no speech" and skips it, together with the speech that follows in the same window:
on a test call, 6 s of speech after 23 s of zeros were lost, while the same 6 s alone were
transcribed by both Whisper and Parakeet. Microphone recordings, and so the test set, never
hold exact zeros (there is always some noise), so this changes nothing there.

Each run of exact zeros longer than ``MIN_SECONDS`` is cut down to ``KEEP_SECONDS`` (half at
each end); ``Cuts`` maps a time in the shortened audio back to the original.
"""

from __future__ import annotations

import wave
from bisect import bisect_right
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np

MIN_SECONDS = 3.0
KEEP_SECONDS = 1.0


def digital_silences(samples: np.ndarray, rate: int, min_seconds: float = MIN_SECONDS
                     ) -> list[tuple[float, float]]:  # fmt: skip
    """(start, end) in seconds of the runs of exact zeros at least ``min_seconds`` long."""
    zero = samples == 0
    if not zero.any():
        return []
    edges = np.flatnonzero(np.diff(np.concatenate(([0], zero.astype(np.int8), [0]))))
    starts, ends = edges[::2], edges[1::2]
    keep = (ends - starts) >= int(min_seconds * rate)
    return [(s / rate, e / rate) for s, e in zip(starts[keep], ends[keep], strict=True)]


@dataclass
class Cuts:
    """Where the shortened audio lost time: at shortened time ``at[i]``, ``shift[i]`` seconds
    in total had been removed."""

    at: list[float] = field(default_factory=list)
    shift: list[float] = field(default_factory=list)

    def original(self, t: float) -> float:
        i = bisect_right(self.at, t)
        return t + (self.shift[i - 1] if i else 0.0)


def condense(samples: np.ndarray, rate: int, silences: list[tuple[float, float]],
             keep: float = KEEP_SECONDS) -> tuple[np.ndarray, Cuts]:  # fmt: skip
    """The samples with each silence shortened to ``keep`` seconds, and the way back."""
    pieces, cuts, removed, pos = [], Cuts(), 0.0, 0
    half = int(keep * rate / 2)
    for start, end in silences:
        a, b = int(start * rate), int(end * rate)
        pieces.append(samples[pos : a + half])
        pos = b - half
        removed += (b - a - 2 * half) / rate
        cuts.at.append((a + half) / rate - (removed - (b - a - 2 * half) / rate))
        cuts.shift.append(removed)
    pieces.append(samples[pos:])
    return np.concatenate(pieces), cuts


def condensed_wav(wav_path: Path, out_path: Path) -> Cuts | None:
    """Write ``wav_path`` with its long digital silences shortened; None if it has none."""
    with wave.open(str(wav_path), "rb") as f:
        rate, width, channels = f.getframerate(), f.getsampwidth(), f.getnchannels()
        if width != 2 or channels != 1:
            return None
        samples = np.frombuffer(f.readframes(f.getnframes()), dtype=np.int16)
    silences = digital_silences(samples, rate)
    if not silences:
        return None
    short, cuts = condense(samples, rate, silences)
    with wave.open(str(out_path), "wb") as f:
        f.setnchannels(1)
        f.setsampwidth(2)
        f.setframerate(rate)
        f.writeframes(short.astype(np.int16).tobytes())
    return cuts
