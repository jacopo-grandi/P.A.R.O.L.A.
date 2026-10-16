// P.A.R.O.L.A. local UI: calls in the sidebar, the transcript in the middle, doubtful words to review.
"use strict";

// "mixed": an imported file, every voice on one track, so no side to name.
const LABELS = { mic: "Io", system: "Altri", mixed: "" };
const LEAD = 0.25;         // start playing a little before the word
const SPEEDS = [0.75, 1, 1.25, 1.5, 1.75, 2];
const EXCERPT_TAIL = 1.0;  // a doubtful run plays until this long after its last word
const LANGS = [["", "Auto"], ["it", "IT"], ["en", "EN"]];

const $main = document.getElementById("main");
const $calls = document.getElementById("list");
const $pending = document.getElementById("pending");
const $search = document.getElementById("search");
const $recorder = document.getElementById("recorder");
const $audio = document.getElementById("audio");

// ---------------------------------------------------------------- helpers

function el(tag, attrs = {}, ...children) {
  const e = document.createElement(tag);
  for (const [k, v] of Object.entries(attrs)) {
    if (v === false || v === null || v === undefined) continue;
    if (k === "class") e.className = v;
    else if (k.startsWith("on")) e.addEventListener(k.slice(2), v);
    else e.setAttribute(k, v === true ? "" : v);
  }
  for (const c of children) if (c !== null && c !== undefined && c !== false) e.append(c);
  return e;
}

// 24px line icons, drawn here so nothing is fetched.
const ICONS = {
  play: '<path d="M8 5.5v13l10.5-6.5z" fill="currentColor"/>',
  pause: '<rect x="6.5" y="5" width="3.6" height="14" rx="1" fill="currentColor"/>' +
         '<rect x="13.9" y="5" width="3.6" height="14" rx="1" fill="currentColor"/>',
  stop: '<rect x="6" y="6" width="12" height="12" rx="2.5" fill="currentColor"/>',
  popout: '<path d="M14 4h6v6M20 4l-8 8M18 14v4.5A1.5 1.5 0 0 1 16.5 20h-11A1.5 1.5 0 0 1 4 18.5' +
          'v-11A1.5 1.5 0 0 1 5.5 6H10"/>',
  prev: '<path d="M15 6l-6 6 6 6"/>',
  next: '<path d="M9 6l6 6-6 6"/>',
  undo: '<path d="M9 14L4 9l5-5"/><path d="M4 9h10.5a5.5 5.5 0 0 1 0 11H11"/>',
  more: '<circle cx="5.5" cy="12" r="1.6" fill="currentColor" stroke="none"/>' +
        '<circle cx="12" cy="12" r="1.6" fill="currentColor" stroke="none"/>' +
        '<circle cx="18.5" cy="12" r="1.6" fill="currentColor" stroke="none"/>',
  filter: '<path d="M4 7h16M7 12h10M10 17h4"/>',
  upload: '<path d="M12 15V4M7.5 8.5L12 4l4.5 4.5"/><path d="M5 14v4.5A1.5 1.5 0 0 0 6.5 20h11' +
          'a1.5 1.5 0 0 0 1.5-1.5V14"/>',
  close: '<path d="M7 7l10 10M17 7L7 17"/>',
};

function icon(name, size = 16) {
  const s = document.createElementNS("http://www.w3.org/2000/svg", "svg");
  s.setAttribute("viewBox", "0 0 24 24");
  s.setAttribute("width", size);
  s.setAttribute("height", size);
  s.setAttribute("aria-hidden", "true");
  s.setAttribute("fill", "none");
  s.setAttribute("stroke", "currentColor");
  s.setAttribute("stroke-width", "1.8");
  s.setAttribute("stroke-linecap", "round");
  s.setAttribute("stroke-linejoin", "round");
  s.innerHTML = ICONS[name];
  return s;
}

function iconButton(name, label, onclick, cls = "") {
  return el("button", { class: `icon-btn ${cls}`, title: label, "aria-label": label, onclick },
    icon(name));
}

function clock(seconds) {
  const s = Math.max(0, Math.floor(seconds || 0));
  const h = Math.floor(s / 3600), m = Math.floor((s % 3600) / 60), r = s % 60;
  const mm = String(m).padStart(2, "0"), ss = String(r).padStart(2, "0");
  return h ? `${h}:${mm}:${ss}` : `${mm}:${ss}`;
}

const enc = encodeURIComponent;

async function getJSON(url) {
  const r = await fetch(url);
  if (!r.ok) throw new Error(`${url}: ${r.status}`);
  return r.json();
}

async function postJSON(url, body) {
  const r = await fetch(url, { method: "POST", headers: { "Content-Type": "application/json" },
                               body: JSON.stringify(body || {}) });
  const data = await r.json().catch(() => ({}));
  if (!r.ok) throw new Error(data.detail || `${r.status}`);
  return data;
}

let toastTimer = null;
function toast(message, action) {
  // A message with an action (Annulla) stays until it is used or closed; plain ones fade.
  const t = document.getElementById("toast");
  const parts = [el("span", {}, message)];
  if (action) {
    parts.push(el("button", { class: "toast-action", onclick: () => { hideToast(); action.run(); } },
      action.label));
    parts.push(iconButton("close", "Chiudi l'avviso", hideToast, "toast-close"));
  }
  t.replaceChildren(...parts);
  t.classList.add("show");
  clearTimeout(toastTimer);
  if (!action) toastTimer = setTimeout(hideToast, 4000);
}

function hideToast() {
  const t = document.getElementById("toast");
  t.classList.remove("show");
  setTimeout(() => { if (!t.classList.contains("show")) t.replaceChildren(); }, 250);
}

