"""The WAV copies the player gets for FLAC calls: same samples, reused, few, forgotten."""

import os
import subprocess
import wave

import numpy as np

from parola.audio import playback
from tests.conftest import requires_ffmpeg


def flac(tmp_path, name, seconds=1.0):
    wav = tmp_path / f"{name}.wav"
    samples = (np.sin(np.arange(int(16000 * seconds)) / 5) * 8000).astype(np.int16)
    with wave.open(str(wav), "wb") as w:
        w.setnchannels(1), w.setsampwidth(2), w.setframerate(16000)
        w.writeframes(samples.tobytes())
    out = tmp_path / f"{name}.flac"
    subprocess.run(["ffmpeg", "-nostdin", "-loglevel", "error", "-i", str(wav), "-c:a", "flac",
                    str(out)], check=True)  # fmt: skip
    wav.unlink()
    return out, samples


def test_a_wav_is_played_as_it_is(tmp_path):
    wav = tmp_path / "call.mic.wav"
    wav.write_bytes(b"RIFF")
    assert playback.playable(tmp_path, wav) == wav
    assert not (tmp_path / playback.CACHE).exists()


@requires_ffmpeg
def test_a_flac_is_played_as_a_wav_with_the_same_samples(tmp_path):
    source, samples = flac(tmp_path, "call.mic")
    copy = playback.playable(tmp_path, source)
    assert copy.suffix == ".wav" and copy.parent == tmp_path / playback.CACHE
    with wave.open(str(copy)) as w:
        assert w.getframerate() == 16000
        assert np.array_equal(np.frombuffer(w.readframes(w.getnframes()), np.int16), samples)
    assert playback.playable(tmp_path, source) == copy  # decoded once


@requires_ffmpeg
def test_only_the_last_opened_copies_are_kept(tmp_path):
    sources = [flac(tmp_path, f"c{i}.mic", 0.1)[0] for i in range(playback.KEEP + 2)]
    copies = []
    for i, s in enumerate(sources):
        copies.append(playback.playable(tmp_path, s))
        os.utime(copies[-1], (1000 + i, 1000 + i))  # opened in this order
    playback.playable(tmp_path, sources[-1])
    kept = sorted(p.name for p in (tmp_path / playback.CACHE).glob("*.wav"))
    assert kept == sorted(c.name for c in copies[-playback.KEEP :])


@requires_ffmpeg
def test_a_call_recorded_again_gets_a_new_copy(tmp_path):
    source, _ = flac(tmp_path, "call.mic", 0.2)
    first = playback.playable(tmp_path, source)
    source.unlink()
    source, _ = flac(tmp_path, "call.mic", 0.5)
    assert playback.playable(tmp_path, source) != first


@requires_ffmpeg
def test_forget_removes_only_that_call(tmp_path):
    a = playback.playable(tmp_path, flac(tmp_path, "call.mic", 0.1)[0])
    b = playback.playable(tmp_path, flac(tmp_path, "call.2.mic", 0.1)[0])
    playback.forget(tmp_path, "call", ("mic", "system"))
    assert not a.exists() and b.exists()
