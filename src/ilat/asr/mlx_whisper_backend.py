"""mlx-whisper backend (Apple Silicon)."""

from pathlib import Path
from typing import Any

from ilat.asr.base import ASRResult
from ilat.schema import Segment, Word

DEFAULT_MODEL = "mlx-community/whisper-large-v3-turbo"


def convert_result(result: dict[str, Any]) -> ASRResult:
    """Convert the dict returned by ``mlx_whisper.transcribe`` into an ``ASRResult``."""
    language = result.get("language")
    segments = []
    for seg in result.get("segments", []):
        words = [
            Word(
                text=w["word"].strip(),
                start=w["start"],
                # Whisper occasionally emits end < start by a few ms; clamp it.
                end=max(w["end"], w["start"]),
                probability=w.get("probability"),
            )
            for w in seg.get("words", [])
            if w["word"].strip()
        ]
        segments.append(
            Segment(
                text=seg["text"].strip(),
                start=seg["start"],
                end=max(seg["end"], seg["start"]),
                lang=language,
                words=words,
            )
        )
    return ASRResult(segments=segments, language=language)


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
