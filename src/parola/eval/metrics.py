"""WER variants and disfluency metrics (docs/conventions.md §4, decision 0007).

Scoring is done per reference segment: every hypothesis word is assigned to the reference
segment that contains its midpoint (or the nearest one), so that confidence intervals can be
computed by bootstrapping over segments. Reference segments flagged ``overlap`` are
excluded, together with the hypothesis words that fall into them.
"""

from __future__ import annotations

import random
from collections import Counter
from dataclasses import dataclass, field

import jiwer

from parola.eval.normalize import METRICS, Metric, Token, tokenize
from parola.schema import Segment, Transcript, Word

# Disfluency tags measured as recall (§4). Reduplications and backchannels are not
# disfluencies; they are reported separately in the counts.
DISFLUENCY_TAGS = ("filler", "truncated", "repetition", "false_start", "edit_term")


@dataclass
class Counts:
    hits: int = 0
    substitutions: int = 0
    deletions: int = 0
    insertions: int = 0

    @property
    def ref_words(self) -> int:
        return self.hits + self.substitutions + self.deletions

    @property
    def errors(self) -> int:
        return self.substitutions + self.deletions + self.insertions

    def __add__(self, other: Counts) -> Counts:
        return Counts(
            self.hits + other.hits,
            self.substitutions + other.substitutions,
            self.deletions + other.deletions,
            self.insertions + other.insertions,
        )


@dataclass
class DisfluencyCounts:
    # Per tag: reference words carrying the tag, and how many the hypothesis kept.
    ref: Counter[str] = field(default_factory=Counter)
    kept: Counter[str] = field(default_factory=Counter)
    # Fillers in the hypothesis, and those that match no reference filler.
    hyp_fillers: int = 0
    invented_fillers: int = 0

    def __add__(self, other: DisfluencyCounts) -> DisfluencyCounts:
        return DisfluencyCounts(
            self.ref + other.ref,
            self.kept + other.kept,
            self.hyp_fillers + other.hyp_fillers,
            self.invented_fillers + other.invented_fillers,
        )


@dataclass
class SegmentScore:
    lang: str
    wer: dict[Metric, Counts]
    disfluency: DisfluencyCounts


def align(ref: list[Token], hyp: list[Token]) -> tuple[Counts, list[tuple[str, int, int]]]:
    """Levenshtein alignment. Returns counts and (op, ref_index, hyp_index) pairs."""
    if not ref:
        return Counts(insertions=len(hyp)), [("insert", -1, j) for j in range(len(hyp))]
    if not hyp:
        return Counts(deletions=len(ref)), [("delete", i, -1) for i in range(len(ref))]
    out = jiwer.process_words(" ".join(t.text for t in ref), " ".join(t.text for t in hyp))
    pairs: list[tuple[str, int, int]] = []
    for chunk in out.alignments[0]:
        rs, re_, hs, he = (chunk.ref_start_idx, chunk.ref_end_idx, chunk.hyp_start_idx,
                           chunk.hyp_end_idx)  # fmt: skip
        if chunk.type in ("equal", "substitute"):
            pairs += [(chunk.type, rs + k, hs + k) for k in range(re_ - rs)]
        elif chunk.type == "delete":
            pairs += [("delete", i, -1) for i in range(rs, re_)]
        else:
            pairs += [("insert", -1, j) for j in range(hs, he)]
    counts = Counts(out.hits, out.substitutions, out.deletions, out.insertions)
    return counts, pairs


