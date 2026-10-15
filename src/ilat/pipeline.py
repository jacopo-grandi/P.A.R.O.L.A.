"""End-to-end transcription: media file -> wav -> ASR -> JSON + txt."""

import tempfile
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

from ilat import __version__
from ilat.asr import ASRBackend
from ilat.audio import extract_audio, wav_duration
from ilat.schema import Metadata, Transcript, to_text


@dataclass
class Outputs:
    transcript: Transcript
    json_path: Path
    txt_path: Path


def transcribe_file(
    src: Path,
    backend: ASRBackend,
    out_dir: Path | None = None,
    language: str | None = None,
) -> Outputs:
    """Transcribe ``src`` and write ``<stem>.json`` and ``<stem>.txt`` into ``out_dir``.

    ``out_dir`` defaults to the folder of ``src``, so transcripts of private
    recordings stay next to them (e.g. under the gitignored ``data/private/``).
    """
    out_dir = out_dir or src.parent
    out_dir.mkdir(parents=True, exist_ok=True)

    with tempfile.TemporaryDirectory(prefix="ilat-") as tmp:
        wav = extract_audio(src, Path(tmp) / "audio.wav")
        duration = wav_duration(wav)
        result = backend.transcribe(wav, language=language)

    transcript = Transcript(
        metadata=Metadata(
            kind="asr",
            audio_file=src.name,
            duration=duration,
            backend=backend.name,
            model=backend.model,
            language_requested=language,
            language_detected=result.language,
            created_at=datetime.now(UTC),
            ilat_version=__version__,
        ),
        segments=result.segments,
    )

    json_path = out_dir / f"{src.stem}.json"
    txt_path = out_dir / f"{src.stem}.txt"
    transcript.save(json_path)
    txt_path.write_text(to_text(transcript), encoding="utf-8")
    return Outputs(transcript=transcript, json_path=json_path, txt_path=txt_path)
