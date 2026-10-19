"""Loudness measured per channel for playback normalization: parsed, cached, never written
back to the audio. The gain policy itself lives in the UI (tests/test_helpers.js)."""

import json
import wave

import numpy as np

from parola.audio import loudness, playback
from tests.conftest import requires_ffmpeg

SUMMARY = """\
[Parsed_ebur128_0 @ 0x600000c74000] Summary:

  Integrated loudness:
    I:         -49.4 LUFS
    Threshold: -60.1 LUFS

  Loudness range:
    LRA:        12.9 LU
    Threshold: -70.2 LUFS
    LRA low:   -60.6 LUFS
    LRA high:  -47.7 LUFS
"""


def tone(tmp_path, name, amplitude, seconds=3.0):
    path = tmp_path / name
    samples = (np.sin(np.arange(int(16000 * seconds)) / 5) * amplitude).astype(np.int16)
    with wave.open(str(path), "wb") as w:
        w.setnchannels(1), w.setsampwidth(2), w.setframerate(16000)
        w.writeframes(samples.tobytes())
    return path


def test_the_integrated_loudness_is_read_from_the_summary():
    assert loudness.integrated(SUMMARY) == -49.4
    assert loudness.integrated("no summary at all") is None
    assert loudness.integrated("    I:          -inf LUFS\n") is None  # no sound at all


@requires_ffmpeg
def test_a_tone_20_db_down_measures_20_lufs_quieter(tmp_path):
    loud = loudness.measure(tone(tmp_path, "loud.wav", 16000))
    quiet = loudness.measure(tone(tmp_path, "quiet.wav", 1600))
    assert loud is not None and quiet is not None and quiet < loud
    assert abs((loud - quiet) - 20.0) < 1.0


def test_a_file_that_cannot_be_read_measures_nothing(tmp_path):
    bad = tmp_path / "call.mic.wav"
    bad.write_bytes(b"RIFF" + b"\0" * 100)  # not real audio, whether ffmpeg is there or not
    assert loudness.measure(bad) is None


def test_each_file_is_measured_exactly_once(tmp_path, monkeypatch):
    calls = []
    monkeypatch.setattr(loudness, "measure", lambda p: calls.append(p) or -40.0)
    mic = tmp_path / "call.mic.wav"
    mic.write_bytes(b"x" * 10)
    for _ in range(2):
        assert loudness.channel_loudness(tmp_path, {"mic": mic}) == {"mic": -40.0}
    assert len(calls) == 1  # the second open reads the cache


def test_a_rewritten_file_is_measured_again_and_the_old_entry_goes(tmp_path, monkeypatch):
    monkeypatch.setattr(loudness, "measure", lambda p: -40.0)
    mic = tmp_path / "call.mic.wav"
    mic.write_bytes(b"x" * 10)
    loudness.channel_loudness(tmp_path, {"mic": mic})
    mic.write_bytes(b"y" * 20)  # recorded again under the same name
    monkeypatch.setattr(loudness, "measure", lambda p: -15.0)
    assert loudness.channel_loudness(tmp_path, {"mic": mic}) == {"mic": -15.0}
    store = json.loads((tmp_path / playback.CACHE / loudness.LOUDNESS).read_text())
    assert list(store.values()) == [-15.0]  # the stale entry was pruned


def test_a_failed_measurement_is_remembered_not_retried(tmp_path, monkeypatch):
    calls = []
    monkeypatch.setattr(loudness, "measure", lambda p: calls.append(p))
    mic = tmp_path / "call.mic.wav"
    mic.write_bytes(b"x" * 10)
    for _ in range(2):
        assert loudness.channel_loudness(tmp_path, {"mic": mic}) == {}
    assert len(calls) == 1