function popMenu(anchor, ...items) {
  // A small menu under `anchor`; closes on a choice, a click elsewhere or Escape.
  document.querySelectorAll(".menu").forEach(m => m.remove());
  const menu = el("div", { class: "menu", role: "menu" }, ...items);
  const close = () => {
    menu.remove();
    document.removeEventListener("click", outside, true);
    document.removeEventListener("keydown", onKey, true);
  };
  const outside = e => { if (!menu.contains(e.target)) close(); };
  const onKey = e => {
    if (e.key === "Escape") { e.stopPropagation(); close(); anchor.querySelector("button")?.focus(); }
  };
  menu.addEventListener("click", e => { if (e.target.closest("a, button")) close(); });
  anchor.append(menu);
  setTimeout(() => {
    document.addEventListener("click", outside, true);
    document.addEventListener("keydown", onKey, true);
  });
  menu.querySelector("a, button")?.focus();
  return menu;
}

// ---------------------------------------------------------------- sidebar

let calls = [];   // summaries from /api/recordings, newest first

function dayOf(d) { return new Date(d.getFullYear(), d.getMonth(), d.getDate()); }

function groupOf(date) {
  const days = Math.round((dayOf(new Date()) - dayOf(date)) / 86400000);
  if (days <= 0) return "Oggi";
  if (days === 1) return "Ieri";
  if (days < 7) return "Ultimi 7 giorni";
  if (days < 30) return "Ultimi 30 giorni";
  return date.toLocaleDateString("it-IT", { month: "long", year: "numeric" });
}

function shortWhen(date) {
  const days = Math.round((dayOf(new Date()) - dayOf(date)) / 86400000);
  return days < 2 ? date.toLocaleTimeString("it-IT", { hour: "2-digit", minute: "2-digit" })
                  : date.toLocaleDateString("it-IT", { day: "numeric", month: "short" });
}

function minutes(seconds) {
  const m = Math.round((seconds || 0) / 60);
  return m < 1 ? "< 1 min" : m < 60 ? `${m} min` : `${Math.floor(m / 60)} h ${m % 60} min`;
}

async function refreshCalls() {
  calls = await getJSON("/api/recordings");
  renderCalls();
}

function renderCalls() {
  if (searchQuery()) { renderResults(); return; }
  const q = $search.value.trim().toLowerCase();
  const shown = calls.filter(c => !q || c.title.toLowerCase().includes(q) ||
                                  c.name.toLowerCase().includes(q));
  const items = [];
  let group = null;
  for (const c of shown) {
    const date = new Date(c.started_at);
    const g = groupOf(date);
    if (g !== group) items.push(el("div", { class: "group" }, group = g));
    const title = el("span", { class: "title" }, c.title);
    const sub = el("span", { class: "sub" }, `${shortWhen(date)} · ${minutes(c.duration)}`,
      c.to_review ? el("span", { class: "n" }, ` · ${c.to_review} da rivedere`) : null);
    // The full title on hover: the row truncates it.
    const a = el("a", { class: "call", href: `#/rec/${enc(c.name)}`, title: c.title }, title, sub);
    a.addEventListener("dblclick", e => { e.preventDefault(); renameInPlace(title, c); });
    const row = el("div", { class: "call-row" + (c.name === recName ? " active" : "") }, a);
    row.append(iconButton("more", `Altre azioni per ${c.title}`, e => {
      e.stopPropagation();
      popMenu(row,
        el("button", { role: "menuitem", onclick: () => renameInPlace(title, c) }, "Rinomina"),
        el("button", { role: "menuitem", onclick: () => suggestTitle(title, c) },
          "Titolo dal contenuto"),
        el("button", { role: "menuitem", class: "danger", onclick: () => deleteCall(c) },
          "Elimina"));
    }, "call-more"));
    items.push(row);
  }
  if (!items.length) {
    items.push(el("p", { class: "empty-list" },
      q ? `Nessuna call per “${$search.value.trim()}”.` : "Ancora nessuna call."));
  }
  $calls.replaceChildren(...items);
}

async function suggestTitle(host, call) {
  // Key phrases of the call, proposed in the rename field: the person confirms or edits.
  let s;
  try {
    s = await getJSON(`/api/recordings/${enc(call.name)}/title-suggestion`);
  } catch (e) { toast(`Nessun titolo suggerito: ${e.message}`); return; }
  if (!s.title) { toast("La call è troppo breve per suggerire un titolo."); return; }
  renameInPlace(host, call, s.title);
}

async function deleteCall(call) {
  let res;
  try {
    res = await fetch(`/api/recordings/${enc(call.name)}`, { method: "DELETE" });
    if (!res.ok) throw new Error((await res.json()).detail || res.status);
    res = await res.json();
  } catch (e) { toast(`Call non eliminata: ${e.message}`); return; }
  if (call.name === recName) location.hash = "#/";
  await refreshCalls();
  toast(`“${call.title}” eliminata`, { label: "Annulla", run: async () => {
    try {
      await postJSON(`/api/trash/${enc(res.trashed)}/restore`);
      await refreshCalls();
      location.hash = `#/rec/${enc(call.name)}`;
    } catch (e) { toast(`Call non ripristinata: ${e.message}`); }
  } });
}

