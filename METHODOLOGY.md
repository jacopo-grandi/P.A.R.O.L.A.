# Methodology

How P.A.R.O.L.A. decides what a transcript should be, how it is measured and why each model and
setting was chosen. Each choice has a short decision note in [`docs/decisions/`](docs/decisions/),
and each number links to the report it comes from in [`results/`](results/). The decision notes
and reports are in Italian.

## Principles

- **Everything runs on the Mac.** The network is used once, to download the models. No cloud API,
  no telemetry.
- **The verbatim transcript is the source of truth.** Anything derived from it (a clean version,
  key phrases, a title) can only remove or normalise, never add, and every word traces back to a
  timestamp in the audio.
- **Fidelity over pure verbatim.** Losing an "ehm" is acceptable; rewriting what was said is not
  (decision [0010](docs/decisions/0010-fidelity-metric.md)). Grammar mistakes stay as spoken.
- **The machine flags, the person decides.** Words the model may have got wrong are marked, and
  only the person corrects them. Nothing is corrected automatically
  ([0014](docs/decisions/0014-doubtful-words.md), [0015](docs/decisions/0015-app-product-direction.md)).
- **Measure before changing.** No model or parameter changes without numbers on the test set.

## Test set and references

- Four recordings with the speakers' consent: it-001 (85 min), it-002 (17 min), en-001 (60 min)
  and en-002 (29 min). They are never committed. Only the manifest is in the repository, with
  each source and its licence ([0004](docs/decisions/0004-training-corpora-licenses.md)).
- The transcription conventions (fillers, truncated words, repetitions, overlaps) are in
  [`docs/conventions.md`](docs/conventions.md). The annotation workflow is in
  [`docs/annotation.md`](docs/annotation.md).
- **References are "silver"**: a model draft checked word by word by a person
  ([0005](docs/decisions/0005-silver-references.md)). The drafts came from Whisper turbo, which
  biases the comparison in turbo's favour. To reduce that bias, it-002 and en-002 were
  **adjudicated**: wherever turbo and CrisperWhisper disagreed, a person listened and chose.
  Clear cases (repetitions, truncated words, extra words actually spoken) were accepted by a
  rule, which was itself checked on samples. In a 30-clip listening audit, 93% of the words
  CrisperWhisper added were really spoken
  ([audit](results/2026-10-15-audit-crisper.md)).
- Current numbers use the two adjudicated files: 0.76 hours. That is small, so the confidence
  intervals are wide and the report shows them.

## Metrics

Three word error rates, from strictest to most lenient
([0008](docs/decisions/0008-evaluation-design.md), [0010](docs/decisions/0010-fidelity-metric.md)):

| Metric | What counts as an error |
|---|---|
| **Fidelity WER** (primary) | Words that are not the ones spoken. Fillers, repetitions, truncated words and false starts are ignored. |
| Literal WER | Like fidelity, but repetitions and truncated words count ([0007](docs/decisions/0007-literal-fidelity-first.md)). |
| Verbatim WER | Everything counts, fillers included, mapped to one spelling per filler. |

Plus filler recall and precision, the share of substitutions (the direct sign of rewording) and
the real-time factor. Numbers are normalised the same way on both sides (for example digits to
words). Confidence intervals come from bootstrapping over segments. Every metric has
hand-built unit tests.

## Models

On the adjudicated references ([report](results/2026-10-15-adjudicated.md); fidelity WER, 95% CI):

| System | Italian | English | Speed (RTF, M4 Pro) | Licence |
|---|---|---|---|---|
| **Whisper large-v3-turbo** (default) | **4.8** [3.6–6.3] | 5.3 [4.3–6.5] | 0.047 | MIT |
| CrisperWhisper 2.0 turbo | 8.5 [6.4–10.7] | **2.7** [2.0–3.6] | 0.159 | non-commercial |
| Parakeet TDT 0.6B v3 | 16.7 | 10.1 | 0.013 | CC BY 4.0 |
| Whisper large-v3 | 27.2 | 21.9 | 0.138 | MIT |