def disfluency_counts(ref: list[Token], hyp: list[Token]) -> DisfluencyCounts:
    """Uses the verbatim tokens.

    - filler: kept if aligned to any hypothesis filler (``eh`` for ``ehm`` is fine);
    - repetition: which occurrence the alignment keeps is arbitrary, so it is counted without
      positions. For each word, the repeated occurrences kept are the hypothesis occurrences
      beyond the reference's non-repeated ones, at most the number of repeated ones;
    - truncated, false_start, edit_term: kept if aligned to an identical token.
    """
    _, pairs = align(ref, hyp)
    d = DisfluencyCounts(hyp_fillers=sum(t.is_filler for t in hyp))
    matched_hyp_fillers = 0
    for t in ref:
        for tag in DISFLUENCY_TAGS:
            if tag in t.tags:
                d.ref[tag] += 1
    for op, i, j in pairs:
        if i < 0 or j < 0:
            continue
        r, h = ref[i], hyp[j]
        for tag in DISFLUENCY_TAGS:
            if tag not in r.tags or tag == "repetition":
                continue
            if tag == "filler":
                if h.is_filler:
                    d.kept[tag] += 1
            elif op == "equal":
                d.kept[tag] += 1
        if "filler" in r.tags and h.is_filler:
            matched_hyp_fillers += 1
    d.invented_fillers = d.hyp_fillers - matched_hyp_fillers

    repeated = Counter(t.text for t in ref if "repetition" in t.tags)
    plain = Counter(t.text for t in ref if "repetition" not in t.tags)
    in_hyp = Counter(t.text for t in hyp)
    for text, n in repeated.items():
        d.kept["repetition"] += max(0, min(n, in_hyp[text] - plain[text]))
    d.kept = +d.kept  # drop zero counts
    return d


def _midpoint(w: Word, seg: Segment, k: int) -> float:
    if w.start is not None and w.end is not None:
        return (w.start + w.end) / 2
    # No word timestamps: spread the words evenly over the segment.
    step = (seg.end - seg.start) / max(len(seg.words), 1)
    return seg.start + step * (k + 0.5)


def assign_words(ref: Transcript, hyp: Transcript) -> list[list[Word]]:
    """Hypothesis words grouped by the reference segment they belong to."""
    groups: list[list[Word]] = [[] for _ in ref.segments]
    if not ref.segments:
        return groups
    for seg in hyp.segments:
        words = seg.words or [Word(text=t) for t in seg.text.split()]
        for k, w in enumerate(words):
            t = _midpoint(w, seg, k)
            best = min(
                range(len(ref.segments)),
                key=lambda i: (
                    0.0
                    if ref.segments[i].start <= t <= ref.segments[i].end
                    else min(abs(t - ref.segments[i].start), abs(t - ref.segments[i].end))
                ),
            )
            groups[best].append(w.model_copy(update={"lang": w.lang or seg.lang}))
    return groups


def score_transcript(ref: Transcript, hyp: Transcript) -> list[SegmentScore]:
    scores = []
    for seg, hyp_words in zip(ref.segments, assign_words(ref, hyp), strict=True):
        if seg.overlap:
            continue
        lang = seg.lang or "it"
        wer = {}
        for metric in METRICS:
            r = tokenize(seg.words, lang, metric, "ref")
            h = tokenize(hyp_words, lang, metric, "hyp")
            wer[metric] = align(r, h)[0]
        disf = disfluency_counts(
            tokenize(seg.words, lang, "verbatim", "ref"),
            tokenize(hyp_words, lang, "verbatim", "hyp"),
        )
        scores.append(SegmentScore(lang, wer, disf))
    return scores


def wer_of(scores: list[SegmentScore], metric: Metric) -> float | None:
    c = sum((s.wer[metric] for s in scores), Counts())
    return c.errors / c.ref_words if c.ref_words else None


def bootstrap_ci(
    scores: list[SegmentScore],
    metric: Metric,
    n: int = 1000,
    seed: int = 0,
    level: float = 0.95,
) -> tuple[float, float] | None:
    """Percentile bootstrap over segments for a WER variant."""
    if not scores:
        return None
    rng = random.Random(seed)
    values = []
    for _ in range(n):
        sample = [scores[rng.randrange(len(scores))] for _ in scores]
        v = wer_of(sample, metric)
        if v is not None:
            values.append(v)
    if not values:
        return None
    values.sort()
    lo = values[int((1 - level) / 2 * (len(values) - 1))]
    hi = values[int((1 + level) / 2 * (len(values) - 1))]
    return lo, hi