function renameInPlace(host, call, proposal) {
  // `proposal` (a suggested title) fills the field; Enter keeps it, Esc leaves the old name.
  const before = call.title;
  const input = el("input", { class: "inline", value: proposal || before, maxlength: "120",
                              "aria-label": "Nome della call" });
  host.replaceChildren(input);
  input.focus();
  input.select();
  let finished = false;
  const finish = async save => {
    if (finished) return;
    finished = true;
    const title = input.value.trim();
    if (save && title && title !== before) {
      try {
        await postJSON(`/api/recordings/${enc(call.name)}/rename`, { title });
        if (rec && call.name === recName) rec.summary.title = title;
      } catch (e) { toast(`Non rinominata: ${e.message}`); }
    }
    await refreshCalls();
    if (rec && call.name === recName) renderHeading();
  };
  input.addEventListener("keydown", e => {
    e.stopPropagation();
    if (e.key === "Enter") { e.preventDefault(); finish(true); }
    else if (e.key === "Escape") { e.preventDefault(); finish(false); }
  });
  input.addEventListener("click", e => { e.preventDefault(); e.stopPropagation(); });
  input.addEventListener("blur", () => finish(true));
}

// ---------------------------------------------------------------- search

let results = null;     // {q, calls} from /api/search for the query in the box
let searchTimer = null;
let searchSeq = 0;

function searchQuery() {
  const q = $search.value.trim();
  return q.length >= 2 ? q : "";
}

async function runSearch() {
  const q = searchQuery();
  const seq = ++searchSeq;
  if (!q) { results = null; renderCalls(); return; }
  try {
    const calls = await getJSON(`/api/search?q=${enc(q)}`);
    if (seq === searchSeq) { results = { q, calls }; renderCalls(); }  // drop late answers
  } catch (e) { /* server restarting: keep the last results */ }
}

$search.addEventListener("input", () => {
  clearTimeout(searchTimer);
  if (!searchQuery()) { results = null; renderCalls(); return; }
  searchTimer = setTimeout(runSearch, 180);
});
$search.addEventListener("keydown", e => {
  if (e.key === "Escape") { $search.value = ""; results = null; renderCalls(); $search.blur(); }
});

function hitLink(call, q, i) {
  return `#/rec/${enc(call.name)}?q=${enc(q)}&hit=${i}`;
}

function renderResults() {
  const q = searchQuery();
  if (!results || results.q !== q) {
    $calls.replaceChildren(el("p", { class: "empty-list" }, "Cerco…"));
    return;
  }
  const items = [el("div", { class: "group" }, "Risultati")];
  for (const c of results.calls) {
    const sub = c.count
      ? `${c.count} ${c.count === 1 ? "volta" : "volte"} · ${shortWhen(new Date(c.started_at))}`
      : `nel titolo · ${shortWhen(new Date(c.started_at))}`;
    const row = el("div", { class: "call-row" + (c.name === recName ? " active" : "") },
      el("a", { class: "call", href: c.count ? hitLink(c, q, 0) : `#/rec/${enc(c.name)}`,
                title: c.title },
        el("span", { class: "title" }, c.title), el("span", { class: "sub" }, sub)));
    items.push(row);
    c.hits.forEach((h, i) => {
      items.push(el("a", { class: "snip", href: hitLink(c, q, i) },
        el("span", { class: "snip-t" }, clock(h.time)),
        h.before ? `…${h.before} ` : "", el("mark", {}, h.match), h.after ? ` ${h.after}…` : ""));
    });
  }
  if (!results.calls.length) {
    items.push(el("p", { class: "empty-list" }, `Nessuna call contiene “${q}”.`));
  }
  $calls.replaceChildren(...items);
}

// ---------------------------------------------------------------- transcript

let rec = null;      // recording being shown
let recName = null;
let players = {};    // channel -> <audio>
let words = [];      // flat list of {el, channel, start, end, doubtful, seg, k}
let runs = [];       // doubtful runs still to review: {seg, start, end, t, channel}
let current = null;  // word element being played
let target = null;   // word chosen by click or N/P, until playback reaches it
let editing = null;  // {seg, start, end}
let stopAt = null;   // {channel, t}: stop playback there (excerpt of a doubtful run)
let lastChannel = null;
let onlyDoubts = false;
let view = {};       // elements of the call view that are updated in place

// Playback speed, remembered in this browser only (a convenience, not data).
let speed = 1;
try {
  const saved = Number(localStorage.getItem("speed"));
  if (SPEEDS.includes(saved)) speed = saved;
} catch (e) { /* storage blocked: start at 1x */ }

function speedLabel(v) {
  return `${String(v).replace(".", ",")}×`;
}

function setSpeed(v) {
  speed = v;
  for (const p of Object.values(players)) p.playbackRate = v;
  try { localStorage.setItem("speed", String(v)); } catch (e) { /* not remembered */ }
  if (view.speed) view.speed.classList.toggle("on", v !== 1);
}

function stopAll() {
  for (const p of Object.values(players)) p.pause();
}

function playing() {
  return Object.values(players).find(p => !p.paused) || null;
}

function duration() {
  const segs = rec ? rec.segments : [];
  return (rec && rec.summary.duration) || (segs.length ? segs[segs.length - 1].end : 0);
}

function play(word, until) {
  const p = players[word.channel];
  if (!p) return;
  for (const [c, q] of Object.entries(players)) if (c !== word.channel) q.pause();
  p.currentTime = Math.max(0, word.start - LEAD);
  stopAt = until === undefined ? null : { channel: word.channel, t: until };
  lastChannel = word.channel;
  p.play().catch(() => {});
  target = word;
  mark(word.el);
}

function togglePlay() {
  const p = playing();
  if (p) { p.pause(); return; }
  const w = current && words.find(w => w.el === current);
  const channel = w ? w.channel : lastChannel || Object.keys(players)[0];
  const q = players[channel];
  if (q) { stopAt = null; lastChannel = channel; q.play().catch(() => {}); }
}

function seek(seconds) {
  // Jump to the word being said at that time (on any channel), or just there.
  const before = words.filter(w => w.start <= seconds);
  const w = before.length ? before.reduce((a, b) => (b.start > a.start ? b : a)) : words[0];
  if (w) play(w);
}

