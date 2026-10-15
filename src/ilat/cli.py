"""Command-line interface: ``ilat transcribe <file>``."""

import argparse
import sys
from pathlib import Path

from ilat import __version__
from ilat.asr import DEFAULT_MODEL, MLXWhisperBackend
from ilat.audio import FFmpegError
from ilat.pipeline import transcribe_file

LANGUAGES = ("auto", "it", "en")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="ilat", description="Local verbatim transcription.")
    parser.add_argument("--version", action="version", version=f"ilat {__version__}")
    sub = parser.add_subparsers(dest="command", required=True)

    t = sub.add_parser("transcribe", help="transcribe an audio or video file")
    t.add_argument("file", type=Path, help="input audio/video file (m4a, mp4, wav, ...)")
    t.add_argument(
        "--lang",
        choices=LANGUAGES,
        default="auto",
        help="force the language or detect it automatically (default: auto)",
    )
    t.add_argument(
        "--out", type=Path, default=None, help="output folder (default: next to the input)"
    )
    t.add_argument(
        "--model", default=DEFAULT_MODEL, help=f"mlx-whisper model (default: {DEFAULT_MODEL})"
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)

    if args.command == "transcribe":
        language = None if args.lang == "auto" else args.lang
        try:
            outputs = transcribe_file(
                args.file, MLXWhisperBackend(args.model), out_dir=args.out, language=language
            )
        except (FileNotFoundError, FFmpegError) as e:
            print(f"error: {e}", file=sys.stderr)
            return 1
        print(f"wrote {outputs.json_path}")
        print(f"wrote {outputs.txt_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
