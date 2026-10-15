"""Audio extraction and conversion with ffmpeg."""

import shutil
import subprocess
import wave
from pathlib import Path

ASR_SAMPLE_RATE = 16_000


class FFmpegError(RuntimeError):
    pass


def ffmpeg_command(src: Path, dst: Path, sample_rate: int = ASR_SAMPLE_RATE) -> list[str]:
    """Build the ffmpeg command that converts any audio/video file to 16-bit PCM mono wav."""
    return [
        "ffmpeg",
        "-nostdin",
        "-hide_banner",
        "-loglevel",
        "error",
        "-y",
        "-i",
        str(src),
        "-vn",
        "-ac",
        "1",
        "-ar",
        str(sample_rate),
        "-c:a",
        "pcm_s16le",
        str(dst),
    ]


def extract_audio(src: Path, dst: Path, sample_rate: int = ASR_SAMPLE_RATE) -> Path:
    """Convert ``src`` (audio or video) to a mono wav at ``sample_rate`` and write it to ``dst``."""
    if shutil.which("ffmpeg") is None:
        raise FFmpegError("ffmpeg not found on PATH (install it with `brew install ffmpeg`)")
    if not src.is_file():
        raise FileNotFoundError(src)
    result = subprocess.run(
        ffmpeg_command(src, dst, sample_rate), capture_output=True, text=True, check=False
    )
    if result.returncode != 0:
        raise FFmpegError(f"ffmpeg failed on {src}: {result.stderr.strip()}")
    return dst


def wav_duration(path: Path) -> float:
    """Duration in seconds of a PCM wav file."""
    with wave.open(str(path), "rb") as f:
        return f.getnframes() / f.getframerate()
