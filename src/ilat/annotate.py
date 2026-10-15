"""Plain-text annotation format for writing references by hand.

A draft is generated from an ASR transcript, corrected in a text editor, then imported back
into the JSON schema. Example::

    # ilat-annotation 1
    # status: reviewed
    # audio_file: call.m4a
    # duration: 362.304

    [00:00:00.000 - 00:00:04.200] lang=it channel=system speaker=A
    Ehm, ci vediamo lunedì,|fs no|ed martedì per la call|en.

    [00:00:04.300 - 00:00:05.000] lang=it bc
    Sì, sì.

The draft starts with ``# status: draft``: change it to ``reviewed`` once the whole file has
been checked against the audio, otherwise it cannot be imported.

Segment header: ``[start - end]`` followed by ``lang=it|en``, optional ``channel=``,
``speaker=`` and the flags ``overlap`` (§2.14) and ``bc`` (whole segment is a backchannel).

Word codes, appended with ``|`` (several allowed, e.g. ``call|en|rep``):
``f`` filler, ``rep`` repetition, ``red`` reduplication, ``fs`` false start, ``ed`` edit term,
``bc`` backchannel, ``it``/``en`` language, ``-f`` cancel the automatic filler tag.
``{several words}|fs`` applies the codes to every word in the braces.

Applied automatically: ``truncated`` for words ending in ``-``; ``nonverbal`` for
``[risata] [tosse] [rumore] [silenzio]``; ``uncertain`` for ``(word?)`` or ``(two words?)``;
``filler`` for eh, ehm, mh, uh, um, hmm (not when followed by ``?`` or in a backchannel).
"""

from __future__ import annotations

import re
from datetime import UTC, datetime

from ilat import __version__
from ilat.schema import Metadata, Segment, Transcript, Word, WordTag, format_timestamp
from ilat.schema.render import parse_timestamp
from ilat.schema.vocab import (
    AUTO_FILLERS,
    INAUDIBLE,
    LANGS,
    NONVERBAL,
    PUNCTUATION,
    core,
    split_punctuation,
)

FORMAT_VERSION = "1"

CODES: dict[str, WordTag] = {
    "f": "filler",
    "rep": "repetition",
    "red": "reduplication",
    "fs": "false_start",
    "ed": "edit_term",
    "bc": "backchannel",
}
TAG_CODES = {tag: code for code, tag in CODES.items()}
NO_AUTO_FILLER = "-f"
DRAFT, REVIEWED = "draft", "reviewed"
_META_KEYS = {"status", "audio_file", "duration", "annotator"}

_HEADER = re.compile(r"^\[(\S+) - (\S+)\](.*)$")
_PUNCT = re.escape(PUNCTUATION)
_UNIT = re.compile(
    r"(?:\{(?P<brace>[^{}]+)\}|\((?P<paren>[^()]+?)\?\)|(?P<word>[^\s|{}()]+))"
    rf"(?P<codes>(?:\|-?[a-z]+)*)(?P<punct>[{_PUNCT}]*)(?=\s|$)"
)

HELP = "Segment header:" + __doc__.split("Segment header:", 1)[1].rstrip()


class AnnotationError(ValueError):
    def __init__(self, line: int, message: str) -> None:
        super().__init__(f"line {line}: {message}")
        self.line = line


# --------------------------------------------------------------------------- export


def to_annotation(transcript: Transcript, draft: bool = False) -> str:
    """Render a transcript in the annotation format.

    ``draft=True`` writes plain words without codes: used to turn an ASR output into a
    starting point for a hand-made reference.
    """
    m = transcript.metadata
    lines = [
        f"# ilat-annotation {FORMAT_VERSION}",
        f"# status: {DRAFT if draft else REVIEWED}",
        f"# audio_file: {m.audio_file}",
    ]
    lines.append(f"# duration: {m.duration:.3f}")
    if m.annotator:
        lines.append(f"# annotator: {m.annotator}")
    lines += ["#"] + [f"# {h}" if h else "#" for h in HELP.splitlines()] + [""]

    for seg in transcript.segments:
        lines.append(_header(seg, draft))
        if draft or not seg.words:
            lines.append(" ".join(w.text for w in seg.words) or seg.text)
        else:
            all_bc = all("backchannel" in w.tags for w in seg.words)
            lines.append(" ".join(_render_word(w, seg, all_bc) for w in seg.words))
        lines.append("")
    return "\n".join(lines)


def _header(seg: Segment, draft: bool) -> str:
    parts = [f"[{format_timestamp(seg.start)} - {format_timestamp(seg.end)}]"]
    if seg.lang:
        parts.append(f"lang={seg.lang}")
    if seg.channel:
        parts.append(f"channel={seg.channel}")
    if seg.speaker:
        parts.append(f"speaker={seg.speaker}")
    if seg.overlap:
        parts.append("overlap")
    if not draft and seg.words and all("backchannel" in w.tags for w in seg.words):
        parts.append("bc")
    return " ".join(parts)


def _render_word(w: Word, seg: Segment, segment_bc: bool) -> str:
    codes = [TAG_CODES[t] for t in w.tags if t in TAG_CODES and t != "filler"]
    if segment_bc and "bc" in codes:
        codes.remove("bc")
    auto = _auto_filler(w.text, "uncertain" in w.tags, "backchannel" in w.tags)
    if "filler" in w.tags and not auto:
        codes.append("f")
    elif auto and "filler" not in w.tags:
        codes.append(NO_AUTO_FILLER)
    if w.lang and w.lang != seg.lang:
        codes.append(w.lang)
    suffix = "".join(f"|{c}" for c in codes)
    if "uncertain" in w.tags:
        body, punct = split_punctuation(w.text)
        return f"({body}?){suffix}{punct}"
    return f"{w.text}{suffix}"