- **Turbo is the default** ([0011](docs/decisions/0011-default-engine-turbo.md)): the best in
  Italian, close in English, fast and freely licensed. It drops almost all fillers, which the
  fidelity metric accepts.
- **CrisperWhisper is optional**: the best in English and the most verbatim (96% filler recall),
  but its weights are non-commercial and it is worse in Italian
  ([0009](docs/decisions/0009-two-models-and-crisperwhisper-license.md)).
- **What did not help:** a "disfluency" prompt (fidelity WER from 5.1 to 7.8 overall) and a
  personal glossary given to Whisper as a prompt (5.1 to 8.6–9.5,
  [report](results/2026-10-16-glossary.md)). The glossary fixed about half of the domain terms
  but made everything else worse. Model runs use a fixed random seed, because Whisper's
  temperature fallback otherwise samples at random.
- **Fine-tuning is parked.** The plan for an English-first LoRA on freely licensed data is in
  [`docs/PLAN.md`](docs/PLAN.md) ([0006](docs/decisions/0006-english-only-training-first.md)).

## Doubtful words

Each call is transcribed twice: by turbo and by Parakeet as a second opinion. The two are aligned
on fidelity tokens, and turbo's words that Parakeet does not confirm are marked as doubtful
([report](results/2026-10-16-doubt-analisi.md)):

- **Parakeet catches 66% of turbo's errors** by marking 12% of the words. Its flags are right 35%
  of the time, five times better than chance (6.5%). It works because it fails in different
  places, and it adds about a minute per hour of audio.
- About a third of the errors stay invisible: the places where both systems make the same
  mistake.
- On a real 30-minute call, recorded with consent, every error noticed in review had been flagged.

In the app, you jump from one doubtful word to the next, hear just that excerpt, and confirm or
correct it. Terms you corrected at least twice (names, acronyms, words rare in the
language spoken) come back as suggestions when you open a similar doubtful word; they are
learned from your own edit logs only, start empty on every install and never change the text
by themselves ([0025](docs/decisions/0025-glossary-learned-from-corrections.md)). Every edit is logged with the model's original words and can be undone; the
untouched model output is kept next to the transcript.

## Recording calls

- **Capture:** Core Audio process taps record the microphone ("Io") and the system audio
  ("Altri") into two files, so speakers are told apart by channel rather than guessed. No
  virtual audio driver is needed ([0013](docs/decisions/0013-capture-with-core-audio-taps.md)).
- **Echo:** a microphone segment whose words are mostly the same as the other channel's at the
  same time (60% or more) is your speakers leaking into the microphone, and is dropped.
- **Voice activity detection:** only stretches with sound are transcribed, to keep Whisper from
  inventing text over silence. Fidelity is unchanged: 5.1 with and without VAD
  ([report](results/2026-10-15-vad.md)). Earlier versions that shifted decoding windows lost
  speech (up to 27.9%) and were dropped ([analysis](results/2026-10-15-vad-analisi.md)).

## Storage

After transcription each channel is stored as FLAC at 16 kHz mono 16-bit: the very signal the
models get, losslessly, at about 100 MB per hour of call instead of about 2 GB. A lossy codec
was measured and rejected: re-encoding the test set as AAC at 32-48 kbps raised turbo's fidelity
WER from about 5% to 9-12%
([0024](docs/decisions/0024-lossless-audio-after-transcription.md)).

## Imported files

An audio or video file dropped into the app goes through the same pipeline as a recording:
conversion to 16 kHz mono, VAD, turbo, Parakeet for the doubtful words, segment merging and the
title. Every voice is on one track (channel `mixed`), so there is no "Io / Altri" split and no
echo removal; telling the voices apart needs speaker diarization, planned after v1
([0021](docs/decisions/0021-import-audio-and-video-files.md)).

## Derived layers

- **Clean version:** only removes material (fillers, repetitions, false starts) by explicit rules,
  never rewrites. A trained classifier is paused
  ([0012](docs/decisions/0012-clean-layer-by-labeling.md)).
