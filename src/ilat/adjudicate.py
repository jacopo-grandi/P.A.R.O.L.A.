"""Adjudicate the disagreements between two transcripts of the same audio.

Two systems that fail differently (Whisper turbo drops repetitions and false starts,
CrisperWhisper keeps them) are aligned; only where they disagree does a person listen and
choose. Words where both agree are kept without listening. The result is an ``adjudicated``
reference (docs/conventions.md §4, decision 0009).

``base`` is the transcript being corrected (a reference, or a draft); ``other`` is the second
opinion. Every region where they differ becomes an item: keep A (base), take B (other), or
type the right text.
"""

from __future__ import annotations

import html
import json
from dataclasses import asdict, dataclass, field
from pathlib import Path

from ilat.eval.audit import _audio_src, cut_clip
from ilat.eval.metrics import align, assign_words
from ilat.eval.normalize import canonical_filler, split_word, tokenize
from ilat.schema import Transcript, Word, WordTag, format_timestamp
from ilat.schema.vocab import split_punctuation

# Disagreements separated by at most this many agreeing tokens form one item.
MERGE_GAP_TOKENS = 1
CONTEXT_WORDS = 6


@dataclass
class Region:
    item_id: str
    segment: int
    # Base words [base_lo, base_hi) are replaced; base_lo == base_hi is a pure insertion.
    base_lo: int
    base_hi: int
    base_text: str
    other_texts: list[str]
    other_times: list[tuple[float | None, float | None]]
    start: float
    end: float
    before: str
    after: str
    other_text: str = field(init=False)

    def __post_init__(self) -> None:
        self.other_text = " ".join(self.other_texts)


def _side(t: Transcript) -> str:
    return "ref" if t.metadata.kind == "reference" else "hyp"


def find_regions(base: Transcript, other: Transcript) -> list[Region]:
    regions: list[Region] = []
    groups = assign_words(base, other)
    for si, (seg, other_words) in enumerate(zip(base.segments, groups, strict=True)):
        if seg.overlap:
            continue
        lang = seg.lang or "it"
        b = tokenize(seg.words, lang, "verbatim", _side(base))
        o = tokenize(other_words, lang, "verbatim", "hyp")
        _, pairs = align(b, o)
        # Indices of the pairs that disagree, grouped into runs.
        bad = [k for k, (op, _, _) in enumerate(pairs) if op != "equal"]
        runs: list[list[int]] = []
        for k in bad:
            if runs and k - runs[-1][-1] - 1 <= MERGE_GAP_TOKENS:
                runs[-1].extend(range(runs[-1][-1] + 1, k + 1))
            else:
                runs.append([k])
        spans: list[tuple[int, int, set[int], int]] = []  # (lo, hi, other indices, run start)
        for run in runs:
            bi = [pairs[k][1] for k in run if pairs[k][1] >= 0]
            oi = {o[pairs[k][2]].word_index for k in run if pairs[k][2] >= 0}
            if bi:
                lo, hi = b[min(bi)].word_index, b[max(bi)].word_index + 1
            else:
                # Pure insertion: after the last base token before the run.
                prev = [pairs[k][1] for k in range(run[0]) if pairs[k][1] >= 0]
                lo = hi = b[prev[-1]].word_index + 1 if prev else 0
            # A word split into several tokens ("dell'80%") can fall into two runs: merge
            # spans that share base or other words, so that replacements never overlap.
            if spans and (lo < spans[-1][1] or oi & spans[-1][2]):
                plo, phi, poi, pstart = spans.pop()
                lo, hi, oi, run0 = min(lo, plo), max(hi, phi), oi | poi, pstart
            else:
                run0 = run[0]
            spans.append((lo, hi, oi, run0))
        for lo, hi, oi, run0 in spans:
            o_words = [other_words[j] for j in sorted(oi)]
            times = [t for w in o_words for t in (w.start, w.end) if t is not None]
            times += [t for w in seg.words[lo:hi] for t in (w.start, w.end) if t is not None]
            if not times:
                # Deletion against a reference without word times: use the neighbours.
                near = [other_words[o[pairs[k][2]].word_index] for k in range(len(pairs))
                        if pairs[k][2] >= 0 and abs(k - run0) <= 3]  # fmt: skip
                times = [t for w in near for t in (w.start, w.end) if t is not None]
            start, end = (min(times), max(times)) if times else (seg.start, seg.end)
            regions.append(
                Region(
                    item_id="",
                    segment=si,
                    base_lo=lo,
                    base_hi=hi,
                    base_text=" ".join(w.text for w in seg.words[lo:hi]),
                    other_texts=[w.text for w in o_words],
                    other_times=[(w.start, w.end) for w in o_words],
                    start=start,
                    end=end,
                    before=" ".join(w.text for w in seg.words[max(0, lo - CONTEXT_WORDS) : lo]),
                    after=" ".join(w.text for w in seg.words[hi : hi + CONTEXT_WORDS]),
                )
            )
    for k, r in enumerate(regions, start=1):
        r.item_id = f"D{k:03d}"
    return regions


