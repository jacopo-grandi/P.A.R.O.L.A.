"""Parakeet TDT v3 backend via parakeet-mlx (optional dependency group ``baselines``)."""

from __future__ import annotations

from functools import cache
from pathlib import Path
from typing import Any

from parola.asr.base import ASRResult
from parola.schema import Segment, Word

PARAKEET_MODEL = "mlx-community/parakeet-tdt-0.6b-v3"
# Same defaults as the parakeet-mlx CLI: long files are decoded in overlapping chunks.
CHUNK_SECONDS = 120.0
OVERLAP_SECONDS = 15.0


def tokens_to_words(tokens: list[Any]) -> list[Word]:
    """Join sub-word tokens into words.

    A token starting with a space opens a new word; the others (``"ora"`` after ``" all"``,
    punctuation) continue the previous one.
    """
    words: list[Word] = []
    for t in tokens:
        text = t.text
        if not text.strip():
            continue
        prob = getattr(t, "confidence", None)
        if words and not text[:1].isspace():
            prev = words[-1]
            probs = [p for p in (prev.probability, prob) if p is not None]
            words[-1] = Word(
                text=prev.text + text.strip(),
                start=prev.start,
                end=max(prev.end or t.end, t.end),
                probability=min(probs) if probs else None,
            )
        else:
            words.append(
                Word(text=text.strip(), start=t.start, end=max(t.end, t.start), probability=prob)
            )
    return words


def convert_result(result: Any) -> ASRResult:
    segments = []
    for sentence in result.sentences:
        words = tokens_to_words(sentence.tokens)
        if not words:
            continue
        start = words[0].start or 0.0
        if segments and start < segments[-1].start:
            start = segments[-1].start
        segments.append(
            Segment(
                start=start,
                end=max(words[-1].end or start, start),
                text=" ".join(w.text for w in words),
                words=words,
            )
        )
    # Parakeet detects the language internally but does not report it.
    return ASRResult(segments=segments, language=None)


@cache
def _load(model: str) -> Any:
    from parakeet_mlx import from_pretrained

    return from_pretrained(model)


class ParakeetBackend:
    name = "parakeet-mlx"

    def __init__(self, model: str = PARAKEET_MODEL) -> None:
        self.model = model

    def transcribe(self, wav_path: Path, language: str | None = None) -> ASRResult:
        # Greedy TDT decoding is deterministic; the language cannot be forced.
        result = _load(self.model).transcribe(
            str(wav_path), chunk_duration=CHUNK_SECONDS, overlap_duration=OVERLAP_SECONDS
        )
        return convert_result(result)
