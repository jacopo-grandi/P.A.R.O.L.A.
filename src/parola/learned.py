"""A personal glossary learned from the person's corrections: it suggests, it never corrects.

Every correction made in the app is logged in the transcript with the words the model had
written (``Edit.before``) and what the person typed (``Edit.text``). The glossary is read from
those logs each time, so there is nothing extra to keep in sync, an undone correction is
forgotten with it, and it lives only where the calls live (``data/private/``, never in git):
every install starts empty and learns from its own user. Only corrections that are terms are
kept: names, acronyms, words with digits or hyphens, or words rare in the language the
sentence was said in ("Orto-Lab", "QX", "mulching", and "baking soda" in an Italian call); fixing
"a" into "ha" is grammar, not a term.

A term is suggested once it was corrected ``MIN_CORRECTIONS`` times. When the person opens a
doubtful word, the terms it resembles are offered: first those whose misheard form it is
exactly ("orto lap" was corrected to "Orto-Lab" before), then those whose spelling is close.
The person accepts one or not (decision 0025).
"""

from __future__ import annotations

import re
from collections import Counter
from dataclasses import dataclass, field
from difflib import SequenceMatcher
from functools import cache
from pathlib import Path

from wordfreq import zipf_frequency

from parola.schema import Transcript
from parola.search import fold

MAX_TERM_WORDS = 4
# Corrections before a term is suggested: one could be a slip, two are a habit.
MIN_CORRECTIONS = 2
# Rarer than this in the sentence's language (about 3 per million words): a term to remember.
RARE_ZIPF = 3.5
# Spellings this close (difflib ratio on the letters) are offered as suggestions.
SIMILAR = 0.75
# Punctuation that may cling to a word's edges without changing its spelling.
EDGE = '.,;:!?…"“”«»()'


@dataclass
class Term:
    text: str  # as the person wrote it: "Orto-Lab"
    heard: Counter = field(default_factory=Counter)  # what the model had written, folded
    count: int = 0  # corrections that taught it


@dataclass
class Suggestion:
    text: str  # the whole replacement for the span: "il Orto-Lab"
    term: str
    count: int
    exact: bool  # the span is a form already corrected to this term


@cache
def _zipf(word: str, lang: str) -> float:
    return zipf_frequency(word, lang if lang in ("it", "en") else "it")


def is_term(text: str, lang: str = "it") -> bool:
    """A name, an acronym, a word with digits or a hyphen, or a word rare in ``lang``: English
    terms in Italian speech ("baking soda") are what the model gets wrong."""
    words = [w.strip(EDGE) for w in text.split()]
    words = [w for w in words if w]
    if not words or len(words) > MAX_TERM_WORDS:
        return False
    for w in words:
        if len(w) >= 2 and (w.isupper() or any(c.isupper() for c in w[1:])):
            return True  # QX, ABC, CamelCase
        if any(c.isdigit() for c in w) or "-" in w:
            return True
        if _zipf(fold(w), lang) < RARE_ZIPF:
            return True
    return False


def _letters(text: str) -> str:
    return re.sub(r"[\W_]+", "", fold(text))


def _as_written(span: str, term: str) -> bool:
    """The span already shows the term's exact spelling (edge punctuation aside). Compared as
    displayed, not by letters: "parola" is not "P.A.R.O.L.A.", the correction IS the case and
    the dots."""
    return [w.strip(EDGE) for w in span.split()] == [w.strip(EDGE) for w in term.split()]


def learn(transcripts: list[Transcript]) -> dict[str, Term]:
    """Terms by their folded form, from every correction in ``transcripts``."""
    terms: dict[str, Term] = {}
    for t in transcripts:
        for edit in t.edits:
            if edit.kind != "correct" or not edit.text:
                continue
            lang = t.segments[edit.segment].lang if edit.segment < len(t.segments) else None
            if not is_term(edit.text, lang or "it"):
                continue
            # Case- or punctuation-only corrections teach too: a brand's exact spelling
            # ("zentrix" -> "Zentrix") is precisely what no model knows.
            heard = " ".join(fold(w.text) for w in edit.before)
            key = _letters(edit.text)
            term = terms.setdefault(key, Term(edit.text))
            term.text = edit.text  # the latest spelling wins
            term.heard[heard] += 1
            term.count += 1
    return terms


def suggest(text: str, terms: dict[str, Term], limit: int = 3) -> list[Suggestion]:
    """Terms the words of ``text`` may be, as whole replacements for ``text``."""
    words = text.split()
    found: dict[str, tuple[float, Suggestion]] = {}
    for i in range(len(words)):
        for j in range(i + 1, min(len(words), i + MAX_TERM_WORDS) + 1):
            span = " ".join(words[i:j])
            heard, letters = " ".join(fold(w) for w in words[i:j]), _letters(span)
            if not letters:
                continue
            for key, term in terms.items():
                if term.count < MIN_CORRECTIONS or _as_written(span, term.text):
                    continue  # not learned yet, or already written that way
                exact = term.heard[heard] > 0
                ratio = max([SequenceMatcher(None, letters, key).ratio()]
                            + [SequenceMatcher(None, letters, _letters(h)).ratio()
                               for h in term.heard])  # fmt: skip
                if not exact and ratio < SIMILAR:
                    continue
                replacement = " ".join([*words[:i], term.text, *words[j:]])
                rank = (2.0 if exact else ratio) + term.count / 100
                if key not in found or rank > found[key][0]:
                    found[key] = (rank, Suggestion(replacement, term.text, term.count, exact))
    ranked = sorted(found.values(), key=lambda x: -x[0])
    return [s for _, s in ranked[:limit]]


def load_terms(folder: Path) -> dict[str, Term]:
    """Terms learned from every call in ``folder``."""
    transcripts = [
        Transcript.load(p)
        for p in sorted(folder.glob("*.json"))
        if not p.name.endswith((".capture.json", ".asr.json"))
    ]
    return learn(transcripts)
