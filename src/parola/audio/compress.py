"""Shrink a call's audio after transcription, without losing what the models hear.

The models never see the recorded audio as it is: every file is converted to 16 kHz mono 16-bit
PCM first (``ffmpeg_command``). That exact signal, stored as FLAC (lossless), takes about
100 MB per hour of call instead of about 2 GB, and transcribing it again gives the same input,
sample for sample. A lossy codec (AAC 32-64 kbps) would be smaller still, but on the test set it
changed turbo's transcript enough to raise the fidelity WER from about 5% to 9-12%
(decision 0024).
"""

from __future__ import annotations

import hashlib
import shutil
import subprocess
from pathlib import Path

from parola.audio.extract import ASR_SAMPLE_RATE, FFmpegError

AUDIO_EXTENSIONS = (".flac", ".wav")  # compressed first: what a call's channel file can be


def _pcm_digest(path: Path) -> str:
    """Hash of the 16 kHz mono 16-bit samples the models would get from ``path``."""
    proc = subprocess.run(
        ["ffmpeg", "-nostdin", "-loglevel", "error", "-i", str(path), "-vn", "-ac", "1",
         "-ar", str(ASR_SAMPLE_RATE), "-c:a", "pcm_s16le", "-f", "s16le", "-"],
        capture_output=True, check=False,
    )  # fmt: skip
    if proc.returncode != 0:
        raise FFmpegError(f"ffmpeg could not read {path}: {proc.stderr.decode().strip()}")
    return hashlib.sha256(proc.stdout).hexdigest()


def compress(wav: Path) -> Path:
    """Write ``<stem>.flac`` next to ``wav``, check it holds the same samples, delete the wav.

    On any failure the wav is kept and the partial FLAC removed.
    """
    if shutil.which("ffmpeg") is None:
        raise FFmpegError("ffmpeg not found on PATH (install it with `brew install ffmpeg`)")
    flac = wav.with_suffix(".flac")
    part = wav.with_suffix(".flac.part")
    try:
        result = subprocess.run(
            ["ffmpeg", "-nostdin", "-loglevel", "error", "-y", "-i", str(wav), "-vn", "-ac", "1",
             "-ar", str(ASR_SAMPLE_RATE), "-sample_fmt", "s16", "-c:a", "flac",
             "-compression_level", "8", "-f", "flac", str(part)],
            capture_output=True, text=True, check=False,
        )  # fmt: skip
        if result.returncode != 0:
            raise FFmpegError(f"ffmpeg failed on {wav}: {result.stderr.strip()}")
        if _pcm_digest(part) != _pcm_digest(wav):
            raise FFmpegError(f"{part.name} does not hold the same samples as {wav.name}")
        part.replace(flac)
    except BaseException:
        part.unlink(missing_ok=True)
        raise
    wav.unlink()
    return flac


def channel_file(folder: Path, name: str, channel: str) -> Path | None:
    """The audio file of one channel of a call, compressed or not."""
    for ext in AUDIO_EXTENSIONS:
        path = folder / f"{name}.{channel}{ext}"
        if path.exists():
            return path
    return None
