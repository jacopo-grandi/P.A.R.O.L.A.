"""Adjudicate the disagreements between two transcripts of the same audio.

Two systems that fail differently (Whisper turbo drops repetitions and false starts,
CrisperWhisper keeps them) are aligned; only where they disagree does a person listen and
choose. Words where both agree are kept without listening. The result is an ``adjudicated``
reference (docs/conventions.md §4, decision 0009).

``base`` is the transcript being corrected (a reference, or a draft); ``other`` is the second
opinion. Every region where they differ becomes an item: keep A (base), take B (other), or
type the right text.

Disagreements fall into a few kinds (``classify``). Where the listening audit showed that
CrisperWhisper is right (it keeps repetitions, truncations and extra words that turbo drops,
results/2026-10-15-audit-crisper.md), B is accepted automatically; for less certain kinds a
sample is listened to as a check of the rule; substitutions and deletions are always listened.
"""

from __future__ import annotations

import html
import json
import math
import random
from dataclasses import asdict, dataclass, field
from pathlib import Path

from parola.eval.audit import _audio_src, cut_clip
from parola.eval.metrics import align, assign_words
from parola.eval.normalize import canonical_filler, split_word, tokenize
from parola.schema import Transcript, Word, WordTag, format_timestamp
from parola.schema.vocab import split_punctuation

# Disagreements separated by at most this many agreeing tokens form one item.
MERGE_GAP_TOKENS = 1
CONTEXT_WORDS = 6

# What to do with each kind of disagreement (decided by Jacopo, 2026-10-15), depending on which
# side is the verbatim system (CrisperWhisper): it is right when it has *more* repetitions,
# truncations and fillers than the other side.
POLICY = {
    # base = reference, other (B) = CrisperWhisper
    "B": {"auto": {"repetition", "truncated", "superset"}, "sampled": {"insertion", "filler"}},
    # base (A) = CrisperWhisper draft, other = Whisper turbo
    "A": {"auto": {"deleted_repetition", "deleted_truncated", "subset"},
          "sampled": {"deleted_filler"}},
}  # fmt: skip
AUTO_KINDS = POLICY["B"]["auto"] | POLICY["A"]["auto"]
SAMPLED_KINDS = POLICY["B"]["sampled"] | POLICY["A"]["sampled"]
CHECK_EVERY = 6
# A sampled kind whose checks agree with B less than this goes back to listening.
MIN_RULE_AGREEMENT = 0.9
KIND_LABELS = {
    "repetition": "B aggiunge una ripetizione",
    "truncated": "B aggiunge una troncata",
    "superset": "B = A con parole in più",
    "insertion": "B aggiunge parole",
    "filler": "B aggiunge un'esitazione",
    "substitution": "parole diverse",
    "deletion": "B toglie parole",
    "deleted_filler": "B toglie un'esitazione",
    "deleted_repetition": "B toglie una ripetizione",
    "deleted_truncated": "B toglie una troncata",
    "subset": "B = A con parole in meno",
}


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
    lang: str = "it"
    kind: str = ""
    # "B" when the rule accepts the other side without listening.
    auto: str | None = None
    # Auto-accepted item shown anyway, as a sample check of the rule.
    check: bool = False
    other_text: str = field(init=False)

    def __post_init__(self) -> None:
        self.other_text = " ".join(self.other_texts)


def classify(base_text: str, other_texts: list[str], before: str, after: str, lang: str) -> str:
    """Kind of a disagreement, from the point of view of B (the other side)."""

    def norm(words: list[str]) -> list[str]:
        return [t for w in words for t in split_word(w, lang)]

    a, b = norm(base_text.split()), norm(other_texts)
    context = norm(before.split()[-2:] + after.split()[:2])

    def extra(words: list[str]) -> str:
        """What kind of words one side has and the other lacks."""
        if words and all(canonical_filler(t, lang) for t in words):
            return "filler"
        if any(t.endswith("-") for t in words):
            return "truncated"
        if words and all(t in context for t in words):
            return "repetition"
        return "other"

    if not a:
        kind = extra(b)
        return "insertion" if kind == "other" else kind
    if not b:
        kind = extra(a)
        return "deletion" if kind == "other" else f"deleted_{kind}"

    def contains(longer: list[str], shorter: list[str]) -> bool:
        it = iter(longer)
        return all(t in it for t in shorter)

    if len(b) > len(a) and contains(b, a):
        return "superset"
    if len(a) > len(b) and contains(a, b):
        return "subset"
    return "substitution"


