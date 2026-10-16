"""Run systems on the test set and write the comparison report (markdown + csv)."""

from __future__ import annotations

import csv
import json
import subprocess
import time
from collections import defaultdict
from dataclasses import dataclass
from datetime import date
from pathlib import Path

from parola.asr.mlx_whisper_backend import SEED
from parola.eval.metrics import (
    DISFLUENCY_TAGS,
    Counts,
    SegmentScore,
    bootstrap_ci,
    score_transcript,
    wer_of,
)
from parola.eval.normalize import METRICS
from parola.eval.systems import System
from parola.manifest import ManifestRecord
from parola.pipeline import transcribe_file
from parola.schema import Transcript

METRIC_LABELS = {"fidelity": "fidelity WER", "literal": "literal WER",
                 "verbatim": "verbatim WER"}  # fmt: skip


def run_system(
    system: System,
    records: list[ManifestRecord],
    root: Path,
    hyp_dir: Path,
    force: bool = False,
    seed: int = SEED,
) -> dict[str, float]:
    """Transcribe every record with ``system``; cached in ``hyp_dir/<system>/<id>.json``.

    Returns the processing time in seconds of the files transcribed in this call.
    """
    out_dir = hyp_dir / system.name
    timing_path = out_dir / "_timing.json"
    timing = json.loads(timing_path.read_text()) if timing_path.exists() else {}
    for r in records:
        audio = root / r.audio
        target = out_dir / f"{audio.stem}.json"
        if target.exists() and not force:
            continue
        t0 = time.perf_counter()
        transcribe_file(audio, system.backend(r.lang, seed), out_dir=out_dir,
                        language=system.language(r.lang))  # fmt: skip
        timing[r.id] = time.perf_counter() - t0
        timing_path.write_text(json.dumps(timing, indent=2))
    return timing


@dataclass
class Row:
    system: str
    scope: str
    values: dict[str, float | None]


def _scope_rows(system: str, scope: str, scores: list[SegmentScore], seconds: float | None,
                audio_seconds: float) -> Row:  # fmt: skip
    v: dict[str, float | None] = {}
    for m in METRICS:
        v[m] = wer_of(scores, m)
        ci = bootstrap_ci(scores, m)
        v[f"{m}_lo"], v[f"{m}_hi"] = ci if ci else (None, None)
    # Error types of the primary metric: substitutions are the direct sign of rewriting.
    f = sum((s.wer["fidelity"] for s in scores), Counts())
    v["fidelity_ref_words"] = f.ref_words
    v["fidelity_sub"], v["fidelity_del"], v["fidelity_ins"] = (f.substitutions, f.deletions,
                                                               f.insertions)  # fmt: skip
    d = sum((s.disfluency for s in scores[1:]), scores[0].disfluency) if scores else None
    for tag in DISFLUENCY_TAGS:
        v[f"{tag}_ref"] = d.ref[tag] if d else 0
        v[f"{tag}_kept"] = d.kept[tag] if d else 0
        v[f"{tag}_recall"] = d.kept[tag] / d.ref[tag] if d and d.ref[tag] else None
    v["hyp_fillers"] = d.hyp_fillers if d else 0
    v["invented_fillers"] = d.invented_fillers if d else 0
    v["filler_precision"] = (
        (d.hyp_fillers - d.invented_fillers) / d.hyp_fillers if d and d.hyp_fillers else None
    )
    v["ref_words_literal"] = sum(s.wer["literal"].ref_words for s in scores)
    v["segments"] = len(scores)
    v["rtf"] = seconds / audio_seconds if seconds and audio_seconds else None
    return Row(system, scope, v)


def score_system(
    system: System, records: list[ManifestRecord], root: Path, hyp_dir: Path,
    timing: dict[str, float],
) -> list[Row]:  # fmt: skip
    per_file: dict[str, list[SegmentScore]] = {}
    for r in records:
        ref = Transcript.load(root / r.reference)
        hyp = Transcript.load(hyp_dir / system.name / f"{Path(r.audio).stem}.json")
        per_file[r.id] = score_transcript(ref, hyp)

    def scope(name: str, rs: list[ManifestRecord]) -> Row:
        scores = [s for r in rs for s in per_file[r.id]]
        secs = [timing.get(r.id) for r in rs]
        seconds = sum(secs) if all(s is not None for s in secs) else None
        return _scope_rows(system.name, name, scores, seconds, sum(r.duration for r in rs))

    rows = [scope("all", records)]
    by_lang: dict[str, list[ManifestRecord]] = defaultdict(list)
    for r in records:
        by_lang[r.lang].append(r)
    rows += [scope(f"lang:{lang}", rs) for lang, rs in sorted(by_lang.items())]
    rows += [scope(r.id, [r]) for r in records]
    return rows


