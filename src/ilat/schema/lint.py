"""Check a reference transcript against docs/conventions.md.

The pydantic model only guarantees structure. These checks enforce the transcription rules
and are meant for hand-made references (``metadata.kind == "reference"``).
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Literal

from ilat.schema.transcript import Segment, Transcript, Word
from ilat.schema.vocab import (
    FILLERS,
    FORBIDDEN_SPELLINGS,
    INAUDIBLE,
    NONVERBAL,
    core,
)

MAX_SEGMENT_SECONDS = 30.0
# Tolerance for word timestamps slightly outside their segment.
TIME_TOLERANCE = 0.1

_DIGIT = re.compile(r"\d")


@dataclass(frozen=True)
class Issue:
    severity: Literal["error", "warning"]
    message: str
    segment: int | None = None
    word: int | None = None

    def __str__(self) -> str:
        where = ""
        if self.segment is not None:
            where = f"segment {self.segment}"
            if self.word is not None:
                where += f", word {self.word}"
            where = f" [{where}]"
        return f"{self.severity}{where}: {self.message}"


def has_errors(issues: list[Issue]) -> bool:
    return any(i.severity == "error" for i in issues)


def lint(transcript: Transcript) -> list[Issue]:
    issues: list[Issue] = []
    for i, segment in enumerate(transcript.segments):
        issues.extend(_lint_segment(i, segment))
    return issues


def _lint_segment(i: int, seg: Segment) -> list[Issue]:
    issues: list[Issue] = []

    def err(msg: str, word: int | None = None) -> None:
        issues.append(Issue("error", msg, i, word))

    def warn(msg: str, word: int | None = None) -> None:
        issues.append(Issue("warning", msg, i, word))

    if seg.lang is None:
        err("segment has no lang")
    if not seg.words:
        err("segment has no words")
    if seg.end - seg.start > MAX_SEGMENT_SECONDS:
        err(f"segment lasts {seg.end - seg.start:.1f} s (max {MAX_SEGMENT_SECONDS:.0f} s)")

    joined = " ".join(w.text for w in seg.words)
    if seg.words and seg.text != joined:
        err(f"segment text does not match its words: {seg.text!r} != {joined!r}")

    for pattern, expected in FORBIDDEN_SPELLINGS:
        for m in pattern.finditer(seg.text):
            err(f"spelling {m.group(0)!r} is not allowed, use {expected!r}")
    if _DIGIT.search(seg.text):
        warn("digits in text: numbers are written in words (ok only inside names, e.g. GPT-4)")

    last_start = None
    for j, w in enumerate(seg.words):
        issues.extend(Issue(s, m, i, j) for s, m in _lint_word(w, seg))
        if w.start is not None and w.end is not None:
            if w.start < seg.start - TIME_TOLERANCE or w.end > seg.end + TIME_TOLERANCE:
                err("word timestamps fall outside the segment", j)
            if last_start is not None and w.start < last_start:
                err("word timestamps are not in order", j)
            last_start = w.start
        if ("repetition" in w.tags or "reduplication" in w.tags) and core(w.text) not in {
            core(x.text) for x in seg.words[j + 1 :]
        }:
            err("repeated word has no later occurrence in the segment", j)
    return issues


def _lint_word(w: Word, seg: Segment) -> list[tuple[Literal["error", "warning"], str]]:
    out: list[tuple[Literal["error", "warning"], str]] = []
    tags = set(w.tags)
    text = w.text
    is_event = text in NONVERBAL or text == INAUDIBLE

    # Bracketed tokens.
    if (text.startswith("[") or text.endswith("]")) and not is_event:
        out.append(("error", f"unknown bracketed token {text!r}"))
    if text in NONVERBAL:
        if tags != {"nonverbal"}:
            out.append(("error", f"{text} must have exactly the tag 'nonverbal'"))
    elif "nonverbal" in tags:
        out.append(("error", f"'nonverbal' is only for {sorted(NONVERBAL)}"))
    if text == INAUDIBLE and tags:
        out.append(("error", f"{INAUDIBLE} takes no tags"))
    if is_event and w.lang is not None:
        out.append(("error", f"{text} must not have a lang"))
    if not is_event and w.lang is None:
        out.append(("error", "word has no lang"))

    # Truncated words: trailing hyphen <=> tag.
    truncated_form = core(text).endswith("-")
    if truncated_form and "truncated" not in tags:
        out.append(("error", "word ending with '-' must have the tag 'truncated'"))
    if "truncated" in tags and not truncated_form:
        out.append(("error", "truncated word must end with '-'"))

    # Fillers come from the closed inventory of their language.
    if "filler" in tags:
        lang = w.lang or seg.lang
        allowed = FILLERS.get(lang or "", frozenset())
        if core(text) not in allowed:
            out.append(
                ("error", f"{text!r} is not in the {lang} filler inventory {sorted(allowed)}")
            )

    if "uncertain" in tags and any(c in text for c in "()"):
        out.append(("error", "uncertain words are stored without parentheses"))
    if any(c in text for c in "(){}|"):
        out.append(("error", f"markup characters left in word {text!r}"))
    return out