def apply_policy(
    regions: list[Region], listen: set[str] = frozenset(), seed: int = 0, verbatim_side: str = "B"
) -> list[Region]:
    """Set ``auto`` and ``check`` on each region; kinds in ``listen`` are always listened.

    ``verbatim_side`` is the side produced by CrisperWhisper: its choice is taken
    automatically for the kinds of POLICY[verbatim_side]."""
    rng = random.Random(seed)
    policy = POLICY[verbatim_side]
    for r in regions:
        r.auto, r.check = None, False
        if r.kind in (policy["auto"] | policy["sampled"]) - set(listen):
            r.auto = verbatim_side
    for kind in sorted(policy["sampled"] - set(listen)):
        pool = [r for r in regions if r.kind == kind]
        for r in rng.sample(pool, math.ceil(len(pool) / CHECK_EVERY)):
            r.check = True
    return regions


def merged_answers(regions: list[Region], answers: dict[str, dict]) -> dict[str, dict]:
    """Automatic choices, overridden by every explicit answer."""
    merged = {r.item_id: {"choice": r.auto} for r in regions if r.auto}
    merged.update({k: v for k, v in answers.items() if v and v.get("choice")})
    return merged


def rule_agreement(regions: list[Region], answers: dict[str, dict]) -> dict[str, tuple[int, int]]:
    """Per sampled kind: (checks where the person made the automatic choice, checks answered)."""
    out: dict[str, tuple[int, int]] = {}
    for r in regions:
        choice = (answers.get(r.item_id) or {}).get("choice")
        if r.check and choice:
            agree, total = out.get(r.kind, (0, 0))
            out[r.kind] = (agree + (choice == r.auto), total + 1)
    return out


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
                    lang=lang,
                )
            )
    for k, r in enumerate(regions, start=1):
        r.item_id = f"D{k:03d}"
        r.kind = classify(r.base_text, r.other_texts, r.before, r.after, r.lang)
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
    """Page with the items to listen to: those without an automatic choice, plus the checks.
    All regions are saved in regions.json; answers are keyed by item id, so a rebuilt page
    keeps the answers already given."""
    shown = [r for r in regions if r.auto is None or r.check]
    n_auto = sum(1 for r in regions if r.auto and not r.check)
    rows = []
    for r in shown:
        tag = (
            f'<span class="chk">controllo a campione · {KIND_LABELS.get(r.kind, r.kind)}</span>'
            if r.check
            else f'<span class="kind">{KIND_LABELS.get(r.kind, r.kind)}</span>'
        )
        src = _audio_src(out_dir / "clips" / f"{r.item_id}.m4a")
        rows.append(f"""
<section id="{r.item_id}" data-id="{r.item_id}">
  <h2>{r.item_id} · {format_timestamp(r.start)[3:]} · {tag}</h2>
  <audio controls preload="none" src="{src}"></audio>
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
    data = json.dumps([asdict(r) for r in shown], ensure_ascii=False)
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
.chk {{ color:var(--cur); }} .kind {{ font-weight:normal; }}
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
esporti; senza risposta vale A. Altre {n_auto} divergenze sono accettate in automatico (B) dalla
regola: ripetizioni, troncate, parole in più. Quelle marcate "controllo a campione" servono a
verificare la regola: rispondi come per le altre.</p>
{"".join(rows)}
<script>
const ITEMS = {data};
// Keyed by the total number of regions, not of shown items: rebuilding the page with a
// different rule keeps the answers already given.
const KEY = "parola-adjudicate-" + {json.dumps(file_id)} + "-" + {len(regions)};
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
  // Also answers to items no longer shown (given before a rule change).
  for (const [k, v] of Object.entries(state)) if (!(k in answers)) answers[k] = v;
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
    all_regions = json.dumps([asdict(r) for r in regions], ensure_ascii=False)
    (out_dir / "regions.json").write_text(all_regions + "\n", encoding="utf-8")
    return path


def build(regions: list[Region], audio: Path, file_id: str, labels: tuple[str, str],
          out_dir: Path) -> Path:  # fmt: skip
    (out_dir / "clips").mkdir(parents=True, exist_ok=True)
    for r in regions:
        if r.auto is None or r.check:
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
