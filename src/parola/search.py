"""Search the words of the transcripts.

Matching works on the transcript's own words, so a hit points at a segment and a word index,
and from there at the audio. Case, accents and punctuation are ignored ("perche" finds
"perché,"), an elided article does not hide the word ("impatto" finds "dell'impatto"), and a
query of several words matches them said in a row.
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass

from parola.schema import Transcript

SNIPPET_WORDS = 8  # words of context on each side of a hit
_PUNCT = re.compile(r"^[^\w]+|[^\w]+$")
_ELIDED = re.compile(r"^\w+['\u2019](\w.*)$")  # straight or typographic apostrophe


def fold(text: str) -> str:
    """Lowercase, no accents, no punctuation at the edges: the form words are compared in."""
    decomposed = unicodedata.normalize("NFKD", text)
    plain = "".join(c for c in decomposed if not unicodedata.combining(c))
    return _PUNCT.sub("", plain.casefold())


def forms(word: str) -> set[str]:
    """The forms a word can be found by: "dell'impatto" by itself and by "impatto"."""
    folded = fold(word)
    m = _ELIDED.match(folded)
    return {folded, m.group(1)} if m else {folded}


def query_tokens(query: str) -> list[str]:
    # "dell'area" is searched as said, "dell" + "area" would match other things.
    return [t for t in (fold(w) for w in query.split()) if t]


@dataclass
class Hit:
    segment: int
    word: int  # index of the first matched word in the segment
    length: int  # number of words matched
    time: float  # start of the first matched word
    channel: str | None
    before: str
    match: str
    after: str


def find(t: Transcript, query: str) -> list[Hit]:
    """Every place where the query's words are said in a row, in order."""
    tokens = query_tokens(query)
    if not tokens:
        return []
    n = len(tokens)
    hits: list[Hit] = []
    for si, seg in enumerate(t.segments):
        words = seg.words
        if not words:
            continue
        alternatives = [forms(w.text) for w in words]
        for k in range(len(words) - n + 1):
            if not all(tokens[i] in alternatives[k + i] for i in range(n)):
                continue
            start = words[k].start if words[k].start is not None else seg.start
            hits.append(Hit(
                segment=si, word=k, length=n, time=start, channel=seg.channel,
                before=" ".join(w.text for w in words[max(0, k - SNIPPET_WORDS) : k]),
                match=" ".join(w.text for w in words[k : k + n]),
                after=" ".join(w.text for w in words[k + n : k + n + SNIPPET_WORDS]),
            ))  # fmt: skip
    return hits
