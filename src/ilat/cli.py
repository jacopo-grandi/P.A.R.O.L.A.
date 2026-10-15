"""Command-line interface.

ilat transcribe <file>              audio/video -> <name>.json + <name>.txt
ilat validate <transcript.json>     check a reference against docs/conventions.md
ilat annotate draft <asr.json>      ASR transcript -> editable <name>.ann.txt
ilat annotate import <name.ann.txt> edited annotation -> validated <name>.ref.json
ilat manifest check <file.jsonl>    validate a dataset manifest
"""

import argparse
import sys
from pathlib import Path

from pydantic import ValidationError

from ilat import __version__
from ilat.annotate import AnnotationError, from_annotation, to_annotation
from ilat.asr import DEFAULT_MODEL, MLXWhisperBackend
from ilat.audio import FFmpegError
from ilat.manifest import check_manifest
from ilat.pipeline import transcribe_file
from ilat.schema import Transcript
from ilat.schema.lint import has_errors, lint

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

    v = sub.add_parser("validate", help="check a reference transcript against the conventions")
    v.add_argument("file", type=Path)

    a = sub.add_parser("annotate", help="write references by hand")
    asub = a.add_subparsers(dest="action", required=True)
    d = asub.add_parser("draft", help="turn an ASR transcript into an editable annotation file")
    d.add_argument("file", type=Path, help="transcript JSON produced by `ilat transcribe`")
    d.add_argument("-o", "--out", type=Path, default=None, help="default: <name>.ann.txt")
    d.add_argument("--force", action="store_true", help="overwrite an existing file")
    i = asub.add_parser("import", help="convert an edited annotation file to a reference JSON")
    i.add_argument("file", type=Path, help="annotation file (.ann.txt)")
    i.add_argument("-o", "--out", type=Path, default=None, help="default: <name>.ref.json")

    m = sub.add_parser("manifest", help="dataset manifests")
    msub = m.add_subparsers(dest="action", required=True)
    c = msub.add_parser("check", help="validate a manifest")
    c.add_argument("file", type=Path)
    c.add_argument("--root", type=Path, default=Path("."), help="repository root (default: .)")
    c.add_argument("--files", action="store_true", help="also open audio and reference files")
    return parser


def _strip_suffixes(path: Path, *suffixes: str) -> str:
    name = path.name
    for s in suffixes:
        if name.endswith(s):
            return name[: -len(s)]
    return path.stem


def _print_issues(issues) -> None:
    for issue in issues:
        print(issue, file=sys.stderr)


def cmd_transcribe(args) -> int:
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


def cmd_validate(args) -> int:
    transcript = Transcript.load(args.file)
    issues = lint(transcript)
    _print_issues(issues)
    n_err = sum(i.severity == "error" for i in issues)
    print(f"{args.file}: {n_err} errors, {len(issues) - n_err} warnings")
    return 1 if n_err else 0


def cmd_annotate_draft(args) -> int:
    out = args.out or args.file.with_name(_strip_suffixes(args.file, ".json") + ".ann.txt")
    if out.exists() and not args.force:
        print(f"error: {out} exists (use --force to overwrite)", file=sys.stderr)
        return 1
    out.write_text(to_annotation(Transcript.load(args.file), draft=True), encoding="utf-8")
    print(f"wrote {out}")
    return 0


def cmd_annotate_import(args) -> int:
    try:
        transcript = from_annotation(args.file.read_text(encoding="utf-8"))
    except AnnotationError as e:
        print(f"error: {args.file}: {e}", file=sys.stderr)
        return 1
    issues = lint(transcript)
    _print_issues(issues)
    if has_errors(issues):
        print("not written: fix the errors above and import again", file=sys.stderr)
        return 1
    out = args.out or args.file.with_name(_strip_suffixes(args.file, ".ann.txt") + ".ref.json")
    transcript.save(out)
    print(f"wrote {out}")
    return 0


def cmd_manifest_check(args) -> int:
    report = check_manifest(args.file, args.root, check_files=args.files)
    for w in report.warnings:
        print(f"warning: {w}", file=sys.stderr)
    for e in report.errors:
        print(f"error: {e}", file=sys.stderr)
    print(report.summary())
    return 1 if report.errors else 0


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    handlers = {
        ("transcribe", None): cmd_transcribe,
        ("validate", None): cmd_validate,
        ("annotate", "draft"): cmd_annotate_draft,
        ("annotate", "import"): cmd_annotate_import,
        ("manifest", "check"): cmd_manifest_check,
    }
    try:
        return handlers[(args.command, getattr(args, "action", None))](args)
    except (FileNotFoundError, ValidationError) as e:
        print(f"error: {e}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
