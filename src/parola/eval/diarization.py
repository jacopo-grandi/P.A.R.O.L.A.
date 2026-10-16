"""Diarization error rate (DER): how much speech time is given to the wrong speaker.

The standard NIST definition, computed on 10 ms frames, with no forgiveness collar and
overlapping speech included (as pyannote reports it). In each frame, with R the reference
speakers talking and H the hypothesis ones:

- missed speech: max(0, |R| - |H|)
- false alarm: max(0, |H| - |R|)
- confusion: min(|R|, |H|) minus the speakers that match under the mapping

The mapping pairs hypothesis and reference speakers one to one so that they overlap the most
(Hungarian algorithm). DER = (missed + false alarm + confusion) / sum of |R| over all frames.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import numpy as np

FRAME = 0.01  # seconds

Turn = tuple[float, float, str]  # start, end, speaker


@dataclass
class DER:
    missed: float  # seconds
    false_alarm: float
    confusion: float
    total: float  # reference speech, seconds

    @property
    def rate(self) -> float:
        return (self.missed + self.false_alarm + self.confusion) / self.total if self.total else 0.0


def read_rttm(path: Path) -> list[Turn]:
    """``SPEAKER <file> <chan> <start> <duration> <NA> <NA> <speaker> <NA> <NA>`` lines."""
    turns = []
    for line in path.read_text().splitlines():
        parts = line.split()
        if parts and parts[0] == "SPEAKER":
            start, dur = float(parts[3]), float(parts[4])
            turns.append((start, start + dur, parts[7]))
    return turns


def _grid(turns: list[Turn], speakers: list[str], frames: int) -> np.ndarray:
    grid = np.zeros((len(speakers), frames), dtype=bool)
    index = {s: i for i, s in enumerate(speakers)}
    for start, end, speaker in turns:
        a, b = round(start / FRAME), round(end / FRAME)
        grid[index[speaker], max(0, a) : max(0, min(frames, b))] = True
    return grid


def der(reference: list[Turn], hypothesis: list[Turn]) -> DER:
    from scipy.optimize import linear_sum_assignment

    end = max([e for _, e, _ in reference + hypothesis], default=0.0)
    frames = round(end / FRAME) + 1
    ref_spk = sorted({s for _, _, s in reference})
    hyp_spk = sorted({s for _, _, s in hypothesis})
    ref = _grid(reference, ref_spk, frames)
    hyp = _grid(hypothesis, hyp_spk, frames)
    n_ref, n_hyp = ref.sum(axis=0), hyp.sum(axis=0)
    # Frames where both talk, per (reference, hypothesis) pair: the mapping maximises it.
    overlap = ref.astype(np.int64) @ hyp.T.astype(np.int64)
    matched = 0
    if overlap.size:
        rows, cols = linear_sum_assignment(-overlap)
        mapped = np.zeros_like(ref)
        for r, c in zip(rows, cols, strict=True):
            mapped[r] = ref[r] & hyp[c]
        matched = mapped.sum(axis=0)
    missed = np.maximum(0, n_ref - n_hyp).sum()
    false_alarm = np.maximum(0, n_hyp - n_ref).sum()
    confusion = (np.minimum(n_ref, n_hyp) - matched).sum()
    return DER(missed * FRAME, false_alarm * FRAME, confusion * FRAME, n_ref.sum() * FRAME)