function mark(e) {
  if (current) current.classList.remove("now");
  current = e;
  if (e) e.classList.add("now");
}

function follow(channel) {
  const p = players[channel];
  const t = p.currentTime;
  if (stopAt && stopAt.channel === channel && t >= stopAt.t) {
    p.pause();
    stopAt = null;
  }
  if (channel === lastChannel) updateProgress(t);
  // Playback starts LEAD seconds early: keep the chosen word highlighted until it is reached.
  if (target && target.channel === channel && t < target.start) return;
  target = null;
  const w = words.find(w => w.channel === channel && w.start <= t && t < w.end);
  if (w && w.el !== current) mark(w.el);
}

function updateProgress(t) {
  if (!view.done) return;
  const total = duration();
  view.done.style.width = total ? `${Math.min(100, (t / total) * 100)}%` : "0";
  view.clock.textContent = `${clock(t)} / ${clock(total)}`;
}

function updatePlayButton() {
  if (!view.play) return;
  const on = !!playing();
  view.play.replaceChildren(icon(on ? "pause" : "play", 14));
  view.play.setAttribute("aria-label", on ? "Pausa" : "Riproduci");
  view.play.title = on ? "Pausa (spazio)" : "Riproduci (spazio)";
}

async function post(action, body) {
  return postJSON(`/api/recordings/${enc(recName)}/${action}`, body);
}

function wordAt(seg, k) {
  return words.find(w => w.seg === seg && w.k === k);
}

function openEditor(seg, start, end, autoplay) {
  closeEditor();
  const first = wordAt(seg, start);
  if (!first) return;
  editing = { seg, start, end };
  const text = rec.segments[seg].words.slice(start, end).map(w => w.text).join(" ");
  const input = el("input", { class: "edit", value: text, size: Math.max(6, text.length + 2),
                              "aria-label": "Correggi",
                              title: "Invio: salva (senza modifiche conferma) · Esc: chiudi" });
  first.el.before(input);
  for (let k = start; k < end; k++) wordAt(seg, k).el.classList.add("editing");
  input.addEventListener("keydown", async e => {
    if (e.key === "Escape") {
      e.preventDefault();
      const p = playing();
      if (p) p.pause();
      closeEditor();
    } else if (e.key === "Enter") {
      e.preventDefault();
      try {
        await render(await post("correct", { segment: seg, start, end, text: input.value }),
                     { seg, start, auto: true });
      } catch (err) { toast(err.message); }
    } else if (e.key === " " && e.ctrlKey) { e.preventDefault(); playRun(seg, start, end); }
  });
  input.focus();
  input.select();
  first.el.scrollIntoView({ block: "center", behavior: "smooth" });
  if (autoplay) playRun(seg, start, end);
}

function playRun(seg, start, end) {
  const first = wordAt(seg, start), last = wordAt(seg, end - 1);
  if (first) play(first, (last || first).end + EXCERPT_TAIL);
}

function closeEditor() {
  document.querySelectorAll("input.edit").forEach(i => i.remove());
  document.querySelectorAll(".editing").forEach(e => e.classList.remove("editing"));
  editing = null;
}

function nextRun(direction, from) {
  if (!runs.length) return null;
  const pos = from ?? (current ? (words.find(w => w.el === current) || {}).start ?? -1 : -1);
  const ordered = [...runs].sort((a, b) => a.t - b.t);
  const found = direction > 0 ? ordered.find(r => r.t > pos + 0.01)
                              : [...ordered].reverse().find(r => r.t < pos - 0.01);
  return found || (direction > 0 ? ordered[0] : ordered[ordered.length - 1]);
}

function jump(direction) {
  const r = nextRun(direction);
  if (r) openEditor(r.seg, r.start, r.end, true);
}

async function undo() {
  try { await render(await post("undo"), {}); } catch (e) { toast("Niente da annullare."); }
}

function renderHeading() {
  const s = rec.summary;
  const h1 = el("h1", { title: `${s.title} (doppio clic per rinominare)` }, s.title);
  h1.addEventListener("dblclick", () => renameInPlace(h1, s));
  const when = new Date(s.started_at).toLocaleString("it-IT",
    { weekday: "long", day: "numeric", month: "long", year: "numeric", hour: "2-digit",
      minute: "2-digit" });
  const who = s.channels.map(c => LABELS[c] ?? c).filter(Boolean).join(" e ");
  const meta = `${when} · ${clock(s.duration)} · ${s.words.toLocaleString("it-IT")} parole` +
               (who ? ` · ${who}` : "") + (s.source ? ` · da ${s.source}` : "");
  view.heading.replaceChildren(h1, el("div", { class: "meta" }, meta));
}

function exportMenu(anchor) {
  const link = (f, label) => el("a", { role: "menuitem", href: `/export/${enc(recName)}.${f}` },
    label);
  popMenu(anchor,
    link("txt", "Testo (.txt)"), link("md", "Markdown (.md)"), link("docx", "Word (.docx)"),
    link("json", "Dati (.json)"), el("hr"),
    el("button", { role: "menuitem", onclick: () => window.print() }, "Stampa o salva PDF"));
}

function relabel() {
  // The speaker is written only when it changes, counting only the visible lines.
  let prev = null;
  for (const turn of view.body.querySelectorAll(".turn")) {
    if (turn.classList.contains("hidden")) continue;
    const who = turn.querySelector(".who");
    who.hidden = !who.textContent || turn.dataset.channel === prev;
    prev = turn.dataset.channel;
  }
}

function applyFilter() {
  for (const turn of view.body.querySelectorAll(".turn")) {
    turn.classList.toggle("hidden", onlyDoubts && turn.dataset.doubt !== "true");
  }
  view.filter.classList.toggle("on", onlyDoubts);
  view.filter.setAttribute("aria-pressed", onlyDoubts);
  relabel();
}

