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


@pytest.fixture(autouse=True)
def no_speaker_models(monkeypatch):
    """Tests never run (or download) the real voice models: they would depend on this machine.
    A test that needs voices patches ``parola.diarize.diarize`` with a fake."""
    monkeypatch.setattr("parola.capture.recorder._speaker_models", lambda: False)


@pytest.fixture(autouse=True)
def models_on_disk(monkeypatch):
    """The app believes the speech models are downloaded, whatever this machine has; the first
    download itself is tested with fakes (test_model_download.py)."""
    monkeypatch.setattr("parola.models.models_ready", lambda: True)
