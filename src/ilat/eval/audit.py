"""Listening audit of a system's insertions.

When a system writes words that the reference does not have, either the system invented them
or the reference missed them (silver references are anchored to Whisper turbo's draft). This
module samples such insertions, cuts an audio clip around each one and writes a local HTML
page where a person marks them as true (really spoken) or false. The answers estimate how
much of the system's WER is due to the reference.
"""

from __future__ import annotations

import html
import json
import random
import subprocess
from collections import Counter, defaultdict
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Literal

from ilat.eval.metrics import align, assign_words
from ilat.eval.normalize import Token, tokenize
from ilat.schema import Transcript, format_timestamp

Category = Literal["repetition", "truncated", "filler", "other"]
CATEGORIES: tuple[Category, ...] = ("repetition", "truncated", "filler", "other")
DEFAULT_QUOTAS: dict[Category, int] = {"repetition": 10, "truncated": 6, "filler": 8,
                                       "other": 6}  # fmt: skip
CONTEXT_WORDS = 6
CLIP_PADDING = 2.0
ANSWERS = ("vero", "falso", "non so")


@dataclass
class Insertion:
    file_id: str
    category: Category
    word: str
    start: float
    end: float
    hyp_context: str  # with the inserted word between ⟦ ⟧
    ref_context: str
    item_id: str = ""


def _category(h: list[Token], j: int) -> Category:
    t = h[j]
    if t.is_filler:
        return "filler"
    if t.text.endswith("-"):
        return "truncated"
    if (j > 0 and h[j - 1].text == t.text) or (j + 1 < len(h) and h[j + 1].text == t.text):
        return "repetition"
    return "other"


def find_insertions(file_id: str, ref: Transcript, hyp: Transcript) -> list[Insertion]:
    """Insertions of the verbatim alignment, with time and context."""
    out = []
    for seg, hyp_words in zip(ref.segments, assign_words(ref, hyp), strict=True):
        if seg.overlap:
            continue
        lang = seg.lang or "it"
        r = tokenize(seg.words, lang, "verbatim", "ref")
        h = tokenize(hyp_words, lang, "verbatim", "hyp")
        _, pairs = align(r, h)
        last_ref = 0
        for op, i, j in pairs:
            if i >= 0:
                last_ref = i
            if op != "insert":
                continue
            w = hyp_words[h[j].word_index]
            if w.start is None or w.end is None:
                continue
            lo, hi = max(0, j - CONTEXT_WORDS), j + CONTEXT_WORDS + 1
            hyp_ctx = " ".join(
                f"⟦{t.text}⟧" if k == j else t.text for k, t in enumerate(h[lo:hi], start=lo)
            )
            ref_ctx = " ".join(t.text for t in r[max(0, last_ref - CONTEXT_WORDS) :
                                                   last_ref + CONTEXT_WORDS + 1])  # fmt: skip
            out.append(Insertion(file_id, _category(h, j), h[j].text, w.start, w.end, hyp_ctx,
                                 ref_ctx))  # fmt: skip
    return out


def sample(
    insertions: list[Insertion], quotas: dict[Category, int] = DEFAULT_QUOTAS, seed: int = 0
) -> list[Insertion]:
    """Random sample per category, sorted by file and time; ids A01, A02..."""
    rng = random.Random(seed)
    by_cat: dict[str, list[Insertion]] = defaultdict(list)
    for ins in insertions:
        by_cat[ins.category].append(ins)
    picked = []
    for cat in CATEGORIES:
        pool = by_cat.get(cat, [])
        picked += rng.sample(pool, min(quotas.get(cat, 0), len(pool)))
    picked.sort(key=lambda x: (x.file_id, x.start))
    for k, ins in enumerate(picked, start=1):
        ins.item_id = f"A{k:02d}"
    return picked


def cut_clip(audio: Path, start: float, end: float, out: Path) -> None:
    begin = max(0.0, start - CLIP_PADDING)
    subprocess.run(
        ["ffmpeg", "-nostdin", "-loglevel", "error", "-y", "-ss", f"{begin:.3f}", "-t",
         f"{end + CLIP_PADDING - begin:.3f}", "-i", str(audio), "-vn", "-ac", "1", "-c:a", "aac",
         str(out)],
        check=True,
    )  # fmt: skip


