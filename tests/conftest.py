import shutil
import subprocess
from pathlib import Path

import pytest

requires_ffmpeg = pytest.mark.skipif(shutil.which("ffmpeg") is None, reason="ffmpeg not installed")


@pytest.fixture
def tone_m4a(tmp_path: Path) -> Path:
    """A 2-second stereo 44.1 kHz AAC tone, generated on the fly (never stored in the repo)."""
    path = tmp_path / "tone.m4a"
    subprocess.run(
        [
            "ffmpeg", "-nostdin", "-loglevel", "error", "-y",
            "-f", "lavfi", "-i", "sine=frequency=440:duration=2:sample_rate=44100",
            "-ac", "2", "-c:a", "aac", str(path),
        ],
        check=True,
    )  # fmt: skip
    return path
