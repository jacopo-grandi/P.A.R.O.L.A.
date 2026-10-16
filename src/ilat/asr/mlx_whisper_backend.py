"""mlx-whisper backend (Apple Silicon)."""

from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from typing import Any

from ilat.asr.base import ASRResult
from ilat.schema import Segment, Word
from ilat.schema.vocab import LANGS

DEFAULT_MODEL = "mlx-community/whisper-large-v3-turbo"
SEED = 0
# With VAD, a segment is dropped only when none of its words falls on sound: text written over
# silence is invented ("Grazie a tutti."). Judging by the share of the segment with sound was
# measured and rejected: long segments with little speech were dropped with real words in them
# (results/2026-10-15-vad.md). Tolerance around the regions, for imprecise word timestamps:
WORD_TOLERANCE_SECONDS = 0.3


def convert_result(result: dict[str, Any]) -> ASRResult:
    """Convert the dict returned by ``mlx_whisper.transcribe`` into an ``ASRResult``."""
    language = result.get("language")
    # The schema only knows it/en; any other detected language stays in the metadata.
    segment_lang = language if language in LANGS else None
    segments: list[Segment] = []
    for seg in result.get("segments", []):
        words = _merge_words(seg.get("words", []))
        # Segments whose words could not be aligned sometimes keep timestamps that go back
        # before the previous segment. Keep the text order and move the start forward.
        start = max(seg["start"], segments[-1].start) if segments else seg["start"]
        segments.append(
            Segment(
                text=seg["text"].strip(),
                start=start,
                end=max(seg["end"], start),
                lang=segment_lang,
                words=words,
            )
        )
    return ASRResult(segments=segments, language=language)


def _merge_words(raw_words: list[dict[str, Any]]) -> list[Word]:
    """Build words, joining tokens without a leading space to the previous word.

    Whisper splits elisions into separate tokens (" d", "'accordo"); in the transcript they
    are one whitespace-delimited word ("d'accordo"), as in the segment text.
    """
    words: list[Word] = []
    for w in raw_words:
        text = w["word"].strip()
        if not text:
            continue
        start = w["start"]
        # Whisper occasionally emits end < start by a few ms; clamp it.
        end = max(w["end"], start)
        probability = w.get("probability")
        if words and not w["word"][:1].isspace():
            prev = words[-1]
            probs = [p for p in (prev.probability, probability) if p is not None]
            words[-1] = Word(
                text=prev.text + text,
                start=prev.start,
                end=max(end, prev.end or end),
                probability=min(probs) if probs else None,
            )
        else:
            words.append(Word(text=text, start=start, end=end, probability=probability))
    return words


def has_sound(segment: Segment, regions: list[tuple[float, float]]) -> bool:
    """True if any word midpoint (or, without word times, the segment) falls on sound."""
    t = WORD_TOLERANCE_SECONDS
    mids = [
        (w.start + w.end) / 2 for w in segment.words if w.start is not None and w.end is not None
    ]
    if not mids:
        return sound_share(segment.start, segment.end, regions) > 0
    return any(a - t <= m <= b + t for m in mids for a, b in regions)


def sound_share(start: float, end: float, regions: list[tuple[float, float]]) -> float:
    """Share of [start, end] covered by the sound regions."""
    if end <= start:
        return 1.0 if any(a <= start <= b for a, b in regions) else 0.0
    covered = sum(max(0.0, min(end, b) - max(start, a)) for a, b in regions)
    return covered / (end - start)


@contextmanager
def carried_prompt(text: str | None) -> Iterator[None]:
    """Put ``text`` at the start of Whisper's prompt on every window, not only the first one.

    mlx-whisper prepends the initial prompt to the transcribed text and keeps only the last
    n_ctx // 2 - 1 tokens of it, so after a minute or two of speech the initial prompt is gone.
    This keeps ``text`` and fills the rest of the budget with the most recent text, like
    openai-whisper's ``carry_initial_prompt``. The patch is active only inside the ``with``.
    """
    if not text:
        yield
        return
    from mlx_whisper import decoding

    original = decoding.DecodingTask._get_initial_tokens

    def initial_tokens(self) -> tuple[int, ...]:
        tokens = list(self.sot_sequence)
        if prefix := self.options.prefix:
            prefix_tokens = (self.tokenizer.encode(" " + prefix.strip())
                             if isinstance(prefix, str) else list(prefix))  # fmt: skip
            if self.sample_len is not None:
                prefix_tokens = prefix_tokens[-(self.n_ctx // 2 - self.sample_len) :]
            tokens = tokens + prefix_tokens
        carried = self.tokenizer.encode(" " + text.strip())
        prompt = self.options.prompt or []
        if isinstance(prompt, str):
            prompt = self.tokenizer.encode(" " + prompt.strip())
        room = max(0, self.n_ctx // 2 - 1 - len(carried))
        recent = list(prompt)[-room:] if room else []
        return tuple([self.tokenizer.sot_prev, *carried, *recent, *tokens])

    decoding.DecodingTask._get_initial_tokens = initial_tokens
    try:
        yield
    finally:
        decoding.DecodingTask._get_initial_tokens = original


class MLXWhisperBackend:
    name = "mlx-whisper"

    def __init__(
        self,
        model: str = DEFAULT_MODEL,
        initial_prompt: str | None = None,
        seed: int = SEED,
        vad: bool = False,
        glossary: str | None = None,
    ) -> None:
        self.model = model
        self.initial_prompt = initial_prompt
        self.seed = seed
        # Transcribe only the stretches with sound (ilat.audio.vad).
        self.vad = vad
        # Terms carried in the prompt of every window (ilat.glossary).
        self.glossary = glossary

    def transcribe(self, wav_path: Path, language: str | None = None) -> ASRResult:
        with carried_prompt(self.glossary):
            return self._transcribe(wav_path, language)

    def _transcribe(self, wav_path: Path, language: str | None = None) -> ASRResult:
        import mlx.core as mx
        import mlx_whisper

        # Whisper falls back to sampling at higher temperatures when decoding fails
        # (loops, low confidence): a fixed seed makes those runs reproducible.
        mx.random.seed(self.seed)

        if not self.vad:
            # Library defaults are kept on purpose: decoding parameters only change after
            # they are measured on the test set (Phase 2).
            result = mlx_whisper.transcribe(
                str(wav_path),
                path_or_hf_repo=self.model,
                language=language,
                word_timestamps=True,
                initial_prompt=self.initial_prompt,
            )
            return convert_result(result)

        from ilat.audio.vad import speech_audio, speech_regions

        regions = speech_regions(wav_path)
        if not regions:
            return ASRResult(segments=[], language=None)
        if language is None:
            # Detect the language on speech only: Whisper looks at the first 30 s, which in a
            # call channel can be silence or the other side's music.
            probe = mlx_whisper.transcribe(
                speech_audio(wav_path, regions, max_seconds=30.0),
                path_or_hf_repo=self.model,
                condition_on_previous_text=False,
            )
            language = probe.get("language")
        # Decoding is the same as without VAD: shifting where it starts (or decoding each sound
        # stretch on its own, or Whisper's hallucination_silence_threshold) moved Whisper's
        # windows and made it skip real speech on the test set (results/2026-10-15-vad.md).
        merged = mlx_whisper.transcribe(
            str(wav_path),
            path_or_hf_repo=self.model,
            language=language,
            word_timestamps=True,
            initial_prompt=self.initial_prompt,
        )
        converted = convert_result(merged)
        converted.segments = [s for s in converted.segments if has_sound(s, regions)]
        return converted