async function render(data, after) {
  const scrollY = view.scroll ? view.scroll.scrollTop : 0;
  rec = data;
  words = [];
  runs = [];
  current = null;
  editing = null;
  view = {};

  const body = el("div", { class: "transcript" });
  rec.segments.forEach((seg, si) => {
    const channel = seg.channel || "mic";
    const text = el("div", { class: "text" });
    const list = seg.words.length ? seg.words : [{ text: seg.text, start: seg.start, end: seg.end }];
    list.forEach((w, k) => {
      const start = w.start ?? seg.start, end = w.end ?? seg.end;
      const span = el("span", { class: "w" + (w.doubtful ? " doubt" : "") }, w.text);
      if (w.doubtful) span.title = "Dubbia: la seconda trascrizione dice altro";
      const word = { el: span, channel, start, end, doubtful: !!w.doubtful, seg: si, k };
      span.addEventListener("click", () => play(word));
      span.addEventListener("dblclick", e => {
        e.preventDefault();
        const run = runs.find(r => r.seg === si && r.start <= k && k < r.end);
        if (run) openEditor(si, run.start, run.end, true);
        else openEditor(si, k, k + 1, true);
      });
      words.push(word);
      text.append(span, k < list.length - 1 ? " " : "");
      if (w.doubtful && !(k > 0 && list[k - 1].doubtful)) {
        let e = k;
        while (e < list.length && list[e].doubtful) e++;
        runs.push({ seg: si, start: k, end: e, t: start, channel });
      }
    });
    const first = words[words.length - list.length];
    // lang per line: an English line is hyphenated and read aloud as English.
    body.append(el("div", { class: "turn", lang: seg.lang || null, "data-channel": channel,
                            "data-doubt": seg.words.some(w => w.doubtful) },
      el("div", { class: `who ${channel}` }, LABELS[channel] ?? channel),
      el("span", { class: "t", onclick: () => play(first) }, clock(seg.start)),
      text));
  });
  if (runs.length) {
    body.prepend(el("p", { class: "hint" },
      "Clic su una parola per ascoltarla. ", el("kbd", {}, "N"), " passa alla prossima dubbia, ",
      el("kbd", {}, "Invio"), " salva o conferma, ", el("kbd", {}, "Esc"), " chiude, ",
      el("kbd", {}, "⌘Z"), " annulla."));
  }

  view.heading = el("div", { class: "heading" });
  view.filter = iconButton("filter", "Solo le righe con parole dubbie",
    () => { onlyDoubts = !onlyDoubts; applyFilter(); });
  const more = iconButton("more", "Esporta", e => { e.stopPropagation(); exportMenu(actions); });
  const undoBtn = iconButton("undo", "Annulla l'ultima modifica (⌘Z)", undo);
  undoBtn.disabled = !rec.summary.edits;
  const actions = el("div", { class: "actions" }, view.filter, undoBtn, more);
  view.findInput = el("input", { class: "find-input", type: "search", placeholder: "Trova nella call",
                                 "aria-label": "Trova nella call", autocomplete: "off" });
  view.findCount = el("span", { class: "find-count", "aria-live": "polite" });
  view.findInput.addEventListener("input", () => {
    find = { q: view.findInput.value, index: 0, hits: [] };
    applyFind(true);
  });
  view.findInput.addEventListener("keydown", e => {
    e.stopPropagation();
    if (e.key === "Enter") { e.preventDefault(); stepFind(e.shiftKey ? -1 : 1); }
    else if (e.key === "Escape") { e.preventDefault(); closeFind(); }
  });
  view.find = el("div", { class: "findbar", hidden: true }, view.findInput, view.findCount,
    iconButton("prev", "Precedente (Maiusc-Invio)", () => stepFind(-1)),
    iconButton("next", "Successiva (Invio)", () => stepFind(1)),
    iconButton("close", "Chiudi la ricerca (Esc)", closeFind));
  const head = el("header", { class: "call-head" },
    el("div", { class: "head-row" }, view.heading, actions), view.find);

  view.body = body;
  view.scroll = el("div", { class: "scroll" }, body);

  const total = duration();
  view.play = el("button", { class: "play", onclick: togglePlay });
  view.clock = el("span", { class: "clock" });
  view.done = el("div", { class: "done" });
  const timeline = el("div", { class: "timeline", title: "Vai a questo punto" },
    el("div", { class: "track" }), view.done,
    ...runs.map(r => {
      const tick = el("i", { class: "tick" });
      tick.style.left = `${total ? (r.t / total) * 100 : 0}%`;
      return tick;
    }));
  timeline.addEventListener("click", e => {
    const box = timeline.getBoundingClientRect();
    seek(((e.clientX - box.left) / box.width) * total);
  });
  const review = runs.length
    ? el("div", { class: "review" }, iconButton("prev", "Dubbia precedente (P)", () => jump(-1)),
         el("b", {}, String(runs.length)), "da rivedere",
         iconButton("next", "Prossima dubbia (N)", () => jump(1)))
    : el("div", { class: "review clear" }, el("b", {}, "✓"), "Tutto rivisto");
  view.speed = el("select", { class: "speed", title: "Velocità di riproduzione",
                              "aria-label": "Velocità di riproduzione",
                              onchange: e => setSpeed(Number(e.target.value)) },
    ...SPEEDS.map(v => el("option", { value: String(v), selected: v === speed }, speedLabel(v))));
  view.speed.classList.toggle("on", speed !== 1);
  const player = el("footer", { class: "player" }, view.play, view.clock, timeline, view.speed,
    review);

  $main.replaceChildren(head, view.scroll, player);
  renderHeading();
  applyFilter();
  updatePlayButton();
  if (find) applyFind(false);
  const p = lastChannel && players[lastChannel];
  updateProgress(p ? p.currentTime : 0);

  if (after && after.seg !== undefined) {
    view.scroll.scrollTop = scrollY;
    if (after.auto) {
      const w = wordAt(after.seg, Math.min(after.start, rec.segments[after.seg].words.length - 1));
      const r = nextRun(1, w ? w.start - 0.02 : undefined);
      if (r) openEditor(r.seg, r.start, r.end, true);
    }
  } else if (after) view.scroll.scrollTop = scrollY;

  // Counts in the sidebar follow the edits.
  const item = calls.find(c => c.name === recName);
  if (item && item.to_review !== rec.summary.to_review) {
    item.to_review = rec.summary.to_review;
    renderCalls();
  }
}

