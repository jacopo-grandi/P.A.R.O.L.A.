"""Personal glossary: terms Whisper should spell right (English words in Italian speech, product
and company names, acronyms).

One term per line in a text file; blank lines and lines starting with ``#`` are ignored. The
default file is ``data/private/glossary.txt``, ignored by git because it can contain names of
clients and companies. The terms are given to Whisper as a prompt on every 30-second window
(``parola.asr.mlx_whisper_backend.carried_prompt``), not only on the first one.
"""

from __future__ import annotations

from pathlib import Path

DEFAULT_PATH = Path("data/private/glossary.txt")
# Whisper's prompt holds at most 223 tokens (n_text_ctx // 2 - 1), shared with the previous text:
# keep the glossary well below, so that some context of the conversation remains.
MAX_CHARS = 400


def load(path: Path = DEFAULT_PATH) -> list[str]:
    if not path.exists():
        return []
    terms = []
    for line in path.read_text(encoding="utf-8").splitlines():
        term = line.strip()
        if term and not term.startswith("#") and term not in terms:
            terms.append(term)
    return terms


def prompt_text(terms: list[str]) -> str | None:
    """The terms as a prompt, cut at MAX_CHARS on a term boundary."""
    out: list[str] = []
    length = 0
    for term in terms:
        if length + len(term) + 2 > MAX_CHARS:
            break
        out.append(term)
        length += len(term) + 2
    return ", ".join(out) + "." if out else None
