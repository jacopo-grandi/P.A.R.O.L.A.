"""Long runs of exact zeros, shortened for Whisper, and the timestamps given back."""

import numpy as np

from parola.audio.silence import condense, digital_silences

RATE = 100  # samples per second: small numbers, easy to check by hand


def signal(*parts):
    """("sound" | "zero", seconds) pieces: sound is a constant 1000."""
    return np.concatenate([np.full(int(s * RATE), 1000 if kind == "sound" else 0, np.int16)
                           for kind, s in parts])  # fmt: skip


def test_only_runs_of_zeros_long_enough_count():
    x = signal(("sound", 2), ("zero", 1), ("sound", 2), ("zero", 5), ("sound", 1))
    assert digital_silences(x, RATE, 3.0) == [(5.0, 10.0)]
    assert digital_silences(signal(("sound", 3)), RATE) == []


def test_noise_is_not_silence():
    noisy = np.random.default_rng(0).integers(-3, 4, 10 * RATE).astype(np.int16)
    noisy[noisy == 0] = 1
    assert digital_silences(noisy, RATE) == []


def test_condense_keeps_one_second_and_maps_times_back():
    # sound 0-2 s, zeros 2-12 s, sound 12-14 s, zeros 14-20 s, sound 20-21 s
    x = signal(("sound", 2), ("zero", 10), ("sound", 2), ("zero", 6), ("sound", 1))
    silences = digital_silences(x, RATE, 3.0)
    short, cuts = condense(x, RATE, silences, keep=1.0)
    assert len(short) == (2 + 1 + 2 + 1 + 1) * RATE  # each silence down to 1 s
    # In the short audio the second sound starts at 3 s, the third at 6 s.
    assert short[3 * RATE] == 1000 and short[3 * RATE - 1] == 0
    assert cuts.original(1.0) == 1.0  # before any cut
    assert cuts.original(3.0) == 12.0  # second sound
    assert cuts.original(4.5) == 13.5
    assert cuts.original(6.0) == 20.0  # third sound
    assert cuts.original(6.5) == 20.5


def test_no_silence_no_change():
    x = signal(("sound", 2))
    short, cuts = condense(x, RATE, [])
    assert np.array_equal(short, x) and cuts.original(1.5) == 1.5


def test_restored_segments_start_on_their_words():
    from parola.asr.mlx_whisper_backend import restore_times
    from parola.audio.silence import Cuts
    from parola.schema import Segment, Word

    cuts = Cuts(at=[3.0], shift=[20.0])  # 20 s were removed at 3.0 s of the short audio
    words = [Word(text="ma", start=3.2, end=3.5), Word(text="non", start=3.6, end=4.0)]
    seg = Segment(text="ma non", start=2.9, end=4.0, words=words)
    (back,) = restore_times([seg], cuts)
    assert (back.start, back.end) == (23.2, 24.0)  # not 2.9: the segment began on the cut
    assert [(w.start, w.end) for w in back.words] == [(23.2, 23.5), (23.6, 24.0)]


def test_restored_segments_stay_in_decode_order():
    """Word times jitter across segment boundaries (a lone "!" restored to 778.92, the next
    segment's first word to 778.86 on a real call): a start taken from the first word must not
    fall before the previous segment's, or the transcript fails validation and a whole call's
    text is refused."""
    from parola.asr.mlx_whisper_backend import restore_times
    from parola.audio.silence import Cuts
    from parola.schema import Segment, Word

    cuts = Cuts(at=[3.0], shift=[20.0])
    first = Segment(text="!", start=3.0, end=3.3, words=[Word(text="!", start=3.2, end=3.3)])
    second = Segment(text="e poi", start=3.1, end=3.4,
                     words=[Word(text="e", start=3.15, end=3.2),
                            Word(text="poi", start=3.2, end=3.4)])  # fmt: skip
    a, b = restore_times([first, second], cuts)
    assert (a.start, b.start) == (23.2, 23.2)  # clamped to the decode order, not reordered
    assert b.words[0].start == 23.15  # the words keep their real times
