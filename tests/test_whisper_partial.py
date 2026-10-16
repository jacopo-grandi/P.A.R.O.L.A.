"""The segments Whisper has decoded so far, read from its loop without changing it."""

import sys

import pytest

from parola.asr.mlx_whisper_backend import whisper_progress

pytest.importorskip("mlx_whisper")


def fake_transcribe():
    # The shape of mlx_whisper.transcribe's loop: a window's segments are added to
    # all_segments, then the progress bar is updated.
    module = sys.modules["mlx_whisper.transcribe"]
    all_segments = []
    with module.tqdm.tqdm(total=20) as pbar:
        for k in range(2):
            all_segments.extend([{"id": k, "text": f"finestra {k}"}])
            pbar.update(10)
    return all_segments


def test_each_window_hands_over_the_segments_so_far():
    shares, seen = [], []
    with whisper_progress(shares.append, seen.append):
        result = fake_transcribe()
    assert shares == [0.5, 1.0]
    assert [[s["text"] for s in so_far] for so_far in seen] == [
        ["finestra 0"],
        ["finestra 0", "finestra 1"],
    ]
    assert seen[0] is not result  # a copy: later windows do not change what was handed over


def test_only_the_text_without_a_progress_callback():
    seen = []
    with whisper_progress(None, seen.append):
        fake_transcribe()
    assert len(seen) == 2


def test_the_real_loop_still_has_what_the_growing_text_reads():
    # Fails when an upgrade of mlx_whisper (pinned in uv.lock) changes the loop that
    # whisper_progress reads: then fix whisper_progress or drop the growing text (decision 0033).
    import inspect

    import mlx_whisper.transcribe as module

    source = inspect.getsource(module.transcribe)
    added, updated = source.find("all_segments.extend("), source.find("pbar.update(")
    assert 0 <= added < updated
