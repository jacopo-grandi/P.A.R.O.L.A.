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

### Writing reference transcripts

```bash
uv run ilat annotate draft call.json         # model output -> editable call.ann.txt
uv run ilat annotate import call.ann.txt     # reviewed annotation -> validated call.ref.json
uv run ilat validate call.ref.json           # check a reference against the conventions
uv run ilat manifest check data/manifests/test.jsonl --files
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
