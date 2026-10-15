import subprocess
from datetime import UTC, datetime
from pathlib import Path

import pytest

from ilat.asr import ASRResult
from ilat.capture import recorder
from ilat.schema import Metadata, Segment, Transcript, Word
from tests.conftest import requires_ffmpeg


def part(*segments):
    return Transcript(
        metadata=Metadata(audio_file="x.wav", duration=10, backend="fake", model="m",
                          created_at=datetime(2026, 10, 15, tzinfo=UTC), ilat_version="0"),
        segments=list(segments),
    )  # fmt: skip


def seg(start, end, text):
    return Segment(start=start, end=end, text=text, lang="it",
                   words=[Word(text=t) for t in text.split()])  # fmt: skip


def test_merge_channels_sorts_and_labels():
    mic = part(seg(0, 2, "ciao a tutti"), seg(5, 6, "sì"))
    system = part(seg(2.5, 4, "ciao Jacopo"), seg(5, 7, "allora iniziamo"))
    merged = recorder.merge_channels({"mic": mic, "system": system}, "call.*.wav", 7.0)
    assert [(s.start, s.channel) for s in merged.segments] == [
        (0, "mic"), (2.5, "system"), (5, "mic"), (5, "system"),
    ]  # fmt: skip
    assert merged.metadata.duration == 7.0
    assert recorder.to_dialogue(merged).splitlines() == [
        "[00:00:00.000 - 00:00:02.000] Io: ciao a tutti",
        "[00:00:02.500 - 00:00:04.000] Altri: ciao Jacopo",
        "[00:00:05.000 - 00:00:06.000] Io: sì",
        "[00:00:05.000 - 00:00:07.000] Altri: allora iniziamo",
    ]


def _write(path: Path, source: str) -> None:
    subprocess.run(["ffmpeg", "-nostdin", "-loglevel", "error", "-y", "-f", "lavfi", "-i",
                    source, "-ac", "1", "-ar", "48000", str(path)], check=True)  # fmt: skip


@requires_ffmpeg
def test_peak_detects_digital_silence(tmp_path):
    _write(tmp_path / "tone.wav", "sine=frequency=440:duration=1")
    _write(tmp_path / "silence.wav", "anullsrc=r=48000:cl=mono:d=1")
    assert recorder.peak(tmp_path / "tone.wav") > 1000
    assert recorder.peak(tmp_path / "silence.wav") < recorder.SILENCE_PEAK


class FakeBackend:
    name, model = "fake", "fake-model"

    def __init__(self):
        self.calls = 0

    def transcribe(self, wav_path, language=None):
        self.calls += 1
        return ASRResult(segments=[seg(0, 1, f"canale {self.calls}")], language="it")


@requires_ffmpeg
def test_transcribe_recording_skips_silent_channel(tmp_path, capsys):
    _write(tmp_path / "c.mic.wav", "sine=frequency=440:duration=1")
    _write(tmp_path / "c.system.wav", "anullsrc=r=48000:cl=mono:d=1")
    rec = recorder.Recording("c", tmp_path, {"mic": {"seconds": 1.0}, "system": {"seconds": 1.0}})
    backend = FakeBackend()
    json_path, txt_path = recorder.transcribe_recording(rec, backend)
    assert backend.calls == 1  # the silent system channel is not transcribed
    assert "system channel is silent" in capsys.readouterr().err
    t = Transcript.load(json_path)
    assert [s.channel for s in t.segments] == ["mic"]
    assert txt_path.read_text().startswith("[00:00:00.000 - 00:00:01.000] Io: canale 1")
    assert not list(tmp_path.glob(".c.*"))  # temporary folders removed


@requires_ffmpeg
def test_transcribe_recording_all_silent(tmp_path):
    _write(tmp_path / "c.mic.wav", "anullsrc=r=48000:cl=mono:d=1")
    rec = recorder.Recording("c", tmp_path, {"mic": {"seconds": 1.0}})
    with pytest.raises(recorder.CaptureError, match="silent"):
        recorder.transcribe_recording(rec, FakeBackend())


def test_helper_is_not_rebuilt_when_up_to_date(monkeypatch, tmp_path):
    binary = tmp_path / "ilat-capture"
    binary.write_text("")
    monkeypatch.setattr(recorder, "BINARY", binary)
    monkeypatch.setattr(subprocess, "run", lambda *a, **k: pytest.fail("rebuilt"))
    future = max(p.stat().st_mtime for p in recorder.SWIFT_DIR.iterdir()) + 10
    import os

    os.utime(binary, (future, future))
    assert recorder.build_helper() == binary
