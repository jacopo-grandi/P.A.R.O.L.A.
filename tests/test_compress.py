"""Lossless compression of a call's audio after transcription."""

import subprocess
from pathlib import Path

import pytest

from parola.audio import FFmpegError, channel_file, compress
from parola.audio.compress import _pcm_digest
from tests.conftest import requires_ffmpeg


def recording_like(path: Path, seconds: int = 2) -> Path:
    """48 kHz stereo float, as the capture helper writes the system channel."""
    subprocess.run(["ffmpeg", "-nostdin", "-loglevel", "error", "-y", "-f", "lavfi", "-i",
                    f"sine=frequency=330:duration={seconds},aformat=channel_layouts=stereo",
                    "-ar", "48000", "-c:a", "pcm_f32le", str(path)], check=True)  # fmt: skip
    return path


@requires_ffmpeg
def test_flac_holds_exactly_what_the_models_hear(tmp_path):
    wav = recording_like(tmp_path / "c.system.wav")
    before = _pcm_digest(wav)
    flac = compress(wav)
    assert flac == tmp_path / "c.system.flac" and not wav.exists()
    assert _pcm_digest(flac) == before
    assert flac.stat().st_size < 0.1 * (2 * 48000 * 2 * 4)  # far below the float wav


@requires_ffmpeg
def test_a_failed_compression_keeps_the_wav(tmp_path):
    bad = tmp_path / "c.mic.wav"
    bad.write_text("not audio")
    with pytest.raises(FFmpegError):
        compress(bad)
    assert bad.exists() and not list(tmp_path.glob("*.flac*"))


@requires_ffmpeg
def test_channel_file_prefers_the_compressed_one(tmp_path):
    assert channel_file(tmp_path, "c", "mic") is None
    recording_like(tmp_path / "c.mic.wav")
    assert channel_file(tmp_path, "c", "mic").suffix == ".wav"
    compress(tmp_path / "c.mic.wav")
    assert channel_file(tmp_path, "c", "mic").suffix == ".flac"


@requires_ffmpeg
def test_compress_command_does_transcribed_calls_only(tmp_path, capsys):
    from datetime import UTC, datetime

    from parola.cli import main
    from parola.schema import Metadata, Transcript

    meta = Metadata(audio_file="x", duration=2, created_at=datetime(2026, 10, 16, tzinfo=UTC),
                    parola_version="0")  # fmt: skip
    Transcript(metadata=meta, segments=[]).save(tmp_path / "done.json")
    recording_like(tmp_path / "done.system.wav")
    recording_like(tmp_path / "pending.system.wav")  # no transcript yet: not touched
    assert main(["compress", "--dir", str(tmp_path), "--dry-run"]) == 0
    assert "would compress done.system.wav" in capsys.readouterr().out
    assert (tmp_path / "done.system.wav").exists()
    assert main(["compress", "--dir", str(tmp_path)]) == 0
    assert (tmp_path / "done.system.flac").exists() and not (tmp_path / "done.system.wav").exists()
    assert (tmp_path / "pending.system.wav").exists()
