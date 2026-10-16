import subprocess
from pathlib import Path

import pytest

from parola.audio.vad import speech_regions
from tests.conftest import requires_ffmpeg


def synth(path: Path, parts: list[tuple[str, float]], noise: bool = False) -> Path:
    """Concatenate tones and silences into a 16 kHz mono 16-bit wav."""
    inputs, labels = [], []
    for k, (kind, seconds) in enumerate(parts):
        src = (f"sine=frequency=300:sample_rate=16000:duration={seconds}" if kind == "tone"
               else f"anullsrc=r=16000:cl=mono:d={seconds}")  # fmt: skip
        inputs += ["-f", "lavfi", "-i", src]
        labels.append(f"[{k}:a]")
    graph = "".join(labels) + f"concat=n={len(parts)}:v=0:a=1[a]"
    if noise:
        inputs += ["-f", "lavfi", "-i", "anoisesrc=r=16000:a=0.002:d=60"]
        graph += f";[a][{len(parts)}:a]amix=inputs=2:duration=first:normalize=0[b]"
    out = "[b]" if noise else "[a]"
    subprocess.run(["ffmpeg", "-nostdin", "-loglevel", "error", "-y", *inputs,
                    "-filter_complex", graph, "-map", out, "-ac", "1", "-c:a", "pcm_s16le",
                    str(path)], check=True)  # fmt: skip
    return path


@requires_ffmpeg
@pytest.mark.parametrize("noise", [False, True])
def test_speech_regions(tmp_path, noise):
    wav = synth(tmp_path / "a.wav", [("silence", 2), ("tone", 1), ("silence", 3), ("tone", 2),
                                     ("silence", 1)], noise=noise)  # fmt: skip
    regions = speech_regions(wav)
    assert len(regions) == 2
    (s1, e1), (s2, e2) = regions
    assert s1 == pytest.approx(1.75, abs=0.1) and e1 == pytest.approx(3.25, abs=0.1)
    assert s2 == pytest.approx(5.75, abs=0.1) and e2 == pytest.approx(8.25, abs=0.1)


@requires_ffmpeg
def test_short_gaps_are_bridged_and_blips_dropped(tmp_path):
    wav = synth(tmp_path / "b.wav", [("tone", 1), ("silence", 0.3), ("tone", 1), ("silence", 2),
                                     ("tone", 0.1), ("silence", 2)])  # fmt: skip
    regions = speech_regions(wav)
    assert len(regions) == 1  # 0.3 s gap bridged, 0.1 s blip dropped
    assert regions[0][1] == pytest.approx(2.55, abs=0.1)


@requires_ffmpeg
def test_digital_silence_has_no_regions(tmp_path):
    assert speech_regions(synth(tmp_path / "c.wav", [("silence", 3)])) == []


@requires_ffmpeg
def test_speech_audio_concatenates_regions_up_to_limit(tmp_path):
    from parola.audio.vad import speech_audio

    wav = synth(tmp_path / "d.wav", [("silence", 2), ("tone", 1), ("silence", 3), ("tone", 2)])
    audio = speech_audio(wav, [(2.0, 3.0), (6.0, 8.0)], max_seconds=2.5)
    assert audio.dtype.name == "float32" and len(audio) == int(2.5 * 16000)
    assert abs(audio).max() > 0.1  # only sound, no leading silence


def test_chunks_group_close_regions_and_split_long_ones():
    from parola.audio.vad import chunks

    regions = [(0.0, 5.0), (6.0, 10.0), (20.0, 25.0), (30.0, 95.0)]
    assert chunks(regions) == [(0.0, 10.0), (20.0, 25.0), (30.0, 58.0), (58.0, 86.0), (86.0, 95.0)]
