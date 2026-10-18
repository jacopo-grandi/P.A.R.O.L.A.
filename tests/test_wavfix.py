"""WAV headers left with a 0-byte data chunk (the file was never closed) get their real sizes."""

import struct
import wave

from parola.audio.wavfix import needs_repair, repair


def broken_wav(path, samples):
    """What an unclosed AVAudioFile leaves: the samples are there, the sizes are not."""
    fmt = struct.pack("<HHIIHH", 1, 1, 16000, 32000, 2, 16)
    header = b"RIFF" + struct.pack("<I", 4088) + b"WAVE" + b"fmt " + struct.pack("<I", 16) + fmt
    header += b"FLLR" + struct.pack("<I", 8) + bytes(8) + b"data" + struct.pack("<I", 0)
    path.write_bytes(header + struct.pack(f"<{len(samples)}h", *samples))
    return path


def test_a_wav_left_unclosed_gets_its_sizes(tmp_path):
    samples = [(i * 37) % 2000 - 1000 for i in range(16000)]  # one second
    path = broken_wav(tmp_path / "a.wav", samples)
    before = path.read_bytes()
    assert needs_repair(path) and repair(path)
    with wave.open(str(path)) as w:
        assert w.getnframes() == 16000
        assert list(struct.unpack("<16000h", w.readframes(16000))) == samples
    after = path.read_bytes()
    assert len(after) == len(before)
    assert sum(a != b for a, b in zip(before, after, strict=True)) <= 8  # only the two sizes


def test_a_good_wav_is_left_alone(tmp_path):
    path = tmp_path / "ok.wav"
    with wave.open(str(path), "wb") as w:
        w.setnchannels(1), w.setsampwidth(2), w.setframerate(16000)
        w.writeframes(bytes(3200))
    before = path.read_bytes()
    assert not needs_repair(path) and not repair(path)
    assert path.read_bytes() == before


def test_repair_is_done_once(tmp_path):
    path = broken_wav(tmp_path / "b.wav", [1, 2, 3])
    assert repair(path) and not repair(path)


def test_not_a_wav(tmp_path):
    path = tmp_path / "c.wav"
    path.write_bytes(b"fLaC" + bytes(100))
    assert not needs_repair(path) and not repair(path)
