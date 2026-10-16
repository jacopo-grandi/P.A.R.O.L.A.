"""Which language a recording is in, Italian or English, from Whisper's language guess.

Whisper guesses the language once, on the first 30 s, and then decodes the whole file in it: a
wrong guess turns an hour of English into an Italian translation. The first 30 s are a poor
sample: in a call they can be silence, and an Italian speaking English can sound Italian there.
Gluing the first stretches of speech together (the old probe) made it worse: on en-001 it said
Italian (50% against 43%), while 30 s windows as they are said English at 92-98%. So the guess is
made on ``WINDOWS`` windows of 30 s that start on speech, spread over the whole recording, with
their probabilities averaged, and only Italian and English are candidates: the transcript knows
no other language (results/2026-10-16-language-detection.md, decision 0030).
"""

from __future__ import annotations

from pathlib import Path

import numpy as np

WINDOWS = 5
CANDIDATES = ("it", "en")


def window_starts(regions: list[tuple[float, float]], n: int = WINDOWS) -> list[float]:
    """Where the windows start: ``n`` speech regions spread evenly over the list."""
    if not regions:
        return []
    picks = sorted({int(i) for i in np.linspace(0, len(regions) - 1, n)})
    return [regions[i][0] for i in picks]


def choose(probabilities: list[dict[str, float]]) -> str:
    """The candidate with the highest average probability (Italian when it is a tie)."""
    mean = {c: float(np.mean([p.get(c, 0.0) for p in probabilities])) for c in CANDIDATES}
    return max(CANDIDATES, key=lambda c: mean[c])


def detect(wav_path: Path, regions: list[tuple[float, float]], model: str) -> str:
    """Italian or English, for a 16 kHz mono wav whose sound ``regions`` are known."""
    import mlx.core as mx
    from mlx_whisper.audio import N_FRAMES, N_SAMPLES, log_mel_spectrogram, pad_or_trim
    from mlx_whisper.decoding import detect_language
    from mlx_whisper.transcribe import ModelHolder

    from parola.audio.vad import load_audio

    samples, rate = load_audio(wav_path)
    # The same model and precision mlx_whisper.transcribe uses: loaded once for both.
    whisper = ModelHolder.get_model(model, mx.float16)
    probabilities = []
    for start in window_starts(regions):
        chunk = mx.array(samples[int(start * rate) : int(start * rate) + N_SAMPLES])
        mel = log_mel_spectrogram(pad_or_trim(chunk), n_mels=whisper.dims.n_mels)
        mel = pad_or_trim(mel, N_FRAMES, axis=-2)
        _, probs = detect_language(whisper, mel[None].astype(mx.float16))
        probabilities.append(probs[0])
    return choose(probabilities) if probabilities else CANDIDATES[0]
