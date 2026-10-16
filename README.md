# ilat — Italian Audio Transcriptor

Verbatim transcription of audio and calls, **100% local** on Apple Silicon Macs, for Italian and
English (including both mixed in the same sentence).

"Verbatim" means hesitations, repetitions, truncated words and false starts are kept. A clean
layer will be derived from the verbatim one, never the other way around.

Status: early development (Phase 1, see [`docs/PLAN.md`](docs/PLAN.md)).

## Requirements

- macOS on Apple Silicon
- [uv](https://docs.astral.sh/uv/) and [ffmpeg](https://ffmpeg.org/): `brew install uv ffmpeg`

## Setup

```bash
uv sync
uv run pre-commit install
```

The first transcription downloads `mlx-community/whisper-large-v3-turbo` (~1.6 GB) from
Hugging Face into the local cache. After that, nothing goes over the network.

## Usage

```bash
uv run ilat transcribe path/to/call.m4a            # language auto-detected
uv run ilat transcribe path/to/call.mp4 --lang it  # force Italian
uv run ilat transcribe call.m4a --out transcripts/
```

Writes `<name>.json` (segments and words with timestamps) and `<name>.txt` (readable, one line
per segment) next to the input, or into `--out`.

### Recording a call

```bash
uv run ilat record                       # Ctrl-C to stop; files in data/private/calls/
```

Records your microphone ("Io") and the system audio ("Altri") with Core Audio taps (macOS 14.2+,
no virtual driver), transcribes each side with Whisper turbo and marks the words a second
transcription (Parakeet v3) does not confirm as `(doubtful?)` in the text. The first run asks for
the microphone and system-audio recording permissions. Once the models are downloaded, nothing
goes over the network.

### Reading the transcripts

```bash
uv run ilat serve                        # http://127.0.0.1:8765, local only
```

Lists the recorded calls; in a call, doubtful words are highlighted and a click on a word plays
the audio of that side from there. N opens the next doubtful word (it plays and becomes editable):
Enter saves the correction (unchanged text confirms it) and moves on, Esc cancels, a double click
edits any word, Cmd-Z undoes. Every change is logged with the model's original text, which is also
kept as `<name>.asr.json`. Export as txt, md, docx, json, or PDF through the browser's print.

### Writing reference transcripts

```bash
uv run ilat annotate draft call.json         # model output -> editable call.ann.txt
uv run ilat annotate import call.ann.txt     # reviewed annotation -> validated call.ref.json
uv run ilat validate call.ref.json           # check a reference against the conventions
uv run ilat manifest check data/manifests/test.jsonl --files
```

### Evaluating ASR systems

```bash
uv run ilat eval                                  # all systems, references in the manifest
uv sync --group baselines                         # optional: Parakeet v3 and CrisperWhisper 2.0
uv run --group baselines ilat eval --systems parakeet-v3,crisper-turbo-lang
```

Reports go to `results/` (markdown + csv); hypotheses are cached in `data/private/hyp/`.
CrisperWhisper weights are under a non-commercial research license: evaluation only.

To check whether a system's extra words were really spoken (references may have missed them):

```bash
uv run ilat audit build --system crisper-turbo-lang   # clips + local page in data/private/audit/
uv run ilat audit summary audit-answers.json          # after exporting the answers from the page
```

Transcription rules: [`docs/conventions.md`](docs/conventions.md). Annotation guide:
[`docs/annotation.md`](docs/annotation.md) (both in Italian).

## Development

```bash
uv run pytest            # fast tests
uv run pytest -m slow    # also runs the real model on synthetic speech
uv run ruff check . && uv run ruff format .
```

Audio files and anything under `data/` (except `data/manifests/`) are ignored by git and
blocked by a pre-commit hook. Never commit recordings or personal data.

## License

Code: [MIT](LICENSE). The license of fine-tuned model weights will depend on the training data.
