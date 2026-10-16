import shutil
import subprocess
import wave
from pathlib import Path

import pytest

from parola.asr import ASRResult, MLXWhisperBackend
from parola.cli import main
from parola.pipeline import transcribe_file
from parola.schema import Segment, Transcript, Word
from tests.conftest import requires_ffmpeg


class FakeBackend:
    name = "fake"
    model = "fake-model"

    def __init__(self) -> None:
        self.calls: list[tuple[Path, str | None]] = []

    def transcribe(self, wav_path: Path, language: str | None = None) -> ASRResult:
        with wave.open(str(wav_path), "rb") as f:
            assert (f.getnchannels(), f.getframerate()) == (1, 16_000)
        self.calls.append((wav_path, language))
        seg = Segment(
            text="ciao ciao",
            start=0.0,
            end=1.0,
            lang="it",
            words=[Word(text="ciao", start=0.0, end=0.4), Word(text="ciao", start=0.5, end=1.0)],
        )
        return ASRResult(segments=[seg], language="it")


@requires_ffmpeg
def test_transcribe_file_writes_json_and_txt(tone_m4a: Path, tmp_path: Path):
    backend = FakeBackend()
    out_dir = tmp_path / "out"
    outputs = transcribe_file(tone_m4a, backend, out_dir=out_dir, language="it")

    assert outputs.json_path == out_dir / "tone.json"
    assert outputs.txt_path == out_dir / "tone.txt"
    assert backend.calls[0][1] == "it"

    t = Transcript.from_json(outputs.json_path.read_text())
    assert t.metadata.audio_file == "tone.m4a"
    assert t.metadata.duration == pytest.approx(2.0, abs=0.05)
    assert t.metadata.backend == "fake"
    assert t.metadata.language_requested == "it"
    assert t.metadata.language_detected == "it"
    assert [w.text for w in t.segments[0].words] == ["ciao", "ciao"]
    assert outputs.txt_path.read_text() == "[00:00:00.000 - 00:00:01.000] ciao ciao\n"


@requires_ffmpeg
def test_transcribe_file_defaults_to_input_folder(tone_m4a: Path):
    outputs = transcribe_file(tone_m4a, FakeBackend())
    assert outputs.json_path.parent == tone_m4a.parent


def test_cli_missing_file(tmp_path: Path, capsys):
    assert main(["transcribe", str(tmp_path / "nope.m4a")]) == 1
    assert "error" in capsys.readouterr().err


@pytest.mark.slow
@pytest.mark.skipif(shutil.which("say") is None, reason="macOS `say` not available")
def test_real_model_on_synthetic_speech(tmp_path: Path):
    """Runs mlx-whisper large-v3-turbo on speech synthesized with macOS `say`."""
    speech = tmp_path / "speech.aiff"
    subprocess.run(["say", "-o", str(speech), "Hello, this is a short test."], check=True)
    outputs = transcribe_file(speech, MLXWhisperBackend(), language="en")
    text = " ".join(s.text for s in outputs.transcript.segments).lower()
    assert "test" in text
    assert all(s.words for s in outputs.transcript.segments)
