"""Closed vocabularies from docs/conventions.md, shared by the linter and the annotation format."""

import re

LANGS = ("it", "en")

# §2.2: closed inventory of filled pauses, per language.
FILLERS = {
    "it": frozenset({"eh", "ehm", "mh", "ah", "oh"}),
    "en": frozenset({"uh", "um", "hmm"}),
}
# Forms tagged `filler` automatically by the annotation importer. `ah` and `oh` are excluded
# because they are often meaningful interjections ("ah, ho capito").
AUTO_FILLERS = frozenset({"eh", "ehm", "mh", "uh", "um", "hmm"})

# §2.11 and §2.12.
NONVERBAL = frozenset({"[risata]", "[tosse]", "[rumore]", "[silenzio]"})
INAUDIBLE = "[inaudibile]"

# Punctuation that may be attached to a word (§2.6). Apostrophes and hyphens are part of words.
PUNCTUATION = ".,;:!?…"

# §2.9 and §2.7: spellings that must not appear in a reference, with the expected form.
FORBIDDEN_SPELLINGS: list[tuple[re.Pattern[str], str]] = [
    (re.compile(r"\bva\s+be'(?=\s|$|[.,;:!?…])", re.IGNORECASE), "vabbè"),
    (re.compile(r"\bvabbe'(?=\s|$|[.,;:!?…])", re.IGNORECASE), "vabbè"),
    (re.compile(r"\bvabbé\b", re.IGNORECASE), "vabbè"),
    (re.compile(r"\bbe'(?=\s|$|[.,;:!?…])", re.IGNORECASE), "beh"),
    (re.compile(r"\bperchè\b", re.IGNORECASE), "perché"),
    (re.compile(r"\bpoichè\b", re.IGNORECASE), "poiché"),
    (re.compile(r"\bokay\b", re.IGNORECASE), "ok"),
    (re.compile(r"\bo\.k\.", re.IGNORECASE), "ok"),
    (re.compile(r"\bOK\b"), "ok"),
]


def core(text: str) -> str:
    """Word text without attached punctuation, lowercased."""
    return text.strip(PUNCTUATION).lower()


def split_punctuation(text: str) -> tuple[str, str]:
    """Split trailing punctuation: ``"lunedì,"`` -> ``("lunedì", ",")``."""
    stripped = text.rstrip(PUNCTUATION)
    if not stripped:
        return text, ""
    return stripped, text[len(stripped) :]
