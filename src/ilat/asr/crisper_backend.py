"""CrisperWhisper 2.0 backend via the crisperwhisper package (optional group ``baselines``).

Weights are under a non-commercial research license: use only for evaluation.
"""

from __future__ import annotations

from functools import cache
from pathlib import Path
from typing import Any

from ilat.asr.base import ASRResult
from ilat.schema import Segment, Word

CRISPER_MODEL = "nyralabs/CrisperWhisper2.0_turbo"
# CPU + float32: on MPS, word timestamps fail with transformers 5 (EncoderDecoderCache has
# no "layers"), and float16 on CPU is very slow.
DEVICE, COMPUTE_TYPE = "cpu", "float32"
# Segmentation of the word stream, as in docs/conventions.md §2.1.
MAX_GAP_SECONDS = 1.0
MAX_SEGMENT_SECONDS = 30.0

# CrisperWhisper writes fillers in brackets ("[UM]"); they are words, not events.
_BRACKET_FILLERS = {"um", "uh", "uhm", "umm", "er", "erm", "eh", "ehm", "hmm", "hm", "mm",
                    "mmm", "mh", "ah", "oh"}  # fmt: skip


def normalize_word(text: str) -> str:
    """``"[UM]"`` -> ``"um"``; other bracketed events (``"[laughter]"``) are kept as they are."""
    core = text.strip()
    if core.startswith("[") and "]" in core:
        inner, _, rest = core[1:].partition("]")
        if inner.lower() in _BRACKET_FILLERS:
            return inner.lower() + rest
    return core


def words_to_segments(raw_words: list[Any]) -> list[Segment]:
    segments: list[Segment] = []
    current: list[Word] = []

    def flush() -> None:
        if current:
            segments.append(
                Segment(
                    start=current[0].start,
                    end=max(current[-1].end, current[0].start),
                    text=" ".join(w.text for w in current),
                    words=list(current),
                )
            )
            current.clear()

    prev_end = 0.0
    for w in raw_words:
        text = normalize_word(w.word)
        if not text:
            continue
        # Keep times monotonic so that segments come out sorted.
        start = max(float(w.start), prev_end)
        end = max(float(w.end), start)
        if current and (
            start - current[-1].end > MAX_GAP_SECONDS
            or end - current[0].start > MAX_SEGMENT_SECONDS
        ):
            flush()
        current.append(Word(text=text, start=start, end=end))
        prev_end = end
    flush()
    return segments


@cache
def _load(model: str) -> Any:
    from crisperwhisper import CrisperWhisperModel

    return CrisperWhisperModel(model, device=DEVICE, compute_type=COMPUTE_TYPE)


class CrisperBackend:
    name = "crisperwhisper"

    def __init__(self, model: str = CRISPER_MODEL, seed: int = 0) -> None:
        self.model = model
        self.seed = seed

    def transcribe(self, wav_path: Path, language: str | None = None) -> ASRResult:
        import torch

        # Temperature fallback samples at random: seed it, as for mlx-whisper.
        torch.manual_seed(self.seed)
        # The package has no language detection: "en" is its own default.
        lang = language or "en"
        result = _load(self.model).transcribe(
            str(wav_path), language=lang, mode="verbatim", word_timestamps=True
        )
        segments = words_to_segments(result.words or [])
        for s in segments:
            s.lang = lang if lang in ("it", "en") else None
        return ASRResult(segments=segments, language=lang)
