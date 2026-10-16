# CLAUDE.md

Personal open source project: **verbatim** transcription of audio and calls, **100% local** on Apple Silicon Macs, Italian and English (also mixed in the same sentence).

The full operational plan is in `docs/PLAN.md` (local, not in git). Read it before starting any work.

## What we build

1. A pipeline that takes audio/video and produces a faithful verbatim transcript (fillers, repetitions, truncated words, false starts).
2. A "clean" layer derived from the verbatim one, never the other way around.
3. A Whisper model fine-tuned for IT/EN verbatim, with a test set and a metric dedicated to disfluencies.
4. A local app that records calls (e.g. Google Meet) and transcribes them.

## Non-negotiable principles

- **Everything local.** No network calls at runtime, apart from the initial download of the models. No cloud APIs, no telemetry.
- **The verbatim is the source of truth.** The clean layer is generated from the verbatim with explicit rules. Every clean sentence must trace back to the verbatim words and to the audio (timestamps).
- **The clean layer never adds content.** It can only remove or normalise according to `docs/conventions.md`. It must be tested.
- **Measure first, then change.** No changes to models or parameters without numbers on the test set.
- **Never commit audio or personal data.** `data/raw/`, `data/private/` and every audio file are in `.gitignore`. Recordings are used only with the participants' consent.
- **Licences tracked.** Every data source has its licence recorded in the manifest. The licence of the model weights depends on the data used to train it.
- **No remote assets at runtime.** Fonts, icons, images and JS/CSS libraries must be included in the repo or in the bundle. No CDNs, Google Fonts or remote images in the app, even if a skill suggests them.

## Stack

- Python 3.11+, environment managed with `uv`; `ruff` for lint and format; `pytest` for tests.
- `ffmpeg` for audio extraction and conversion (16 kHz mono for ASR).
- Inference on Mac: `mlx-whisper`. Other backends (CrisperWhisper, Parakeet) behind the same interface.
- Metrics: `jiwer` plus our own metrics for disfluencies.
- Training (on NVIDIA GPUs, not on the Mac): `transformers` + `peft` (LoRA).
- Clean layer: local LLM via `mlx-lm` or Ollama.
- App v1: FastAPI backend + minimal local web interface; audio capture with BlackHole + `sounddevice`.

## Working rules

- Work **one phase at a time** as per `docs/PLAN.md`. Do not move to the next phase until the "Fatto quando" (done when) criteria are met.
- Tasks marked **[JACOPO]** need a human decision or action: stop and ask, do not make things up.
- **Do not download datasets** without asking first. Do not take a corpus's licence for granted: it must be checked by hand.
- Ask before adding heavy dependencies (e.g. torch in the inference environment).
- The skills in `.claude/skills/` are third-party: before running a script provided by a skill, show what it does and ask.
- Everything is written **in English**: code, comments, docstrings, README, commit messages, and the documents in `docs/` and `results/`. Only the app's interface text is in Italian.
- Every non-obvious design choice must be recorded in `docs/decisions/` (one short file per decision: context, choice, rejected alternatives).
- Metrics have unit tests with hand-built cases: they must be right before the numbers can be trusted.
- Small, descriptive commits; update the status in `docs/PLAN.md` at the end of each phase.
