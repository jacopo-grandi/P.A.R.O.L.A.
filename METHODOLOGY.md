# Methodology

How P.A.R.O.L.A. decides what a transcript should be, how it is measured and why each model and
setting was chosen. Each choice has a short decision note in [`docs/decisions/`](docs/decisions/),
and each number links to the report it comes from in [`results/`](results/).

## Summary

P.A.R.O.L.A. transcribes Italian and English speech, calls and imported files, entirely on an
Apple Silicon Mac. It keeps what was said, as it was said: repetitions, truncations and false
starts stay, and grammar is not fixed. Whisper large-v3-turbo writes the transcript (fidelity
WER 4.8% in Italian and 5.3% in English on adjudicated references), a second model, Parakeet v3,
marks the words it does not confirm (66% of turbo's errors flagged by marking 12% of the words),
and the person reviews only those. Calls are recorded on two channels, so "me" and "the others"
are never guessed; within a channel, voices are told apart by sherpa-onnx with our own spectral
clustering (diarization error 30% on two AMI meetings). An hour of audio takes about 8 minutes on
an M4 Pro, with a memory peak of about 6 GB. The test set is small (0.76 hours of adjudicated
references), and the limitations are listed at the end.

## Pipeline

Each stage, with what it costs on an hour of audio (en-001, M4 Pro,
[0031](docs/decisions/0031-provisional-text-after-whisper.md)):

| Stage | What it does | Time per hour |
|---|---|---|
| Capture or import | Two channels from Core Audio taps, or any audio or video file, to 16 kHz mono | real time / seconds |
| Language | Italian or English, from 5 windows spread over the audio, unless the person chose it | 2 s |
| Voice activity | Finds the stretches with sound; text over silence is dropped | seconds |
| Transcript | Whisper large-v3-turbo, word timestamps; the text is shown as it grows | 3:00 |
| Doubtful words | Parakeet TDT 0.6B v3 as a second opinion, aligned word by word | 1:14 |
| Echo, segments | Drops the others' voice leaking into the microphone; joins short segments | seconds |
| Who speaks | sherpa-onnx pieces, regrouped by spectral clustering | 3:23 |
| Title, storage | Key-phrase title; lossless FLAC | seconds |

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
- **Fine-tuning is parked.** The plan, an English-first LoRA on freely licensed data, is in
  [0006](docs/decisions/0006-english-only-training-first.md).

## Language

Whisper picks one language and transcribes the whole file in it. If it picks wrong, it does not
transcribe: an hour of English came out as an Italian translation. Its own guess looks at the
first 30 seconds only, and our earlier probe (the first 30 seconds of speech glued together)
said Italian for an Italian speaking English. Now the guess is the average of Whisper's language
probabilities on 5 raw 30-second windows that start on speech, spread over the whole recording,
and only Italian and English can win. On the four test-set files: 4 of 4 right, against 3 of 4,
in 1.9 seconds; the language of it-002 and en-002 does not change, so their error rates do not
either ([0030](docs/decisions/0030-language-from-windows-and-asked-on-import.md),
[report](results/2026-10-16-language-detection.md)). When a file is imported the app asks its
language first (Italiano, English or detect), since the person usually knows it.

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

## Who speaks

The others' channel and imported files can hold several voices. After transcription, sherpa-onnx
(pyannote segmentation 3.0, MIT; WeSpeaker VoxCeleb ResNet34-LM, CC BY 4.0; about 70 MB in all,
CPU only) finds where someone speaks; its pieces are regrouped by our own spectral clustering
(NME-SC) over 3-second voice prints. On two AMI test meetings this gets the diarization error
rate from 47% (sherpa-onnx alone) to 30%; pyannote reports 17-19% on the whole AMI test set.
Voices show as "Altri 1", "Altri 2"..., can be named, and every turn can be moved to another
voice and undone ([0026](docs/decisions/0026-who-speaks-with-sherpa-onnx.md),
[results](results/2026-10-16-diarization-sherpa.md)).

## Time and memory

An hour of audio takes about 7 minutes 50 seconds on an M4 Pro (stages in "Pipeline"). Only one
speech model is in memory at a time, and none between calls: for a 6-minute file the peak goes
from 11.5 GB to 6.1 GB and the waiting server from 10 GB to 0.27 GB, with the same time and the
same transcript ([0027](docs/decisions/0027-release-speech-models-after-use.md)).

The person does not wait for the end to read. Each 30-second window Whisper decodes is shown as
soon as it is done, then the doubtful words, then the voices; the text can be corrected once it is
final. The windows are read from Whisper's own decoding loop without changing it: on en-002 the
final transcript is identical, word for word with the same times, doubtful words and voices,
to the one made before ([0031](docs/decisions/0031-provisional-text-after-whisper.md),
[0033](docs/decisions/0033-text-grows-while-whisper-works.md)).

## Storage

After transcription each channel is stored as FLAC at 16 kHz mono 16-bit: the very signal the
models get, losslessly, at about 100 MB per hour of call instead of about 2 GB. A lossy codec
was measured and rejected: re-encoding the test set as AAC at 32-48 kbps raised turbo's fidelity
WER from about 5% to 9-12%
([0024](docs/decisions/0024-lossless-audio-after-transcription.md)).

Clicking a word plays the audio from there, so the player must land on the right second. The
native app's window is WebKit, and WebKit cannot seek in FLAC: on an hour-long test file with a
beep on every minute, after a jump the beep came tens of seconds late or not at all, with or
without a FLAC seek table, while in WAV it came where expected; Chrome was exact (±0.02 s) on
both. Calls stay FLAC on disk, and the player gets a WAV copy decoded when the call is opened
(0.6 s per hour), of which only the last three are kept
([0032](docs/decisions/0032-play-wav-copies-of-flac-calls.md),
[report](results/2026-10-16-flac-seeking.md)).

## Imported files

An audio or video file dropped into the app goes through the same pipeline as a recording:
conversion to 16 kHz mono, VAD, turbo, Parakeet for the doubtful words, segment merging and the
title, after the language question above. Every voice is on one track (channel `mixed`), so
there is no "Io / Altri" split and no echo removal; the voices are told apart as in "Who speaks"
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

## Limitations

- **A small test set.** The error rates come from 0.76 hours on two files, one per language;
  the confidence intervals are wide. it-001 and en-001 have no
  reference yet.
- **Silver references.** The references started as turbo drafts. Adjudication against
  CrisperWhisper reduces the bias towards turbo but does not remove it.
- **Same mistakes are invisible.** About a third of turbo's errors are not flagged, because
  Parakeet makes the same mistake. On accented English (en-001, an Italian speaker) 24% of the
  words are flagged, twice the test-set rate; this has not been analysed yet.
- **Voices measured on English meetings only.** The diarization error comes from two AMI
  meetings recorded in a room in 2005: no Meet audio, no Italian, and no reference on real calls.
  On en-001, a lecture, the voices alternate as if there were two speakers; not checked yet.
- **Language on four files.** The 5-window detection is checked on four recordings, none of them
  mixed Italian and English.
- **One machine.** Times and memory are measured on an M4 Pro with 24 GB. Macs with 8 GB and
  Windows are not covered.
- **Playback precision.** Seeking in WebKit was measured with Web Audio inside the page, which
  adds a variable delay at start; the WAV lands "where expected" (within about a second), not
  "to the hundredth".

## Third-party models and data

| What | Used for | Licence | Size |
|---|---|---|---|
| Whisper large-v3-turbo (MLX conversion) | transcript | MIT | 1.6 GB |
| Parakeet TDT 0.6B v3 (MLX conversion) | doubtful words | CC BY 4.0 | 2.5 GB |
| pyannote segmentation 3.0 (sherpa-onnx export) | who speaks | MIT | 6 MB |
| WeSpeaker VoxCeleb ResNet34-LM | who speaks | CC BY 4.0 | 27 MB |
| wordfreq | titles, glossary | Apache-2.0 (data CC BY-SA 4.0) | in the package |
| CrisperWhisper 2.0 (optional, evaluation only) | comparison | non-commercial | not bundled |

The models are downloaded once, when the person agrees in the app; the two voice models are
checked by SHA-256 ([0029](docs/decisions/0029-install-from-the-repo-folder.md)).

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
| [0026](docs/decisions/0026-who-speaks-with-sherpa-onnx.md) | Who speaks: sherpa-onnx with our own grouping, fixable by hand |
| [0027](docs/decisions/0027-release-speech-models-after-use.md) | Release the speech models after use |
| [0028](docs/decisions/0028-native-mac-app-shell.md) | Native app: a Swift shell around the Python engine |
| [0029](docs/decisions/0029-install-from-the-repo-folder.md) | Install from the repository folder; models asked on first start |
| [0030](docs/decisions/0030-language-from-windows-and-asked-on-import.md) | Language: asked on import, detected on 5 windows |
| [0031](docs/decisions/0031-provisional-text-after-whisper.md) | Provisional text once Whisper is done |
| [0032](docs/decisions/0032-play-wav-copies-of-flac-calls.md) | The player gets WAV, calls stay FLAC |
| [0033](docs/decisions/0033-text-grows-while-whisper-works.md) | The text grows while Whisper works |
