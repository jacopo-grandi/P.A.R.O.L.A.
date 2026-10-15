"""Energy-based voice activity detection.

Whisper invents text on silence and music ("Grazie a tutti.", "Sottotitoli a cura di...") and
picks the language from the first 30 s, even when they are silent. In a two-channel call each
channel is silent while the other side talks, so only the stretches with sound are passed to
Whisper (``clip_timestamps``), and the language is detected on speech.

This is a level detector, not a speech classifier: music and noise above the threshold still
pass. It needs no extra model and is measured on the test set like any other change.
"""

from __future__ import annotations

import wave
from pathlib import Path

import numpy as np

FRAME_SECONDS = 0.03
# Frames louder than the noise floor by this much count as sound...
ABOVE_FLOOR_DB = 15.0
# ...but never below this absolute level (digital silence has no meaningful floor), and never
# above this one (a channel full of speech must not raise the bar over quiet syllables).
MIN_THRESHOLD_DB = -55.0
MAX_THRESHOLD_DB = -35.0
# Gaps shorter than this are bridged; sounds shorter than this are dropped.
MIN_SILENCE_SECONDS = 0.6
MIN_SOUND_SECONDS = 0.25
PAD_SECONDS = 0.25


def frame_levels(wav_path: Path) -> np.ndarray:
    """RMS level in dBFS of each FRAME_SECONDS frame of a 16-bit mono wav."""
    with wave.open(str(wav_path), "rb") as f:
        rate = f.getframerate()
        samples = np.frombuffer(f.readframes(f.getnframes()), dtype=np.int16)
    size = max(1, int(rate * FRAME_SECONDS))
    n = len(samples) // size
    if n == 0:
        return np.array([])
    frames = samples[: n * size].astype(np.float64).reshape(n, size) / 32768.0
    rms = np.sqrt(np.mean(frames**2, axis=1))
    return 20 * np.log10(np.maximum(rms, 1e-9))


def speech_regions(wav_path: Path) -> list[tuple[float, float]]:
    """(start, end) in seconds of the stretches with sound, padded and merged."""
    levels = frame_levels(wav_path)
    if levels.size == 0:
        return []
    # Noise floor: 10th percentile of all frames (digital silence counts as -120 dB).
    floor = float(np.percentile(np.maximum(levels, -120.0), 10))
    threshold = min(max(floor + ABOVE_FLOOR_DB, MIN_THRESHOLD_DB), MAX_THRESHOLD_DB)
    active = levels > threshold

    regions: list[list[float]] = []
    start = None
    for i, on in enumerate(np.append(active, False)):
        if on and start is None:
            start = i
        elif not on and start is not None:
            regions.append([start * FRAME_SECONDS, i * FRAME_SECONDS])
            start = None

    merged: list[list[float]] = []
    for r in regions:
        if merged and r[0] - merged[-1][1] < MIN_SILENCE_SECONDS:
            merged[-1][1] = r[1]
        else:
            merged.append(r)
    total = len(levels) * FRAME_SECONDS
    out: list[tuple[float, float]] = []
    for s, e in merged:
        if e - s < MIN_SOUND_SECONDS:
            continue
        s, e = max(0.0, s - PAD_SECONDS), min(total, e + PAD_SECONDS)
        if out and s <= out[-1][1]:
            out[-1] = (out[-1][0], e)
        else:
            out.append((s, e))
    return out


def speech_audio(wav_path: Path, regions: list[tuple[float, float]], max_seconds: float
                 ) -> np.ndarray:  # fmt: skip
    """The sound stretches of a 16 kHz mono wav, concatenated, as float32 (for Whisper)."""
    with wave.open(str(wav_path), "rb") as f:
        rate = f.getframerate()
        samples = np.frombuffer(f.readframes(f.getnframes()), dtype=np.int16)
    pieces, total = [], 0
    for start, end in regions:
        piece = samples[int(start * rate) : int(end * rate)]
        pieces.append(piece[: int(max_seconds * rate) - total])
        total += len(pieces[-1])
        if total >= max_seconds * rate:
            break
    return (np.concatenate(pieces) if pieces else samples[:0]).astype(np.float32) / 32768.0


def chunks(regions: list[tuple[float, float]], max_seconds: float = 28.0,
           max_gap: float = 2.0) -> list[tuple[float, float]]:  # fmt: skip
    """Group sound regions into chunks Whisper decodes in one window (at most ``max_seconds``).

    Regions closer than ``max_gap`` are joined with the gap; a region longer than
    ``max_seconds`` is cut into pieces."""
    out: list[tuple[float, float]] = []
    for start, end in regions:
        if out and start - out[-1][1] <= max_gap and end - out[-1][0] <= max_seconds:
            out[-1] = (out[-1][0], end)
            continue
        while end - start > max_seconds:
            out.append((start, start + max_seconds))
            start += max_seconds
        out.append((start, end))
    return out


def load_audio(wav_path: Path) -> tuple[np.ndarray, int]:
    """A 16-bit mono wav as float32 samples, with its sample rate."""
    with wave.open(str(wav_path), "rb") as f:
        rate = f.getframerate()
        samples = np.frombuffer(f.readframes(f.getnframes()), dtype=np.int16)
    return samples.astype(np.float32) / 32768.0, rate
