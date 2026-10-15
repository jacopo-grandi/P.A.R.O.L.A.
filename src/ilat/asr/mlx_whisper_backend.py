"""mlx-whisper backend (Apple Silicon)."""

from pathlib import Path
from typing import Any

from ilat.asr.base import ASRResult
from ilat.schema import Segment, Word
from ilat.schema.vocab import LANGS

DEFAULT_MODEL = "mlx-community/whisper-large-v3-turbo"


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


class MLXWhisperBackend:
    name = "mlx-whisper"

    def __init__(self, model: str = DEFAULT_MODEL) -> None:
        self.model = model

    def transcribe(self, wav_path: Path, language: str | None = None) -> ASRResult:
        import mlx_whisper

        # Library defaults are kept on purpose: decoding parameters only change after
        # they are measured on the test set (Phase 2).
        result = mlx_whisper.transcribe(
            str(wav_path),
            path_or_hf_repo=self.model,
            language=language,
            word_timestamps=True,
        )
        return convert_result(result)