- **Title:** key noun phrases chosen without a language model
  ([0020](docs/decisions/0020-title-from-key-phrases.md),
  [0022](docs/decisions/0022-titles-read-like-titles.md),
  [0023](docs/decisions/0023-title-rules-that-generalize.md)), with rules that do not depend on
  any particular call:
  - phrases are cut at closed-class words (articles, prepositions, pronouns, auxiliaries,
    numbers, fillers) and at the most frequent words of Italian or English (Zipf ≥ 6);
  - they are scored by TF-IDF against the language: frequent in the call, rare in general;
  - only noun phrases count: said after a determiner at least 10% of the time, or a name or an
    acronym. This keeps out discourse markers such as "esatto" or "ciao".

  The title joins the two best phrases ("Peperoni rossi e gialli"). Each call keeps the
  suggested title apart from the one the user chose, and `parola titles` compares them, so the
  rules are measured on calls they were never tuned on. Word frequencies come from
  [wordfreq](https://github.com/rspeer/wordfreq) by Robyn Speer (code Apache-2.0, data
  CC BY-SA 4.0).

## Reproducing the numbers

```bash
uv run parola eval                      # all systems on the references in the manifest
uv run parola eval --systems turbo,turbo-vad
uv run --group baselines parola eval --systems crisper-turbo-lang
```

Reports are written to `results/` with the commit they were produced from.

## All decisions

| # | Decision |
|---|---|
| [0001](docs/decisions/0001-python-3.12.md) | Python 3.12 |
| [0002](docs/decisions/0002-phase0-pipeline.md) | Phase 0 pipeline |
| [0003](docs/decisions/0003-schema-and-annotation-format.md) | Transcript schema and annotation format |
| [0004](docs/decisions/0004-training-corpora-licenses.md) | Training corpora and their licences |
| [0005](docs/decisions/0005-silver-references.md) | Silver references |
| [0006](docs/decisions/0006-english-only-training-first.md) | English-only fine-tuning first |
| [0007](docs/decisions/0007-literal-fidelity-first.md) | Literal fidelity first |
| [0008](docs/decisions/0008-evaluation-design.md) | Evaluation design |
| [0009](docs/decisions/0009-two-models-and-crisperwhisper-license.md) | Two models and the CrisperWhisper licence |
| [0010](docs/decisions/0010-fidelity-metric.md) | Fidelity as the primary metric |
| [0011](docs/decisions/0011-default-engine-turbo.md) | Turbo as the default engine |
| [0012](docs/decisions/0012-clean-layer-by-labeling.md) | Clean layer by labelling, classifier paused |
| [0013](docs/decisions/0013-capture-with-core-audio-taps.md) | Capture with Core Audio taps |
| [0014](docs/decisions/0014-doubtful-words.md) | Doubtful words |
| [0015](docs/decisions/0015-app-product-direction.md) | Product direction: flag, let the user correct, then organise |
| [0016](docs/decisions/0016-app-layout-and-floating-recorder.md) | App layout and floating recorder |
| [0017](docs/decisions/0017-delete-to-trash-folder.md) | Deleting a call: app trash with undo |
| [0018](docs/decisions/0018-type-charter-and-sf.md) | Typography: Charter and SF |
| [0019](docs/decisions/0019-rename-to-parola.md) | Rename to P.A.R.O.L.A. |
| [0020](docs/decisions/0020-title-from-key-phrases.md) | Title from key phrases, without a language model |
| [0021](docs/decisions/0021-import-audio-and-video-files.md) | Importing audio and video files |
| [0022](docs/decisions/0022-titles-read-like-titles.md) | Titles that read like titles |
| [0023](docs/decisions/0023-title-rules-that-generalize.md) | Title rules that generalize |
| [0024](docs/decisions/0024-lossless-audio-after-transcription.md) | Lossless audio after transcription |
| [0025](docs/decisions/0025-glossary-learned-from-corrections.md) | Glossary learned from corrections: suggests, never corrects |
