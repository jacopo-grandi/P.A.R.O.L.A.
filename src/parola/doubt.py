"""Doubtful passages: where a second transcription disagrees with the primary one.

Errors cluster where two systems that fail differently disagree
(results/2026-10-15-audit-crisper.md, results/2026-10-15-adjudicated-analisi.md). The primary
transcript (Whisper turbo) is aligned with a second opinion on the fidelity tokens (fillers and
repetitions ignored, decision 0010), and its words that the second opinion does not confirm are
flagged for the person to check.

``evaluate`` measures a second opinion against a reference: how many of the primary's errors
fall on flagged words (recall), how many flagged words are errors (precision) and how much has to
be checked (share of words flagged).
"""

from __future__ import annotations

from dataclasses import dataclass

from parola.eval.metrics import align
from parola.eval.normalize import Token, tokenize
from parola.schema import Transcript


def word_tokens(t: Transcript, side: str) -> list[Token]:
    """Fidelity tokens of the whole transcript; ``word_index`` is the global word index."""
    tokens: list[Token] = []
    offset = 0
    for seg in t.segments:
        if seg.overlap:
            offset += len(seg.words)
            continue
        for tok in tokenize(seg.words, seg.lang or "it", "fidelity", side):
            tokens.append(Token(tok.text, offset + tok.word_index, tok.tags, tok.is_filler))
        offset += len(seg.words)
    return tokens


def _disputed(primary: list[Token], other: list[Token]) -> set[int]:
    """Global word indices of ``primary`` not confirmed by ``other``.

    A substituted or missing primary word is disputed; where ``other`` has extra words, the
    primary words on both sides of the gap are disputed (something may be missing there)."""
    _, pairs = align(primary, other)
    out: set[int] = set()
    last_primary: int | None = None
    pending_insert = False
    for op, i, _ in pairs:
        if op in ("substitute", "delete"):
            out.add(primary[i].word_index)
        if op == "insert":
            pending_insert = True
            if last_primary is not None:
                out.add(last_primary)
            continue
        if i >= 0:
            if pending_insert:
                out.add(primary[i].word_index)
                pending_insert = False
            last_primary = primary[i].word_index
    return out


def doubtful_words(primary: Transcript, second: Transcript, window: int = 0) -> set[int]:
    """Words of ``primary`` (global indices) to check, widened by ``window`` words each side."""
    flagged = _disputed(word_tokens(primary, "hyp"), word_tokens(second, "hyp"))
    if window:
        total = sum(len(s.words) for s in primary.segments)
        flagged = {
            j for i in flagged for j in range(max(0, i - window), min(total, i + window + 1))
        }
    return flagged


def error_words(primary: Transcript, reference: Transcript) -> set[int]:
    """Words of ``primary`` (global indices) involved in a fidelity error against ``reference``:
    the word itself is wrong or extra, or a reference word is missing next to it."""
    return _disputed(word_tokens(primary, "hyp"), word_tokens(reference, "ref"))


@dataclass
class DoubtScore:
    words: int
    errors: int
    flagged: int
    caught: int

    @property
    def recall(self) -> float:
        return self.caught / self.errors if self.errors else 0.0

    @property
    def precision(self) -> float:
        return self.caught / self.flagged if self.flagged else 0.0

    @property
    def burden(self) -> float:
        return self.flagged / self.words if self.words else 0.0

    @property
    def base_rate(self) -> float:
        """Precision of flagging words at random: the share of words that are errors."""
        return self.errors / self.words if self.words else 0.0

    def __add__(self, o: DoubtScore) -> DoubtScore:
        return DoubtScore(self.words + o.words, self.errors + o.errors, self.flagged + o.flagged,
                          self.caught + o.caught)  # fmt: skip


def evaluate(primary: Transcript, flagged: set[int], reference: Transcript) -> DoubtScore:
    errors = error_words(primary, reference)
    words = sum(len(s.words) for s in primary.segments)
    return DoubtScore(words, len(errors), len(flagged), len(errors & flagged))