def write_page(items: list[Insertion], system: str, out_dir: Path) -> Path:
    """Self-contained HTML page (no network); answers kept in localStorage and exported as
    JSON with the "Esporta" button."""
    rows = []
    for ins in items:
        hyp = html.escape(ins.hyp_context).replace("⟦", "<mark>").replace("⟧", "</mark>")
        radios = " ".join(
            f'<label><input type="radio" name="{ins.item_id}" value="{a}"> {a}</label>'
            for a in ANSWERS
        )
        rows.append(f"""
<section id="{ins.item_id}">
  <h2>{ins.item_id} · {html.escape(ins.file_id)} · {format_timestamp(ins.start)[3:]} ·
      <span class="cat">{ins.category}</span></h2>
  <audio controls preload="none" src="clips/{ins.item_id}.m4a"></audio>
  <p><b>{html.escape(system)}:</b> {hyp}</p>
  <p class="ref"><b>riferimento:</b> {html.escape(ins.ref_context)}</p>
  <p class="answer">La parola evidenziata è stata detta davvero? {radios}
     <input type="text" class="note" data-id="{ins.item_id}" placeholder="nota (facoltativa)"></p>
</section>""")
    data = json.dumps([asdict(i) for i in items], ensure_ascii=False)
    page = f"""<!doctype html>
<html lang="it"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Verifica inserzioni</title>
<style>
:root {{ --bg:#fafafa; --fg:#1d1d1f; --muted:#6e6e73; --card:#fff; --line:#e5e5ea;
         --mark:#ffe58a; }}
@media (prefers-color-scheme: dark) {{
  :root {{ --bg:#1c1c1e; --fg:#f2f2f7; --muted:#a1a1a6; --card:#2c2c2e; --line:#3a3a3c;
           --mark:#8a6d00; }} }}
body {{ font: 16px/1.5 -apple-system, system-ui, sans-serif; background:var(--bg);
        color:var(--fg); max-width:900px; margin:0 auto; padding:16px; }}
section {{ background:var(--card); border:1px solid var(--line); border-radius:10px;
           padding:12px 16px; margin:12px 0; }}
h2 {{ font-size:15px; margin:0 0 8px; }} .cat {{ color:var(--muted); font-weight:normal; }}
mark {{ background:var(--mark); color:inherit; padding:0 2px; }}
.ref {{ color:var(--muted); }} audio {{ width:100%; }} .note {{ width:100%; margin-top:6px; }}
header {{ position:sticky; top:0; background:var(--bg); padding:8px 0;
          border-bottom:1px solid var(--line); }}
</style></head><body>
<header><b>Verifica inserzioni di {html.escape(system)}</b> — <span id="progress"></span>
  <button id="export">Esporta risposte</button></header>
<p>Per ogni clip: ascolta e indica se la parola evidenziata (scritta dal sistema ma assente
dal riferimento) è stata <b>detta davvero</b>. "vero" vuol dire che il riferimento l'ha persa;
"falso" che il sistema l'ha inventata. Le risposte restano in questo browser finché non le
esporti.</p>
{"".join(rows)}
<script>
const ITEMS = {data};
const KEY = "ilat-audit-" + {json.dumps(out_dir.name)};
let state = {{}};
try {{ state = JSON.parse(localStorage.getItem(KEY) || "{{}}"); }} catch (e) {{}}
function save() {{ try {{ localStorage.setItem(KEY, JSON.stringify(state)); }} catch (e) {{}}
  const done = ITEMS.filter(i => state[i.item_id] && state[i.item_id].answer).length;
  document.getElementById("progress").textContent = done + " / " + ITEMS.length; }}
for (const i of ITEMS) {{
  const s = state[i.item_id] || {{}};
  document.querySelectorAll(`input[name="${{i.item_id}}"]`).forEach(r => {{
    if (r.value === s.answer) r.checked = true;
    r.addEventListener("change", () => {{
      state[i.item_id] = {{...(state[i.item_id] || {{}}), answer: r.value}}; save(); }});
  }});
  const note = document.querySelector(`.note[data-id="${{i.item_id}}"]`);
  note.value = s.note || "";
  note.addEventListener("input", () => {{
    state[i.item_id] = {{...(state[i.item_id] || {{}}), note: note.value}}; save(); }});
}}
document.getElementById("export").addEventListener("click", () => {{
  const items = ITEMS.map(i => {{
    const s = state[i.item_id] || {{}};
    return {{...i, answer: s.answer || null, note: s.note || ""}};
  }});
  const out = {{system: {json.dumps(system)}, items}};
  const blob = new Blob([JSON.stringify(out, null, 2)], {{type: "application/json"}});
  const a = document.createElement("a");
  a.href = URL.createObjectURL(blob);
  a.download = "audit-answers.json"; a.click();
}});
save();
</script></body></html>
"""
    path = out_dir / "index.html"
    path.write_text(page, encoding="utf-8")
    (out_dir / "items.json").write_text(data + "\n", encoding="utf-8")
    return path


def summarize(answers: dict) -> str:
    """Share of insertions really spoken, per category, from an exported answers file."""
    counts: dict[str, Counter[str]] = defaultdict(Counter)
    for item in answers["items"]:
        counts[item["category"]][item.get("answer") or "senza risposta"] += 1
    lines = [f"Verifica di {answers.get('system', '?')}:", ""]
    lines.append("| Categoria | vero | falso | non so | senza risposta | % vero (su vero+falso) |")
    lines.append("|---|---|---|---|---|---|")
    total: Counter[str] = Counter()
    for cat in [*CATEGORIES, "totale"]:
        c = total if cat == "totale" else counts.get(cat, Counter())
        if cat != "totale":
            total.update(c)
        judged = c["vero"] + c["falso"]
        share = f"{c['vero'] / judged * 100:.0f}%" if judged else "—"
        lines.append(f"| {cat} | {c['vero']} | {c['falso']} | {c['non so']} | "
                     f"{c['senza risposta']} | {share} |")  # fmt: skip
    return "\n".join(lines)