def _new_word(text: str, lang: str | None, reference: bool, times=(None, None)) -> Word:
    """A word taken from the other side or typed by the annotator: tags from its form."""
    tags: list[WordTag] = []
    parts = split_word(text, lang or "it")
    canonical = canonical_filler(parts[0], lang or "it") if len(parts) == 1 else None
    if canonical and "?" not in text:
        tags.append("filler")
        if reference:
            # §2.2: map the form to the inventory of the language ("um" in Italian -> "ehm").
            _, punct = split_punctuation(text)
            text = canonical + punct
    if parts and parts[-1].endswith("-"):
        tags.append("truncated")
    if not reference:
        return Word(text=text, start=times[0], end=times[1])
    return Word(text=text, lang=lang, tags=tags)


def apply(base: Transcript, regions: list[Region], answers: dict[str, dict]) -> Transcript:
    """Apply the choices: "A" (or no answer) keeps base, "B" takes other, "text" uses the
    typed text (empty text deletes the base words)."""
    reference = base.metadata.kind == "reference"
    segments = [s.model_copy(deep=True) for s in base.segments]
    by_seg: dict[int, list[Region]] = {}
    for r in regions:
        by_seg.setdefault(r.segment, []).append(r)
    for si, regs in by_seg.items():
        seg = segments[si]
        words = list(seg.words)
        # Right to left, so that earlier indices stay valid.
        for r in sorted(regs, key=lambda r: (r.base_lo, r.base_hi), reverse=True):
            a = answers.get(r.item_id) or {}
            choice = a.get("choice") or "A"
            if choice == "B":
                new = [_new_word(t, seg.lang, reference, tm)
                       for t, tm in zip(r.other_texts, r.other_times, strict=True)]  # fmt: skip
            elif choice == "text":
                new = [_new_word(t, seg.lang, reference) for t in (a.get("text") or "").split()]
            else:
                continue
            words[r.base_lo : r.base_hi] = new
        seg.words = words
        seg.text = " ".join(w.text for w in words)
    return base.model_copy(update={"segments": [s for s in segments if s.words or s.text]})


