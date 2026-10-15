"""Command-line interface.

ilat transcribe <file>              audio/video -> <name>.json + <name>.txt
ilat validate <transcript.json>     check a reference against docs/conventions.md
ilat annotate draft <asr.json>      ASR transcript -> editable <name>.ann.txt
ilat annotate import <name.ann.txt> edited annotation -> validated <name>.ref.json
ilat manifest check <file.jsonl>    validate a dataset manifest
ilat eval [--systems a,b]           run ASR systems on the test set and write a report
"""

import argparse
import sys
from datetime import date
from pathlib import Path

from pydantic import ValidationError

from ilat import __version__
from ilat.annotate import AnnotationError, from_annotation, merge_segments, to_annotation
from ilat.asr import DEFAULT_MODEL, MLXWhisperBackend
from ilat.audio import FFmpegError
from ilat.eval.report import run_system, score_system, write_report
from ilat.eval.systems import SYSTEMS
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
    d.add_argument(
        "--merge-gap",
        type=float,
        default=1.0,
        help="join segments separated by at most this many seconds, up to 30 s (default: 1.0)",
    )
    d.add_argument("--no-merge", action="store_true", help="keep the ASR segments as they are")
    i = asub.add_parser("import", help="convert an edited annotation file to a reference JSON")
    i.add_argument("file", type=Path, help="annotation file (.ann.txt)")
    i.add_argument("-o", "--out", type=Path, default=None, help="default: <name>.ref.json")

    m = sub.add_parser("manifest", help="dataset manifests")
    msub = m.add_subparsers(dest="action", required=True)
    c = msub.add_parser("check", help="validate a manifest")
    c.add_argument("file", type=Path)
    c.add_argument("--root", type=Path, default=Path("."), help="repository root (default: .)")
    c.add_argument("--files", action="store_true", help="also open audio and reference files")

    e = sub.add_parser("eval", help="run ASR systems on the test set and write a report")
    e.add_argument(
        "--systems",
        default=",".join(SYSTEMS),
        help=f"comma-separated systems (default: all of {', '.join(SYSTEMS)})",
    )
    e.add_argument("--manifest", type=Path, default=Path("data/manifests/test.jsonl"))
    e.add_argument("--root", type=Path, default=Path("."), help="repository root (default: .)")
    e.add_argument("--hyp-dir", type=Path, default=Path("data/private/hyp"))
    e.add_argument("--out", type=Path, default=None, help="default: results/<date>-baseline")
    e.add_argument("--force", action="store_true", help="re-run cached transcriptions")
    e.add_argument(
        "--seed", type=int, default=0, help="random seed for decoding (use another --hyp-dir)"
    )
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
    transcript = Transcript.load(args.file)
    n_asr = len(transcript.segments)
    if not args.no_merge:
        transcript = merge_segments(transcript, max_gap=args.merge_gap)
    out.write_text(to_annotation(transcript, draft=True), encoding="utf-8")
    print(f"wrote {out} ({len(transcript.segments)} segments from {n_asr})")
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


def cmd_eval(args) -> int:
    names = [n.strip() for n in args.systems.split(",") if n.strip()]
    unknown = [n for n in names if n not in SYSTEMS]
    if unknown:
        print(f"error: unknown systems {unknown}; known: {list(SYSTEMS)}", file=sys.stderr)
        return 1
    report = check_manifest(args.manifest, args.root, check_files=True)
    if report.errors:
        for e in report.errors:
            print(f"error: {e}", file=sys.stderr)
        return 1
    records = [r for r in report.records if r.reference is not None]
    if not records:
        print("error: no references in the manifest", file=sys.stderr)
        return 1
    systems = [SYSTEMS[n] for n in names]
    rows = []
    for system in systems:
        print(f"[{system.name}] transcribing {len(records)} files (cached ones are skipped)")
        timing = run_system(
            system, records, args.root, args.hyp_dir, force=args.force, seed=args.seed
        )
        rows += score_system(system, records, args.root, args.hyp_dir, timing)
    out = args.out or Path("results") / f"{date.today().isoformat()}-baseline"
    md, csv_path = write_report(rows, systems, records, out)
    print(f"wrote {md}")
    print(f"wrote {csv_path}")
    return 0


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    handlers = {
        ("transcribe", None): cmd_transcribe,
        ("validate", None): cmd_validate,
        ("annotate", "draft"): cmd_annotate_draft,
        ("annotate", "import"): cmd_annotate_import,
        ("manifest", "check"): cmd_manifest_check,
        ("eval", None): cmd_eval,
    }
    try:
        return handlers[(args.command, getattr(args, "action", None))](args)
    except (FileNotFoundError, ValidationError) as e:
        print(f"error: {e}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
