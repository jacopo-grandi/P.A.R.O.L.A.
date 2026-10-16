import wave
from pathlib import Path

import pytest

from parola.audio import FFmpegError, extract_audio, wav_duration
from parola.audio.extract import ffmpeg_command
from tests.conftest import requires_ffmpeg


def test_ffmpeg_command_targets_16k_mono_pcm():
    cmd = ffmpeg_command(Path("in.mp4"), Path("out.wav"))
    assert cmd[0] == "ffmpeg"
    assert "-nostdin" in cmd
    assert cmd[cmd.index("-i") + 1] == "in.mp4"
    assert cmd[cmd.index("-ac") + 1] == "1"
    assert cmd[cmd.index("-ar") + 1] == "16000"
    assert cmd[cmd.index("-c:a") + 1] == "pcm_s16le"
    assert "-vn" in cmd
    assert cmd[-1] == "out.wav"


@requires_ffmpeg
def test_extract_audio_converts_to_16k_mono(tone_m4a: Path, tmp_path: Path):
    out = extract_audio(tone_m4a, tmp_path / "out.wav")
    with wave.open(str(out), "rb") as f:
        assert f.getnchannels() == 1
        assert f.getframerate() == 16_000
        assert f.getsampwidth() == 2
    assert wav_duration(out) == pytest.approx(2.0, abs=0.05)


def test_extract_audio_missing_file(tmp_path: Path):
    with pytest.raises(FileNotFoundError):
        extract_audio(tmp_path / "nope.m4a", tmp_path / "out.wav")


@requires_ffmpeg
def test_extract_audio_invalid_file(tmp_path: Path):
    bad = tmp_path / "bad.m4a"
    bad.write_text("not audio")
    with pytest.raises(FFmpegError):
        extract_audio(bad, tmp_path / "out.wav")