def _pct(v: float | None) -> str:
    return "—" if v is None else f"{v * 100:.1f}"


def _ratio(a: float | None, b: float | None) -> float | None:
    return a / b if a is not None and b else None


def _wer_cell(row: Row, m: str) -> str:
    v, lo, hi = row.values[m], row.values[f"{m}_lo"], row.values[f"{m}_hi"]
    return "—" if v is None else f"{_pct(v)} [{_pct(lo)}-{_pct(hi)}]"


def write_report(
    rows: list[Row], systems: list[System], records: list[ManifestRecord], out: Path
) -> tuple[Path, Path]:
    out.parent.mkdir(parents=True, exist_ok=True)
    csv_path, md_path = out.with_suffix(".csv"), out.with_suffix(".md")
    keys = list(rows[0].values) if rows else []
    with csv_path.open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["system", "scope", *keys])
        for r in rows:
            w.writerow([r.system, r.scope, *("" if r.values[k] is None else r.values[k]
                                               for k in keys)])  # fmt: skip

    try:
        commit = subprocess.run(["git", "rev-parse", "--short", "HEAD"], capture_output=True,
                                text=True, check=False).stdout.strip()  # fmt: skip
    except OSError:
        commit = ""
    hours = sum(r.duration for r in records) / 3600
    lines = [
        f"# Baseline — {date.today().isoformat()}",
        "",
        f"Commit `{commit or '?'}`. Generated by `parola eval`. Values in %, with the 95% "
        "confidence interval in brackets (bootstrap over segments).",
        "",
        f"**References** ({len(records)} files, {hours:.2f} h): "
        + ", ".join(
            f"{r.id} ({r.lang}, {r.duration / 60:.0f} min, {r.reference_quality})" for r in records
        )
        + ".",
        "",
        "## Systems",
        "",
        *[f"- `{s.name}`: {s.description}" for s in systems],
        "",
        "## Results",
        "",
        "| System | Scope | **Fidelity WER** | subst. | Literal WER | Verbatim WER | "
        "Filler recall | Filler precision | RTF |",
        "|---|---|---|---|---|---|---|---|---|",
    ]
    for r in rows:
        rtf = r.values["rtf"]
        lines.append(
            f"| `{r.system}` | {r.scope} | **{_wer_cell(r, 'fidelity')}** | "
            f"{_pct(_ratio(r.values['fidelity_sub'], r.values['fidelity_ref_words']))} | "
            f"{_wer_cell(r, 'literal')} | "
            f"{_wer_cell(r, 'verbatim')} | {_pct(r.values['filler_recall'])} | "
            f"{_pct(r.values['filler_precision'])} | {'—' if rtf is None else f'{rtf:.3f}'} |"
        )
    lines += [
        "",
        "## Disfluencies kept (all files)",
        "",
        "| System | " + " | ".join(DISFLUENCY_TAGS) + " | invented fillers |",
        "|---|" + "---|" * (len(DISFLUENCY_TAGS) + 1),
    ]
    for r in (r for r in rows if r.scope == "all"):
        cells = [f"{int(r.values[f'{t}_kept'])}/{int(r.values[f'{t}_ref'])}"
                 for t in DISFLUENCY_TAGS]  # fmt: skip
        lines.append(f"| `{r.system}` | " + " | ".join(cells)
                     + f" | {int(r.values['invented_fillers'])} |")  # fmt: skip
    lines += [
        "",
        "## How to read the numbers",
        "",
        "- **Fidelity WER** is the primary metric (decision 0010): it counts whether the words "
        "are the ones spoken, without rewording; fillers, repetitions, truncated words and "
        "false starts do not count. **subst.** = substitutions as a % of the words: the direct "
        "sign of rewording.",
        "- **Literal WER**: only fillers are removed; repetitions and truncated words count.",
        "- **RTF**: processing time / audio duration, on the Mac (M4 Pro).",
        "- **Reproducibility**: fixed MLX random seed (0). Whisper's temperature fallback "
        "samples at random: without a seed, two runs of the same system give different numbers.",
        "- **Silver references**: words checked by a person, fillers mostly proposed by "
        "Whisper large-v3-turbo. The filler metrics are optimistic for the turbo variants, "
        "especially with the prompt.",
        "- **Anchoring**: the references start from the large-v3-turbo draft, so the turbo "
        "systems have an advantage over the other models.",
        "- With few references the intervals are wide: differences within the intervals are "
        "not significant.",
    ]
    md_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return md_path, csv_path