// ---------------------------------------------------------------- find in the call

let find = null;  // {q, index, hits: [[word, ...], ...]} while the find bar is open

function fold(text) {
  // Same as parola.search.fold: lowercase, no accents, no punctuation at the edges.
  return text.normalize("NFKD").replace(/[\u0300-\u036f]/g, "").toLowerCase()
    .replace(/^[^\p{L}\p{N}_]+|[^\p{L}\p{N}_]+$/gu, "");
}

function forms(text) {
  // "dell'impatto" is found by itself and by "impatto".
  const f = fold(text);
  const m = f.match(/^[\p{L}\p{N}_]+['\u2019]([\p{L}\p{N}_].*)$/u);
  return m ? [f, m[1]] : [f];
}

function findHits(q) {
  const tokens = q.split(/\s+/).map(fold).filter(Boolean);
  if (!tokens.length) return [];
  const hits = [];
  const bySeg = new Map();
  for (const w of words) {
    if (!bySeg.has(w.seg)) bySeg.set(w.seg, []);
    bySeg.get(w.seg).push(w);
  }
  for (const list of bySeg.values()) {
    const alts = list.map(w => forms(w.el.textContent));
    for (let k = 0; k + tokens.length <= list.length; k++) {
      if (tokens.every((t, i) => alts[k + i].includes(t))) hits.push(list.slice(k, k + tokens.length));
    }
  }
  return hits;
}

function openFind(q, index = 0, focus = false) {
  if (!view.find) return;
  view.findInput.value = q;
  view.find.hidden = false;
  find = { q, index, hits: [] };
  applyFind(true);
  if (focus || !q) { view.findInput.focus(); view.findInput.select(); }
}

function closeFind() {
  find = null;
  document.querySelectorAll(".w.hit").forEach(e => e.classList.remove("hit", "hit-now"));
  if (view.find) view.find.hidden = true;
}

function applyFind(scroll) {
  if (!view.find) return;
  document.querySelectorAll(".w.hit").forEach(e => e.classList.remove("hit", "hit-now"));
  view.find.hidden = false;
  if (view.findInput.value !== find.q) view.findInput.value = find.q;
  find.hits = findHits(find.q);
  const n = find.hits.length;
  find.index = n ? ((find.index % n) + n) % n : 0;
  for (const hit of find.hits) for (const w of hit) w.el.classList.add("hit");
  view.findCount.textContent = !find.q.trim() ? "" : n ? `${find.index + 1} di ${n}` : "nessuna";
  if (!n) return;
  const current = find.hits[find.index];
  for (const w of current) w.el.classList.add("hit-now");
  if (scroll) current[0].el.scrollIntoView({ block: "center", behavior: "smooth" });
}

function stepFind(direction) {
  if (!find || !find.hits.length) return;
  find.index += direction;
  applyFind(true);
}

async function showRecording(name) {
  stopAll();
  find = null;  // a search belongs to the call it was made in
  recName = name;
  renderCalls();
  const data = await getJSON(`/api/recordings/${enc(name)}`);
  players = {};
  lastChannel = null;
  $audio.replaceChildren();
  for (const [channel, url] of Object.entries(data.audio)) {
    const a = el("audio", { preload: "metadata", src: url });
    a.addEventListener("timeupdate", () => follow(channel));
    a.addEventListener("play", updatePlayButton);
    a.addEventListener("pause", updatePlayButton);
    a.playbackRate = speed;
    // Some browsers reset the rate when the source loads.
    a.addEventListener("loadedmetadata", () => { a.playbackRate = speed; });
    players[channel] = a;
    $audio.append(a);
  }
  lastChannel = Object.keys(players)[0] || null;
  view = {};
  await render(data);
}

function showEmpty() {
  stopAll();
  players = {};
  $audio.replaceChildren();
  rec = recName = null;
  view = {};
  renderCalls();
  $main.replaceChildren(el("div", { class: "placeholder" },
    ...(calls.length
      ? [el("h2", {}, "Scegli una call"), el("p", {}, "Oppure registrane una nuova.")]
      : [el("h2", {}, "Nessuna call"),
         el("p", {}, "Premi Registra: l'audio e la trascrizione restano su questo Mac.")])));
}

// ---------------------------------------------------------------- recorder

let recState = { state: "idle" };
let recAt = 0;          // when recState arrived, to keep the clock running between polls
let recLang = "";
let recMode = null;     // what the recorder shows now, to rebuild only when it changes
let liveViews = [];     // the recorder in the sidebar and, if open, in the floating window
let pip = null;         // floating window (Document Picture-in-Picture)
let pollTimer = null;

async function recAction(action, body) {
  try {
    setRecState(await postJSON(`/api/record/${action}`, body));
    if (action === "start") openFloating(true);
  } catch (e) { toast(e.message); }
}

function liveElapsed() {
  const st = recState;
  if (st.state !== "recording") return 0;
  return st.elapsed + (st.paused ? 0 : (Date.now() - recAt) / 1000);
}

function meter() {
  const fill = el("i");
  return { root: el("div", { class: "meter" }, fill), fill };
}

function buildLive(floating) {
  // The recording controls; built with this document but also moved into the floating window.
  const dot = el("span", { class: "rec-dot" });
  const time = el("span", { class: "rec-time" });
  const mic = meter(), system = meter();
  const meters = el("div", { class: "meters", title: "Livelli: Io, Altri" },
    mic.root, system.root);
  const pause = el("button", { class: "icon-btn" });
  const stop = iconButton("stop", "Ferma e trascrivi", () => recAction("stop"), "rec-stop");
  const pop = floating ? null : iconButton("popout", "Finestra mobile", () => openFloating(false));
  const root = el("div", { class: floating ? "rec-live pip-bar" : "rec-live" },
    dot, time, meters, pause, pop, stop);
  return {
    root,
    update(st) {
      dot.classList.toggle("blink", !st.paused);
      dot.style.opacity = st.paused ? "0.35" : "";
      time.textContent = clock(liveElapsed());
      const lv = st.levels || {};
      for (const [m, db] of [[mic, lv.mic], [system, lv.system]]) {
        // -60 dBFS (empty) .. 0 dBFS (full)
        const v = db === undefined ? 0 : Math.max(0, Math.min(1, (db + 60) / 60));
        m.fill.style.width = `${Math.round(v * 100)}%`;
      }
      const label = st.paused ? "Riprendi" : "Pausa";
      pause.replaceChildren(icon(st.paused ? "play" : "pause", 14));
      pause.title = label;
      pause.setAttribute("aria-label", label);
      pause.onclick = () => recAction(st.paused ? "resume" : "pause");
    },
  };
}

function renderRecorder() {
  const st = recState;
  // While a file uploads or a call is transcribed the controls stay, disabled: the progress is
  // on the call itself, at the top of the list (renderPending).
  const busy = !!uploading || st.state === "transcribing";
  const mode = st.state === "recording" ? "recording" : `idle:${st.state}:${st.name}:${busy}`;
  renderPending();
  if (mode !== recMode) {
    recMode = mode;
    liveViews = liveViews.filter(v => v.floating);
    if (mode === "recording") {
      const v = buildLive(false);
      liveViews.push(v);
      $recorder.replaceChildren(v.root);
    } else {
      closeFloating();
      const lang = el("select", { class: "lang", title: "Lingua della call",
                                  "aria-label": "Lingua della call",
                                  onchange: e => { recLang = e.target.value; } },
        ...LANGS.map(([v, label]) => el("option", { value: v, selected: v === recLang }, label)));
      const start = el("button", { class: "rec-start", disabled: busy,
                                   title: busy ? "Trascrizione in corso" : null,
                                   onclick: () => recAction("start", { lang: recLang || null }) },
        el("span", { class: "rec-dot" }), "Registra");
      const pick = iconButton("upload", "Trascrivi un file audio o video", () => $file.click(),
                              "rec-import");
      pick.disabled = busy;
      const note = busy ? null : st.state === "done" && st.name
        ? el("p", { class: "rec-note" }, "Trascritta: ",
             el("a", { href: `#/rec/${enc(st.name)}` }, "apri"))
        : st.state === "error" ? el("p", { class: "rec-note err" }, st.message) : null;
      $recorder.replaceChildren(el("div", { class: "rec-row" }, start, pick, lang), note || "");
    }
  }
  if (mode === "recording") for (const v of liveViews) v.update(st);
}

const pendingView = {};

function renderPending() {
  // The call being uploaded or transcribed, at the top of the list, until it is ready.
  let title, text, pct;
  if (uploading) {
    title = uploading.name;
    pct = uploading.pct;
    text = `Caricamento… ${pct}%`;
  } else if (recState.state === "transcribing") {
    title = recState.source ? recState.source.replace(/\.[^.]+$/, "") : "Registrazione";
    const [done, total] = recState.step || [0, 0];
    pct = total ? Math.min(99, Math.round((done / total) * 100)) : 0;
    text = recState.message === "conversione" ? "Conversione…" : `Trascrizione… ${pct}%`;
  } else {
    $pending.hidden = true;
    return;
  }
  if (!pendingView.title) {
    pendingView.title = el("span", { class: "title" });
    pendingView.text = el("span", { class: "sub" });
    pendingView.bar = el("i");
    $pending.replaceChildren(el("div", { class: "group" }, "In corso"),
      el("div", { class: "pending-call" }, el("span", { class: "pending-dot blink" }),
        el("div", { class: "pending-body" }, pendingView.title, pendingView.text,
          el("div", { class: "bar" }, pendingView.bar))));
  }
  $pending.hidden = false;
  pendingView.title.textContent = title;
  pendingView.text.textContent = text;
  pendingView.bar.style.width = `${pct}%`;
}

function setRecState(st) {
  const prev = recState;
  recState = st;
  recAt = Date.now();
  renderRecorder();
  if (prev.state === "transcribing" && st.state === "done") {
    const open = !rec || st.name === imported;  // a file you just imported opens by itself
    imported = null;
    refreshCalls().then(() => { if (open && st.name) location.hash = `#/rec/${enc(st.name)}`; });
  }
}

// ---------------------------------------------------------------- importing a file

const $file = el("input", { type: "file", accept: "audio/*,video/*", hidden: true,
                            onchange: e => { if (e.target.files[0]) importFile(e.target.files[0]); } });
document.body.append($file);
let uploading = null;   // {name, pct} while a file is being sent
let imported = null;    // name of the call being imported from this window

function importFile(file) {
  // The raw file goes in the request body (no form encoding); progress from XHR.
  if (["recording", "transcribing"].includes(recState.state) || uploading) {
    toast("Aspetta che finisca la registrazione o la trascrizione in corso.");
    return;
  }
  uploading = { name: file.name.replace(/\.[^.]+$/, ""), pct: 0 };
  renderRecorder();
  const params = new URLSearchParams({ filename: file.name, modified: String(file.lastModified) });
  if (recLang) params.set("lang", recLang);
  const xhr = new XMLHttpRequest();
  xhr.open("POST", `/api/import?${params}`);
  xhr.upload.onprogress = e => {
    if (!e.lengthComputable || !uploading) return;
    uploading.pct = Math.round((e.loaded / e.total) * 100);
    renderPending();
  };
  xhr.onload = () => {
    uploading = null;
    $file.value = "";
    let data = {};
    try { data = JSON.parse(xhr.responseText); } catch (e) { /* not JSON */ }
    recMode = null;
    if (xhr.status >= 300) {
      renderRecorder();
      toast(`File non importato: ${data.detail || xhr.status}`);
      return;
    }
    imported = data.name;
    setRecState(data);
    poll();
  };
  xhr.onerror = () => {
    uploading = null;
    recMode = null;
    renderRecorder();
    toast("File non importato: il server non risponde.");
  };
  xhr.send(file);
}

// Drop a file anywhere on the window.
let dragDepth = 0;
const $drop = el("div", { class: "drop", hidden: true },
  el("div", {}, el("strong", {}, "Rilascia per trascrivere"),
    el("span", {}, "Audio o video: resta su questo Mac.")));
document.body.append($drop);
const hasFiles = e => [...(e.dataTransfer?.types || [])].includes("Files");
window.addEventListener("dragenter", e => {
  if (!hasFiles(e)) return;
  e.preventDefault();
  dragDepth++;
  $drop.hidden = false;
});
window.addEventListener("dragover", e => { if (hasFiles(e)) e.preventDefault(); });
window.addEventListener("dragleave", e => {
  if (!hasFiles(e)) return;
  dragDepth = Math.max(0, dragDepth - 1);
  if (!dragDepth) $drop.hidden = true;
});
window.addEventListener("drop", e => {
  if (!hasFiles(e)) return;
  e.preventDefault();
  dragDepth = 0;
  $drop.hidden = true;
  const file = e.dataTransfer.files[0];
  if (file) importFile(file);
});

async function openFloating(auto) {
  if (pip) { pip.focus(); return; }
  if (!("documentPictureInPicture" in window)) {
    if (!auto) toast("La finestra mobile funziona in Chrome e in Edge.");
    return;
  }
  try {
    pip = await window.documentPictureInPicture.requestWindow({ width: 220, height: 52 });
  } catch (e) {
    if (!auto) toast("Finestra mobile non disponibile.");
    return;
  }
  const doc = pip.document;
  doc.head.append(el("link", { rel: "stylesheet", href: `${location.origin}/static/style.css` }));
  doc.title = "P.A.R.O.L.A.";
  doc.body.className = "pip";
  const v = buildLive(true);
  v.floating = true;
  liveViews.push(v);
  doc.body.append(v.root);
  v.update(recState);
  pip.addEventListener("pagehide", () => {
    pip = null;
    liveViews = liveViews.filter(x => x !== v);
  });
}

function closeFloating() {
  if (pip) pip.close();
}

async function poll() {
  try { setRecState(await getJSON("/api/record/status")); } catch (e) { /* server restarting */ }
  const active = ["recording", "transcribing"].includes(recState.state);
  clearTimeout(pollTimer);
  // The floating window stays visible when this tab is in the background: tick from there.
  pollTimer = (pip || window).setTimeout(poll, active ? 250 : 3000);
}

// ---------------------------------------------------------------- routing and keys

async function route() {
  const m = location.hash.match(/^#\/rec\/([^?]+)(?:\?(.*))?$/);
  try {
    if (m) {
      const name = decodeURIComponent(m[1]);
      const params = new URLSearchParams(m[2] || "");
      // Another hit in the call already open: no reload, the audio keeps its place.
      if (name !== recName || !rec) await showRecording(name);
      else renderCalls();
      if (params.get("q")) openFind(params.get("q"), Number(params.get("hit") || 0));
    } else showEmpty();
  } catch (e) {
    $main.replaceChildren(el("div", { class: "placeholder" },
      el("h2", {}, "Non trovata"), el("p", {}, e.message)));
  }
}

document.addEventListener("keydown", e => {
  if ((e.metaKey || e.ctrlKey) && e.key === "k") { e.preventDefault(); $search.focus(); return; }
  if ((e.metaKey || e.ctrlKey) && e.key === "f" && rec) {
    e.preventDefault();
    openFind(find ? find.q : "", find ? find.index : 0, true);
    return;
  }
  if (["INPUT", "SELECT", "TEXTAREA"].includes(e.target.tagName)) return;
  if (!Object.keys(players).length) return;
  if (e.key === " ") { e.preventDefault(); togglePlay(); }
  else if (e.key === "Escape") { const p = playing(); if (p) p.pause(); }
  else if (e.key === "n" || e.key === "N") { e.preventDefault(); jump(1); }
  else if (e.key === "p" || e.key === "P") { e.preventDefault(); jump(-1); }
  else if (e.key === "ArrowRight" || e.key === "ArrowLeft") {
    const p = players[lastChannel];
    if (p) p.currentTime = Math.max(0, p.currentTime + (e.key === "ArrowRight" ? 5 : -5));
  } else if ((e.metaKey || e.ctrlKey) && e.key === "z") { e.preventDefault(); undo(); }
});

window.addEventListener("hashchange", route);
refreshCalls().catch(() => {}).then(route);
poll();