def write_page(regions: list[Region], file_id: str, labels: tuple[str, str], out_dir: Path) -> Path:
    rows = []
    for r in regions:
        src = _audio_src(out_dir / "clips" / f"{r.item_id}.m4a")
        rows.append(f"""
<section id="{r.item_id}" data-id="{r.item_id}">
  <h2>{r.item_id} · {format_timestamp(r.start)[3:]}</h2>
  <audio preload="none" src="{src}"></audio>
  <p class="opt"><label><input type="radio" name="{r.item_id}" value="A"> <kbd>1</kbd>
    <b>A</b> <span class="ctx">{html.escape(r.before)}</span>
    <mark>{html.escape(r.base_text) or "∅"}</mark>
    <span class="ctx">{html.escape(r.after)}</span></label></p>
  <p class="opt"><label><input type="radio" name="{r.item_id}" value="B"> <kbd>2</kbd>
    <b>B</b> <span class="ctx">{html.escape(r.before)}</span>
    <mark>{html.escape(r.other_text) or "∅"}</mark>
    <span class="ctx">{html.escape(r.after)}</span></label></p>
  <p class="opt"><label><input type="radio" name="{r.item_id}" value="text"> <kbd>3</kbd>
    altro: <input type="text" class="txt" data-id="{r.item_id}"
    placeholder="testo giusto al posto della parte evidenziata (vuoto = niente)"></label></p>
</section>""")
    data = json.dumps([asdict(r) for r in regions], ensure_ascii=False)
    a_label, b_label = (html.escape(x) for x in labels)
    page = f"""<!doctype html>
<html lang="it"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Divergenze {html.escape(file_id)}</title>
<style>
:root {{ --bg:#fafafa; --fg:#1d1d1f; --muted:#6e6e73; --card:#fff; --line:#e5e5ea;
         --mark:#ffe58a; --cur:#0a84ff; }}
@media (prefers-color-scheme: dark) {{
  :root {{ --bg:#1c1c1e; --fg:#f2f2f7; --muted:#a1a1a6; --card:#2c2c2e; --line:#3a3a3c;
           --mark:#8a6d00; }} }}
body {{ font: 16px/1.5 -apple-system, system-ui, sans-serif; background:var(--bg);
        color:var(--fg); max-width:960px; margin:0 auto; padding:16px; }}
section {{ background:var(--card); border:2px solid var(--line); border-radius:10px;
           padding:10px 14px; margin:10px 0; }}
section.cur {{ border-color:var(--cur); }} section.done {{ opacity:.6; }}
h2 {{ font-size:14px; margin:0 0 4px; color:var(--muted); }}
.opt {{ margin:4px 0; }} .ctx {{ color:var(--muted); }}
mark {{ background:var(--mark); color:inherit; padding:0 3px; }}
kbd {{ font-size:12px; border:1px solid var(--line); border-radius:4px; padding:0 4px; }}
.txt {{ width:60%; }}
header {{ position:sticky; top:0; background:var(--bg); padding:8px 0; z-index:1;
          border-bottom:1px solid var(--line); }}
</style></head><body>
<header><b>Divergenze {html.escape(file_id)}</b> — A = {a_label}, B = {b_label} —
  <span id="progress"></span> <button id="export">Esporta risposte</button></header>
<p>Ascolta e scegli quale versione corrisponde a ciò che è stato <b>detto</b>, parola per parola
(ripetizioni, esitazioni, errori compresi). Tasti: <kbd>spazio</kbd> ascolta di nuovo,
<kbd>1</kbd> A, <kbd>2</kbd> B, <kbd>3</kbd> scrivi tu,
<kbd>↓</kbd>/<kbd>↑</kbd> successiva/precedente.
Dopo una scelta passa da sola alla successiva. Le risposte restano in questo browser finché non le
esporti; senza risposta vale A.</p>
{"".join(rows)}
<script>
const ITEMS = {data};
const KEY = "ilat-adjudicate-" + {json.dumps(file_id)} + "-" + ITEMS.length;
let state = {{}};
try {{ state = JSON.parse(localStorage.getItem(KEY) || "{{}}"); }} catch (e) {{}}
const sections = [...document.querySelectorAll("section")];
let cur = 0;
function save() {{
  try {{ localStorage.setItem(KEY, JSON.stringify(state)); }} catch (e) {{}}
  const done = ITEMS.filter(i => state[i.item_id] && state[i.item_id].choice).length;
  document.getElementById("progress").textContent = done + " / " + ITEMS.length;
  sections.forEach(s => s.classList.toggle("done", !!(state[s.dataset.id] || {{}}).choice));
}}
function focusItem(k, play) {{
  if (k < 0 || k >= sections.length) return;
  sections.forEach(s => {{ s.classList.remove("cur"); s.querySelector("audio").pause(); }});
  cur = k; const s = sections[k]; s.classList.add("cur");
  s.scrollIntoView({{block: "center", behavior: "smooth"}});
  if (play) {{ const a = s.querySelector("audio"); a.currentTime = 0; a.play().catch(() => {{}}); }}
}}
function choose(id, choice, advance) {{
  state[id] = {{...(state[id] || {{}}), choice}};
  document.querySelector(`input[name="${{id}}"][value="${{choice}}"]`).checked = true;
  save();
  if (advance) focusItem(cur + 1, true);
}}
sections.forEach((s, k) => {{
  const id = s.dataset.id, st = state[id] || {{}};
  s.querySelectorAll(`input[name="${{id}}"]`).forEach(r => {{
    if (r.value === st.choice) r.checked = true;
    r.addEventListener("change", () => choose(id, r.value, false));
  }});
  const t = s.querySelector(".txt"); t.value = st.text || "";
  t.addEventListener("input", () => {{ state[id] = {{...(state[id] || {{}}), text: t.value,
    choice: "text"}}; document.querySelector(`input[name="${{id}}"][value="text"]`).checked = true;
    save(); }});
  s.addEventListener("click", () => {{ if (cur !== k) focusItem(k, false); }});
}});
document.addEventListener("keydown", e => {{
  if (e.target.tagName === "INPUT" && e.target.type === "text") {{
    if (e.key === "Enter" || e.key === "Escape") {{ e.target.blur(); focusItem(cur + 1, true); }}
    return;
  }}
  const id = sections[cur].dataset.id;
  if (e.key === " ") {{ e.preventDefault(); focusItem(cur, true); }}
  else if (e.key === "1") choose(id, "A", true);
  else if (e.key === "2") choose(id, "B", true);
  else if (e.key === "3") {{ e.preventDefault(); sections[cur].querySelector(".txt").focus();
    choose(id, "text", false); }}
  else if (e.key === "ArrowDown") {{ e.preventDefault(); focusItem(cur + 1, true); }}
  else if (e.key === "ArrowUp") {{ e.preventDefault(); focusItem(cur - 1, true); }}
}});
document.getElementById("export").addEventListener("click", () => {{
  const answers = {{}};
  for (const i of ITEMS) answers[i.item_id] = state[i.item_id] || {{}};
  const blob = new Blob([JSON.stringify({{file_id: {json.dumps(file_id)}, answers}}, null, 2)],
                        {{type: "application/json"}});
  const a = document.createElement("a");
  a.href = URL.createObjectURL(blob);
  a.download = "adjudication-" + {json.dumps(file_id)} + ".json"; a.click();
}});
save(); focusItem(0, false);
</script></body></html>
"""
    path = out_dir / "index.html"
    path.write_text(page, encoding="utf-8")
    (out_dir / "regions.json").write_text(data + "\n", encoding="utf-8")
    return path


def build(regions: list[Region], audio: Path, file_id: str, labels: tuple[str, str],
          out_dir: Path) -> Path:  # fmt: skip
    (out_dir / "clips").mkdir(parents=True, exist_ok=True)
    for r in regions:
        cut_clip(audio, r.start, r.end, out_dir / "clips" / f"{r.item_id}.m4a")
    return write_page(regions, file_id, labels, out_dir)


def load_regions(out_dir: Path) -> list[Region]:
    raw = json.loads((out_dir / "regions.json").read_text(encoding="utf-8"))
    regions = []
    for d in raw:
        d.pop("other_text", None)
        d["other_times"] = [tuple(t) for t in d["other_times"]]
        regions.append(Region(**d))
    return regions
