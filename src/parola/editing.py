"""Corrections made by a person in the app (decision 0015).

The model's transcript is changed only through ``correct`` and ``confirm``, which record every
change in ``Transcript.edits`` with the replaced words: the original text stays traceable and
the last change can be undone. Before the first change the untouched model output is kept as
``<name>.asr.json``.
"""

from __future__ import annotations

import shutil
from datetime import UTC, datetime
from pathlib import Path

from parola.schema import Edit, Transcript, Word


class EditError(ValueError):
    pass


def doubt_runs(t: Transcript) -> list[tuple[int, int, int]]:
    """(segment, start, end) of each run of consecutive doubtful words still to review."""
    runs = []
    for si, seg in enumerate(t.segments):
        start = None
        for wi, w in enumerate([*seg.words, None]):
            if w is not None and w.doubtful:
                start = wi if start is None else start
            elif start is not None:
                runs.append((si, start, wi))
                start = None
    return runs


def _span(t: Transcript, segment: int, start: int, end: int) -> list[Word]:
    if not 0 <= segment < len(t.segments):
        raise EditError(f"no segment {segment}")
    words = t.segments[segment].words
    if not 0 <= start < end <= len(words):
        raise EditError(f"bad word range {start}:{end} in segment {segment}")
    return words[start:end]


def _new_words(text: str, old: list[Word]) -> list[Word]:
    """Words typed by a person; their times split the replaced span by length."""
    parts = text.split()
    times = [t for w in old for t in (w.start, w.end) if t is not None]
    if not parts:
        return []
    if not times:
        return [Word(text=p, checked=True) for p in parts]
    lo, hi = min(times), max(times)
    weights = [len(p) + 1 for p in parts]
    total, at, out = sum(weights), lo, []
    for p, weight in zip(parts, weights, strict=True):
        step = (hi - lo) * weight / total
        out.append(Word(text=p, start=round(at, 3), end=round(at + step, 3), checked=True))
        at += step
    return out


def _refresh(t: Transcript, segment: int) -> None:
    seg = t.segments[segment]
    seg.text = " ".join(w.text for w in seg.words)


def correct(t: Transcript, segment: int, start: int, end: int, text: str) -> Edit:
    """Replace words [start, end) of ``segment`` with ``text`` (empty text deletes them)."""
    if "\n" in text:
        raise EditError("the text must be on one line")
    old = _span(t, segment, start, end)
    if " ".join(w.text for w in old) == text.strip():
        return confirm(t, segment, start, end)
    new = _new_words(text, old)
    edit = Edit(kind="correct", segment=segment, start=start,
                before=[w.model_copy() for w in old], after_count=len(new), text=text.strip(),
                at=datetime.now(UTC))  # fmt: skip
    t.segments[segment].words[start:end] = new
    _refresh(t, segment)
    t.edits.append(edit)
    return edit


def confirm(t: Transcript, segment: int, start: int, end: int) -> Edit:
    """The person checked words [start, end) and they are right."""
    old = _span(t, segment, start, end)
    edit = Edit(kind="confirm", segment=segment, start=start,
                before=[w.model_copy() for w in old], after_count=len(old),
                text=" ".join(w.text for w in old), at=datetime.now(UTC))  # fmt: skip
    for w in old:
        w.doubtful, w.checked = False, True
    t.edits.append(edit)
    return edit


def undo(t: Transcript) -> Edit | None:
    """Revert the last edit; returns it, or None if there is nothing to undo."""
    if not t.edits:
        return None
    edit = t.edits.pop()
    words = t.segments[edit.segment].words
    words[edit.start : edit.start + edit.after_count] = [w.model_copy() for w in edit.before]
    _refresh(t, edit.segment)
    return edit


def save(t: Transcript, json_path: Path) -> None:
    """Write the edited transcript, keeping the untouched model output the first time."""
    original = json_path.with_name(json_path.name.replace(".json", ".asr.json"))
    if json_path.exists() and not original.exists():
        shutil.copy2(json_path, original)
    t.save(json_path)