# --------------------------------------------------------------------------- import


def from_annotation(text: str) -> Transcript:
    """Parse the annotation format into a reference transcript."""
    meta: dict[str, str] = {}
    segments: list[Segment] = []
    current: dict | None = None

    def flush() -> None:
        if current is None:
            return
        if not current["body"]:
            raise AnnotationError(current["line"], "segment has no text (delete the block)")
        segments.append(_build_segment(current))

    for n, raw in enumerate(text.splitlines(), start=1):
        line = raw.strip()
        if line.startswith("#"):
            key, sep, value = line[1:].partition(":")
            if sep and current is None and key.strip() in _META_KEYS:
                meta[key.strip()] = value.strip()
            continue
        if not line:
            continue
        if line.startswith("["):
            header = _HEADER.match(line)
            if header:
                flush()
                current = _parse_header(n, header)
                continue
        if current is None:
            raise AnnotationError(n, "text before the first segment header")
        current["body"].append((n, line))
    flush()

    if meta.get("status") != REVIEWED:
        raise AnnotationError(
            1, f"'# status:' is {meta.get('status')!r}: set it to {REVIEWED!r} after reviewing"
        )
    if "audio_file" not in meta or "duration" not in meta:
        raise AnnotationError(1, "missing '# audio_file:' or '# duration:' header")
    try:
        duration = float(meta["duration"])
    except ValueError as e:
        raise AnnotationError(1, f"invalid duration {meta['duration']!r}") from e

    return Transcript(
        metadata=Metadata(
            kind="reference",
            audio_file=meta["audio_file"],
            duration=duration,
            annotator=meta.get("annotator") or None,
            created_at=datetime.now(UTC),
            ilat_version=__version__,
        ),
        segments=sorted(segments, key=lambda s: s.start),
    )


def _parse_header(n: int, m: re.Match[str]) -> dict:
    try:
        start, end = parse_timestamp(m.group(1)), parse_timestamp(m.group(2))
    except ValueError as e:
        raise AnnotationError(n, str(e)) from e
    if end < start:
        raise AnnotationError(n, "segment end is before start")
    seg: dict = {"line": n, "start": start, "end": end, "lang": None, "channel": None,
                 "speaker": None, "overlap": False, "bc": False, "body": []}  # fmt: skip
    for attr in m.group(3).split():
        key, sep, value = attr.partition("=")
        if sep and key == "lang" and value in LANGS:
            seg["lang"] = value
        elif sep and key == "channel" and value in ("mic", "system", "mixed"):
            seg["channel"] = value
        elif sep and key == "speaker" and value:
            seg["speaker"] = value
        elif not sep and key in ("overlap", "bc"):
            seg[key] = True
        else:
            raise AnnotationError(n, f"unknown segment attribute {attr!r}")
    return seg


def _build_segment(seg: dict) -> Segment:
    words: list[Word] = []
    for n, line in seg["body"]:
        words.extend(_parse_line(n, line, seg["lang"], seg["bc"]))
    return Segment(
        start=seg["start"],
        end=seg["end"],
        text=" ".join(w.text for w in words),
        lang=seg["lang"],
        channel=seg["channel"],
        speaker=seg["speaker"],
        overlap=seg["overlap"],
        words=words,
    )


def _parse_line(n: int, line: str, seg_lang: str | None, seg_bc: bool) -> list[Word]:
    words: list[Word] = []
    pos = 0
    while pos < len(line):
        if line[pos].isspace():
            pos += 1
            continue
        m = _UNIT.match(line, pos)
        if not m:
            raise AnnotationError(n, f"cannot parse {line[pos:].split()[0]!r}")
        pos = m.end()
        codes = [c for c in m.group("codes").split("|") if c]
        if m.group("brace") is not None:
            texts, uncertain = m.group("brace").split(), False
        elif m.group("paren") is not None:
            texts, uncertain = m.group("paren").split(), True
        else:
            texts, uncertain = [m.group("word")], False
        if not texts:
            raise AnnotationError(n, "empty group")
        texts[-1] += m.group("punct")
        for t in texts:
            words.append(_make_word(n, t, codes, uncertain, seg_lang, seg_bc))
    return words


def _make_word(
    n: int, text: str, codes: list[str], uncertain: bool, seg_lang: str | None, seg_bc: bool
) -> Word:
    tags: list[WordTag] = []
    lang = seg_lang
    no_auto_filler = False
    for code in codes:
        if code in CODES:
            tags.append(CODES[code])
        elif code in LANGS:
            lang = code
        elif code == NO_AUTO_FILLER:
            no_auto_filler = True
        else:
            raise AnnotationError(n, f"unknown code {code!r} on {text!r}")
    if seg_bc:
        tags.append("backchannel")
    if core(text).endswith("-"):
        tags.append("truncated")
    if text in NONVERBAL:
        tags.append("nonverbal")
    if uncertain:
        tags.append("uncertain")
    if not no_auto_filler and _auto_filler(text, uncertain, "backchannel" in tags):
        tags.append("filler")
    if text in NONVERBAL or text == INAUDIBLE:
        lang = None
    # Keep a stable order and drop duplicates (e.g. "f" on an automatic filler).
    order = [*CODES.values(), "truncated", "nonverbal", "uncertain"]
    tags = sorted(set(tags), key=order.index)
    try:
        return Word(text=text, lang=lang, tags=tags)
    except ValueError as e:
        raise AnnotationError(n, str(e)) from e


def _auto_filler(text: str, uncertain: bool, backchannel: bool) -> bool:
    return (
        not uncertain and not backchannel and not text.endswith("?") and core(text) in AUTO_FILLERS
    )
