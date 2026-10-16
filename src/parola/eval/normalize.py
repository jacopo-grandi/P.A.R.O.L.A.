"""Turn transcript words into comparable tokens for each metric (docs/conventions.md §4).

The same rules apply to reference and hypothesis, except that tags are known only on the
reference: on the hypothesis, fillers and truncations are recognised from their form.

- ``fidelity`` (primary metric, decision 0010): were the words said, as said? Drop fillers,
  truncations, repetitions, false starts and edit terms; collapse immediate repeats
  (untagged repetitions in silver references, and all of them in the hypothesis). Rewrites,
  paraphrases and grammar "corrections" still count.
- ``literal`` (decision 0007): drop only fillers; repetitions and truncations count.
- ``verbatim``: keep fillers too, mapped to the canonical inventory form.

Shared normalisation: lowercase, strip punctuation, split elisions after the apostrophe
(``l'info`` -> ``l'`` ``info``), write numbers in words, drop non-verbal events and
``[inaudibile]``.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Literal

from num2words import num2words

from parola.schema import Word
from parola.schema.vocab import INAUDIBLE, NONVERBAL

Metric = Literal["fidelity", "literal", "verbatim"]
METRICS: tuple[Metric, ...] = ("fidelity", "literal", "verbatim")

# Spelling variants of filled pauses -> canonical form of docs/conventions.md §2.2.
FILLER_FORMS = {
    "it": {
        **dict.fromkeys(["eh", "ehh", "eeh", "eee"], "eh"),
        **dict.fromkeys(["ehm", "ehmm", "emm", "uhm", "umh", "em"], "ehm"),
        **dict.fromkeys(["mh", "mmh", "mm", "mmm", "hmm", "hm"], "mh"),
        # Whisper writes English-style forms in Italian speech too.
        **dict.fromkeys(["uh", "uhh"], "eh"),
        **dict.fromkeys(["um", "umm"], "ehm"),
    },
    "en": {
        **dict.fromkeys(["uh", "uhh", "er", "err", "eh"], "uh"),
        **dict.fromkeys(["um", "umm", "uhm", "erm", "em", "ehm"], "um"),
        **dict.fromkeys(["hmm", "hm", "mm", "mmm", "mh"], "hmm"),
    },
}
# Tags removed from the reference by the fidelity metric (§4).
FIDELITY_DROPPED_TAGS = {"filler", "truncated", "repetition", "reduplication", "false_start",
                        "edit_term"}  # fmt: skip

# Spelling variants that docs/conventions.md §2.9 treats as the same word.
SPELLINGS = {"okay": "ok", "o.k": "ok", "perchè": "perché", "poichè": "poiché",
             "vabbe'": "vabbè", "vabbé": "vabbè"}  # fmt: skip

_STRIP = '.,;:!?…"“”«»()[]{}'
_ELISION = re.compile(r"(?<=\w')(?=\w)")
_THOUSANDS_SEP = {"it": ".", "en": ","}
_PLAIN_NUMBER = re.compile(r"^(\d+)(?:[.,](\d+))?$")
_PERCENT = {"it": "per cento", "en": "percent"}


@dataclass
class Token:
    text: str
    # Index of the source word in the segment (for disfluency metrics), or None.
    word_index: int | None = None
    tags: frozenset[str] = field(default_factory=frozenset)
    is_filler: bool = False


def is_event(text: str) -> bool:
    """Non-verbal events and inaudible markers, including the hypothesis' own (``[Music]``)."""
    t = text.strip(".,;:!?…")
    return (
        t in NONVERBAL
        or t == INAUDIBLE
        or (t.startswith("[") and t.endswith("]"))
        or (t.startswith("(") and t.endswith(")"))
    )


def number_to_words(token: str, lang: str) -> list[str]:
    """``"80%"`` -> ``["ottanta", "per", "cento"]``; non-numbers are returned unchanged.

    Thousands separators follow the language (``3.000`` in Italian, ``3,000`` in English);
    any other ``.`` or ``,`` between digits is a decimal separator (``9.3``, ``2,5``).
    """
    body, percent = (token[:-1], True) if token.endswith("%") else (token, False)
    sep = re.escape(_THOUSANDS_SEP.get(lang, ","))
    if re.fullmatch(rf"\d{{1,3}}(?:{sep}\d{{3}})+", body):
        value: int | float = int(re.sub(sep, "", body))
    elif m := _PLAIN_NUMBER.match(body):
        value = float(f"{m.group(1)}.{m.group(2)}") if m.group(2) else int(m.group(1))
    else:
        return [token]
    words = num2words(value, lang=lang).split()
    if percent:
        words += _PERCENT[lang].split()
    return words


def split_word(text: str, lang: str) -> list[str]:
    """Normalise one word into one or more tokens."""
    t = text.replace("\u2019", "'").lower().strip(_STRIP)
    if not t:
        return []
    t = SPELLINGS.get(t, t)
    out = []
    for part in _ELISION.split(t):
        part = part.strip(_STRIP)
        if part:
            out.extend(number_to_words(part, lang))
    return out


def canonical_filler(token: str, lang: str) -> str | None:
    return FILLER_FORMS.get(lang, {}).get(token)


def tokenize(
    words: list[Word], lang: str, metric: Metric, side: Literal["ref", "hyp"]
) -> list[Token]:
    """Tokens of one segment for ``metric``. ``lang`` is the segment language."""
    tokens: list[Token] = []
    for i, w in enumerate(words):
        if is_event(w.text):
            continue
        word_lang = w.lang or lang
        tags = frozenset(w.tags)
        parts = split_word(w.text, word_lang)
        if not parts:
            continue
        canonical = canonical_filler(parts[0], word_lang) if len(parts) == 1 else None
        # As in the annotation importer, "eh?" (interrogative) is not a filler.
        filler = "filler" in tags if side == "ref" else canonical is not None and "?" not in w.text
        truncated = "truncated" in tags if side == "ref" else parts[-1].endswith("-")
        if filler and metric in ("fidelity", "literal"):
            continue
        if metric == "fidelity" and (truncated or tags & FIDELITY_DROPPED_TAGS):
            continue
        if filler and canonical:
            parts = [canonical]
        tokens.extend(Token(p, i, tags, filler) for p in parts)
    if metric == "fidelity":
        tokens = [t for k, t in enumerate(tokens) if k == 0 or t.text != tokens[k - 1].text]
    return tokens
