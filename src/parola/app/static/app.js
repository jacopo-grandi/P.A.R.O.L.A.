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
  people: '<circle cx="9" cy="8" r="3.2"/><path d="M3.5 19c.6-3.2 2.8-5 5.5-5s4.9 1.8 5.5 5"/>' +
          '<circle cx="17" cy="9" r="2.4"/><path d="M15.8 14.2c2.4.1 4 1.7 4.7 4.3"/>',
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
let gains = {};      // channel -> linear playback gain (1 = as recorded)
let audioCtx = null; // Web Audio, created on the first boosted play (a user gesture)
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

// A quiet channel is raised at playback only, never in the stored file: the element is
// routed through a gain and a limiter (a boosted track can hold a full-scale pop that a
// bare gain would clip). Wired lazily on the first play — a user gesture, so the context
// may start — and only when there is something to raise: WebKit routes a wired element
// through the context alone, so the others keep the plain path.
function amplify(channel) {
  const p = players[channel];
  const g = gains[channel] || 1;
  const Ctx = window.AudioContext || window.webkitAudioContext;
  if (!p || g === 1 || p.dataset.wired || !Ctx) return;
  try {
    audioCtx = audioCtx || new Ctx();
    const source = audioCtx.createMediaElementSource(p);
    const gain = audioCtx.createGain();
    gain.gain.value = g;
    const limiter = audioCtx.createDynamicsCompressor();
    limiter.threshold.value = -1; // squash only what would clip
    limiter.knee.value = 0;
    limiter.ratio.value = 20;
    limiter.attack.value = 0.001;
    limiter.release.value = 0.05;
    source.connect(gain);
    gain.connect(limiter);
    limiter.connect(audioCtx.destination);
    p.dataset.wired = "1";
  } catch (e) { /* no Web Audio: play as recorded */ }
  if (audioCtx && audioCtx.state === "suspended") audioCtx.resume().catch(() => {});
}

function play(word, until) {
  const p = players[word.channel];
  if (!p) return;
  for (const [c, q] of Object.entries(players)) if (c !== word.channel) q.pause();
  amplify(word.channel);
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
  if (q) { stopAt = null; lastChannel = channel; amplify(channel); q.play().catch(() => {}); }
}

function seek(seconds) {
  // Jump to the word being said at that time (on any channel), or just there, and show it.
  const before = words.filter(w => w.start <= seconds);
  const w = before.length ? before.reduce((a, b) => (b.start > a.start ? b : a)) : words[0];
  if (w) { play(w); keepInView(w.el, true); }
}

// The transcript follows the word being played. When the person scrolls it (to read ahead or
// back) it waits FOLLOW_PAUSE before following again; a click on the timeline always shows it.
const FOLLOW_PAUSE = 4000;  // ms
let scrolledByHand = 0;

function keepInView(e, force) {
  const box = view.scroll;
  if (!box || !e || (!force && Date.now() - scrolledByHand < FOLLOW_PAUSE)) return;
  const r = e.getBoundingClientRect(), b = box.getBoundingClientRect();
  const margin = b.height * 0.15;
  if (r.top < b.top + margin || r.bottom > b.bottom - margin) {
    e.scrollIntoView({ block: "center", behavior: "smooth" });
  }
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
  if (w && w.el !== current) {
    mark(w.el);
    if (!p.paused) keepInView(w.el);
  }
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
  if (rec.provisional) return;  // read-only until the final transcript is written
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
    else if (e.key === "Tab" && suggestions.length) {
      e.preventDefault();  // Tab takes the first suggestion; Enter still decides
      useSuggestion(input, suggestions[0]);
    }
  });
  input.focus();
  input.select();
  first.el.scrollIntoView({ block: "center", behavior: "smooth" });
  if (autoplay) playRun(seg, start, end);
  showSuggestions(input, text, editing);
}

// Terms learned from your own corrections (decision 0025): offered, never applied.
let suggestions = [];

async function showSuggestions(input, text, opened) {
  suggestions = [];
  let found = [];
  try { found = await getJSON(`/api/suggestions?text=${enc(text)}`); } catch (e) { return; }
  if (editing !== opened || !found.length) return;  // the editor moved on meanwhile
  suggestions = found;
  const box = el("span", { class: "suggest", role: "group", "aria-label": "Suggerimenti" },
    ...found.map((s, i) => el("button", {
      class: "chip", title: `Hai corretto così ${s.count} volte${i === 0 ? " · Tab per usarlo" : ""}`,
      onmousedown: e => e.preventDefault(),  // keep the focus in the field
      onclick: () => useSuggestion(input, s) }, s.term, el("span", { class: "n" }, `×${s.count}`))));
  input.after(box);
}

function useSuggestion(input, s) {
  input.value = s.text;
  input.size = Math.max(6, s.text.length + 2);
  input.focus();
}

function playRun(seg, start, end) {
  const first = wordAt(seg, start), last = wordAt(seg, end - 1);
  if (first) play(first, (last || first).end + EXCERPT_TAIL);
}

function closeEditor() {
  document.querySelectorAll("input.edit, .suggest").forEach(i => i.remove());
  suggestions = [];
  document.querySelectorAll(".editing").forEach(e => e.classList.remove("editing"));
  editing = null;
}

function nextRun(direction, from) {
  const pos = from ?? (current ? (words.find(w => w.el === current) || {}).start ?? -1 : -1);
  return pickRun(runs, direction, pos);
}

function jump(direction) {
  const r = nextRun(direction);
  if (r) openEditor(r.seg, r.start, r.end, true);
}

async function undo() {
  if (!rec || rec.provisional) return;
  try { await render(await post("undo"), {}); } catch (e) { toast("Niente da annullare."); }
}

function renderHeading() {
  const s = rec.summary;
  const h1 = el("h1", { title: rec.provisional ? s.title : `${s.title} (doppio clic per rinominare)` },
                s.title);
  if (!rec.provisional) h1.addEventListener("dblclick", () => renameInPlace(h1, s));
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
    who.hidden = !who.textContent || turn.dataset.key === prev;
    prev = turn.dataset.key;
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
    runs.push(...doubtfulRuns(list, si, channel, seg.start));
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
    });
    const first = words[words.length - list.length];
    // lang per line: an English line is hyphenated and read aloud as English.
    const voiced = VOICED.includes(channel) && Object.keys(rec.voices || {}).length > 0;
    const key = showVoices && seg.speaker ? seg.speaker : channel;
    const who = showVoices && seg.speaker
      ? el("button", { class: `who voice ${channel}`, title: "Clic per dare un nome a questa voce",
                       onclick: e => renameVoice(e.currentTarget, seg.speaker) },
          rec.voices[seg.speaker] || seg.speaker)
      : el("div", { class: `who ${channel}` }, LABELS[channel] ?? channel);
    body.append(el("div", { class: "turn", lang: seg.lang || null, "data-channel": channel,
                            // String(), not the boolean: el() writes `true` as an empty
                            // attribute, and the doubts filter compares against "true".
                            "data-key": key, "data-doubt": String(seg.words.some(w => w.doubtful)) },
      who,
      // The voice menu lives in the time column: its clicks must not start the audio.
      el("span", { class: "t", onclick: e => { if (!e.target.closest(".menu, .turn-voice")) play(first); } },
        clock(seg.start),
        voiced && showVoices ? el("button", {
          class: "turn-voice", title: "Di chi è questa battuta", "aria-label": "Cambia voce",
          onclick: e => { e.stopPropagation(); voiceMenu(e.currentTarget, si); } }, "•") : null),
      text));
  });
  if (rec.provisional) {
    // Whisper is done, the rest is still running (decision 0031): the text can be read and
    // listened to, and is replaced by the final one, so nothing can be corrected yet.
    view.stage = el("span", { class: "stage" });
    body.prepend(el("p", { class: "hint provisional" },
      rec.provisional === "partial"
        ? "Whisper sta ancora trascrivendo: il testo cresce man mano, poi arrivano parole " +
          "dubbie e chi parla. "
        : rec.provisional === "doubts"
          ? "Testo provvisorio con le parole dubbie: chi parla arriva tra poco. "
          : "Testo provvisorio: parole dubbie e chi parla arrivano tra poco. ",
      "Puoi leggerlo e ascoltarlo; le correzioni quando è pronto.", view.stage));
  } else if (runs.length) {
    body.prepend(el("p", { class: "hint" },
      "Clic su una parola per ascoltarla. ", el("kbd", {}, "N"), " passa alla prossima dubbia, ",
      el("kbd", {}, "Invio"), " salva o conferma, ", el("kbd", {}, "Esc"), " chiude, ",
      el("kbd", {}, "⌘Z"), " annulla."));
  }

  view.heading = el("div", { class: "heading" });
  view.filter = iconButton("filter", "Solo le righe con parole dubbie",
    () => { onlyDoubts = !onlyDoubts; applyFilter(); });
  // Voices (decision 0026): shown by default, hidden with one click when they are more noise
  // than help; the choice is remembered in this browser.
  const voicesBtn = Object.keys(rec.voices || {}).length
    ? iconButton("people", showVoices ? "Nascondi chi parla" : "Mostra chi parla", () => {
        showVoices = !showVoices;
        try { localStorage.setItem("voices", showVoices ? "1" : "0"); } catch (e) { /* not kept */ }
        render(rec, {});
      }, showVoices ? "on-voices" : "")
    : null;
  const more = iconButton("more", "Esporta", e => { e.stopPropagation(); exportMenu(actions); });
  const undoBtn = iconButton("undo", "Annulla l'ultima modifica (⌘Z)", undo);
  undoBtn.disabled = !rec.summary.edits || !!rec.provisional;
  // Exports read the final file: none while the transcript is provisional.
  const actions = el("div", { class: "actions" }, voicesBtn, view.filter, undoBtn,
                     rec.provisional ? null : more);
  view.findInput = el("input", { class: "find-input", type: "search",
                                 placeholder: "Trova nella call  ⌘F",
                                 "aria-label": "Trova nella call", autocomplete: "off" });
  view.findCount = el("span", { class: "find-count", "aria-live": "polite" });
  view.findInput.addEventListener("input", () => {
    find = { q: view.findInput.value, index: 0, hits: [] };
    applyFind(true);
  });
  view.findInput.addEventListener("keydown", e => {
    e.stopPropagation();
    if (e.key === "Enter") { e.preventDefault(); stepFind(e.shiftKey ? -1 : 1); }
    else if (e.key === "Escape") { e.preventDefault(); closeFind(); view.findInput.blur(); }
  });
  // Always there, like the search field of a Mac app; the arrows show once something is typed.
  view.findNav = el("span", { class: "find-nav" }, view.findCount,
    iconButton("prev", "Precedente (Maiusc-Invio)", () => stepFind(-1)),
    iconButton("next", "Successiva (Invio)", () => stepFind(1)),
    iconButton("close", "Svuota la ricerca (Esc)", closeFind));
  view.find = el("div", { class: "findbar" }, view.findInput, view.findNav);
  view.findNav.hidden = true;
  const head = el("header", { class: "call-head" },
    el("div", { class: "head-row" }, view.heading, view.find, actions));

  view.body = body;
  view.scroll = el("div", { class: "scroll" }, body);
  const byHand = () => { scrolledByHand = Date.now(); };
  view.scroll.addEventListener("wheel", byHand, { passive: true });
  view.scroll.addEventListener("touchmove", byHand, { passive: true });
  view.scroll.addEventListener("pointerdown", e => { if (e.target === view.scroll) byHand(); });

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
  const review = rec.provisional
    ? el("div", { class: "review" }, ...(runs.length ? [el("b", {}, String(runs.length)), "dubbie · "] : []),
         "provvisoria")
    : runs.length
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
  renderPending();  // the stage line in the provisional banner

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

// ---------------------------------------------------------------- voices

const VOICED = ["system", "mixed"];  // channels that can hold several voices
let showVoices = true;
try { showVoices = localStorage.getItem("voices") !== "0"; } catch (e) { /* default: shown */ }

function renameVoice(button, id) {
  // The label becomes a field; Enter gives the voice its name for the whole call.
  const before = rec.voices[id] || id;
  const input = el("input", { class: "inline voice-input", value: before, maxlength: "60",
                              "aria-label": "Nome della voce" });
  button.replaceWith(input);
  input.focus();
  input.select();
  let done = false;
  const finish = async save => {
    if (done) return;
    done = true;
    const value = input.value.trim();
    if (save && value !== before) {
      try { await render(await postJSON(`/api/recordings/${enc(recName)}/voices`,
                                        { id, name: value }), {}); return; }
      catch (e) { toast(`Nome non salvato: ${e.message}`); }
    }
    input.replaceWith(button);
  };
  input.addEventListener("keydown", e => {
    e.stopPropagation();
    if (e.key === "Enter") { e.preventDefault(); finish(true); }
    else if (e.key === "Escape") { e.preventDefault(); finish(false); }
  });
  input.addEventListener("blur", () => finish(true));
}

function voiceMenu(anchor, segment) {
  // "Whose line is this?": the voices of this channel, a new one, nothing else.
  const seg = rec.segments[segment];
  const ids = Object.keys(rec.voices).filter(v => v.startsWith(`${seg.channel}:`));
  const move = async speaker => {
    try {
      await render(await postJSON(`/api/recordings/${enc(recName)}/speaker`,
                                  { segment, speaker }), {});
    } catch (e) { toast(`Voce non cambiata: ${e.message}`); }
  };
  const holder = anchor.parentElement;
  popMenu(holder,
    ...ids.map(v => el("button", { role: "menuitemradio", "aria-checked": String(v === seg.speaker),
                                   class: v === seg.speaker ? "current" : "",
                                   onclick: () => { if (v !== seg.speaker) move(v); } },
      rec.voices[v])),
    el("hr"),
    el("button", { role: "menuitem", onclick: () => move("new") }, "Nuova voce"));
}

// ---------------------------------------------------------------- find in the call

let find = null;  // {q, index, hits: [[word, ...], ...]} while the find bar is open

function findHits(q) {
  const bySeg = new Map();
  for (const w of words) {
    if (!bySeg.has(w.seg)) bySeg.set(w.seg, []);
    bySeg.get(w.seg).push(w);
  }
  const lists = [...bySeg.values()];
  return findMatches(q, lists.map(list => list.map(w => w.el.textContent)))
    .map(m => lists[m.seg].slice(m.start, m.end));
}

function openFind(q, index = 0, focus = false) {
  if (!view.find) return;
  view.findInput.value = q;
  find = { q, index, hits: [] };
  applyFind(true);
  if (focus || !q) { view.findInput.focus(); view.findInput.select(); }
}

function closeFind() {
  find = null;
  document.querySelectorAll(".w.hit").forEach(e => e.classList.remove("hit", "hit-now"));
  if (view.findInput) view.findInput.value = "";
  if (view.findNav) view.findNav.hidden = true;
}

function applyFind(scroll) {
  if (!view.find) return;
  document.querySelectorAll(".w.hit").forEach(e => e.classList.remove("hit", "hit-now"));
  if (view.findInput.value !== find.q) view.findInput.value = find.q;
  view.findNav.hidden = !find.q.trim();
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

async function showRecording(name, data = null) {
  stopAll();
  find = null;  // a search belongs to the call it was made in
  recName = name;
  renderCalls();
  renderPending();
  data = data || await getJSON(`/api/recordings/${enc(name)}`);
  players = {};
  gains = {};
  lastChannel = null;
  $audio.replaceChildren();
  for (const [channel, lufs] of Object.entries(data.loudness || {})) {
    gains[channel] = playbackGain(lufs);
  }
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

function showWaiting(name) {
  // The call being transcribed, before Whisper is done: nothing to read yet, only how far it
  // is (renderPending updates the line). The text replaces this page as soon as it exists.
  stopAll();
  find = null;
  players = {};
  gains = {};
  $audio.replaceChildren();
  rec = null;
  recName = name;
  view = { waiting: el("p", {}) };
  renderCalls();
  $main.replaceChildren(el("div", { class: "placeholder" },
    el("h2", {}, recState.source ? recState.source.replace(/\.[^.]+$/, "") : name),
    view.waiting,
    el("p", {}, "Il testo compare qui appena Whisper ha finito; poi si aggiungono le parole " +
                "dubbie e le voci.")));
  renderPending();
}

function showEmpty() {
  stopAll();
  players = {};
  $audio.replaceChildren();
  rec = recName = null;
  view = {};
  renderCalls();
  renderPending();
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
  if (action === "start" && !modelsReady()) return;
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
  // In the native app the floating window is the app's own panel (phase 8, step 2).
  const pop = floating || window.parolaNative ? null
    : iconButton("popout", "Finestra mobile", () => openFloating(false));
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
// What the transcription is doing, from the progress message ("parole dubbie Altri" too).
const STEPS = [["trascrizione", "Trascrizione"], ["parole dubbie", "Parole dubbie"],
               ["chi parla", "Chi parla"]];

function renderPending() {
  // The call being uploaded or transcribed, at the top of the list, until it is ready. Once
  // Whisper is done it opens the provisional text (decision 0031).
  let title, text, pct;
  const preview = !uploading && recState.state === "transcribing" && recState.preview;
  if (view.stage && rec && rec.provisional && recName === recState.name &&
      recState.state === "error") {
    view.stage.textContent = " La trascrizione si è fermata: questo testo non è stato salvato.";
  }
  if (view.waiting && recName === recState.name && recState.state === "error") {
    view.waiting.textContent = `La trascrizione si è fermata: ${recState.message}`;
  }
  if (uploading) {
    title = uploading.name;
    pct = uploading.pct;
    text = `Caricamento… ${pct}%`;
  } else if (recState.state === "transcribing") {
    title = recState.source ? recState.source.replace(/\.[^.]+$/, "") : "Registrazione";
    const [done, total] = recState.step || [0, 0];
    pct = total ? Math.min(99, Math.round((done / total) * 100)) : 0;
    const step = STEPS.find(([m]) => (recState.message || "").startsWith(m));
    text = recState.message === "conversione" ? "Conversione…"
                                              : `${step ? step[1] : "Trascrizione"}… ${pct}%`;
  } else {
    $pending.hidden = true;
    return;
  }
  if (!pendingView.title) {
    pendingView.title = el("span", { class: "title" });
    pendingView.text = el("span", { class: "sub" });
    pendingView.bar = el("i");
    pendingView.row = el("a", { class: "pending-call" }, el("span", { class: "pending-dot blink" }),
      el("div", { class: "pending-body" }, pendingView.title, pendingView.text,
        el("div", { class: "bar" }, pendingView.bar)));
    $pending.replaceChildren(el("div", { class: "group" }, "In corso"), pendingView.row);
  }
  $pending.hidden = false;
  pendingView.title.textContent = title;
  pendingView.text.textContent = text;
  pendingView.bar.style.width = `${pct}%`;
  // Clickable from the start: before Whisper is done it opens a page that says how far it is.
  const name = !uploading && recState.state === "transcribing" && recState.name;
  if (name) pendingView.row.href = `#/rec/${enc(name)}`;
  else pendingView.row.removeAttribute("href");
  pendingView.row.classList.toggle("active", !!name && recName === name);
  if (view.waiting && recName === recState.name) view.waiting.textContent = text;
  if (view.stage && rec && rec.provisional && recName === recState.name) {
    view.stage.textContent = ` ${text}`;
  }
}

async function refreshShown(final) {
  // The call on screen is the one being transcribed: its text moves to the next stage in place.
  const name = recName;
  let data;
  try { data = await getJSON(`/api/recordings/${enc(name)}`); } catch (e) { return; }
  if (recName !== name) return;  // another call was opened meanwhile
  if (!final) {
    // Same audio: only the text changes. While Whisper works it grows (decision 0033): the new
    // words fade in, and the view follows the end if that is where the person is reading.
    const box = view.scroll;
    const atEnd = box && box.scrollHeight - box.scrollTop - box.clientHeight < 80;
    const scrollY = box ? box.scrollTop : 0;
    const before = words.length;
    await render(data, {});
    if (view.scroll) view.scroll.scrollTop = scrollY;
    if (before && words.length > before) {
      words.slice(before).forEach((w, i) => {
        w.el.classList.add("fresh");
        w.el.style.animationDelay = `${Math.min(i * 12, 900)}ms`;
      });
      if (atEnd && Date.now() - scrolledByHand > FOLLOW_PAUSE) {
        view.scroll.scrollTo({ top: view.scroll.scrollHeight, behavior: "smooth" });
      }
    }
    return;
  }
  // The final transcript: editable, and the audio is now FLAC (decision 0024), so new players,
  // at the same point.
  const p = lastChannel && players[lastChannel];
  const at = p ? p.currentTime : 0, wasPlaying = !!(p && !p.paused);
  const scrollY = view.scroll ? view.scroll.scrollTop : 0;
  await showRecording(name, data);
  if (view.scroll) view.scroll.scrollTop = scrollY;
  const q = lastChannel && players[lastChannel];
  if (q && at) {
    q.addEventListener("loadedmetadata", () => {
      q.currentTime = at;
      if (wasPlaying) q.play().catch(() => {});
    }, { once: true });
  }
}

function setRecState(st) {
  const prev = recState;
  recState = st;
  recAt = Date.now();
  // A new recording captures the system audio: a call playing in the app would be recorded
  // over the real one, so playback pauses by itself, however the recording was started.
  if (startedRecording(prev.state, st.state) && playing()) {
    stopAll();
    toast("Riproduzione in pausa: registrazione avviata");
  }
  renderRecorder();
  if (st.state === "transcribing" && st.preview && st.name &&
      (st.preview !== prev.preview || st.revision !== prev.revision)) {
    // Whisper is done (decision 0031): the text shows up, then the doubtful words.
    if (recName === st.name) {
      if (rec) refreshShown(false);
      else showRecording(st.name).catch(() => {});  // from the waiting page to the text
    }
    else if (!prev.preview && (!rec || st.name === imported)) {
      imported = null;  // opened now: not again when it is done
      location.hash = `#/rec/${enc(st.name)}`;
    }
  }
  if (prev.state === "transcribing" && st.state === "done") {
    const here = recName === st.name;
    const open = !here && (!rec || st.name === imported);  // a file you just imported opens by itself
    imported = null;
    refreshCalls().then(() => {
      if (here) refreshShown(true);
      else if (open && st.name) location.hash = `#/rec/${enc(st.name)}`;
    });
  }
}

// ---------------------------------------------------------------- importing a file

const $file = el("input", { type: "file", accept: "audio/*,video/*,.qta", hidden: true,
                            onchange: e => { if (e.target.files[0]) importFile(e.target.files[0]); } });
document.body.append($file);
let uploading = null;   // {name, pct} while a file is being sent
let imported = null;    // name of the call being imported from this window

// A file's language is asked before it is sent: Whisper transcribes the whole file in one
// language, and a wrong guess turns English into an Italian translation (decision 0030).
const IMPORT_LANGS = [["it", "Italiano"], ["en", "English"], ["", "Rileva"]];
let importLang = null;   // the last choice, offered first next time
try { importLang = localStorage.getItem("importLang"); } catch (e) { /* none yet */ }

function askLanguage(file) {
  return new Promise(resolve => {
    const box = el("div", { class: "modal", role: "dialog", "aria-modal": "true",
                            "aria-labelledby": "lang-title" });
    const done = lang => {
      box.remove();
      document.removeEventListener("keydown", onKey, true);
      resolve(lang);
    };
    const onKey = e => {
      if (e.key === "Escape") { e.preventDefault(); e.stopPropagation(); done(null); }
    };
    const buttons = IMPORT_LANGS.map(([value, label]) =>
      el("button", { class: value === importLang ? "primary" : null, onclick: () => done(value) },
         label));
    box.append(el("div", { class: "modal-card" },
      el("h2", { id: "lang-title" }, "In che lingua è?"),
      el("p", { class: "modal-file" }, file.name),
      el("p", {}, "La trascrizione segue una lingua per tutto il file. Se non sei sicuro, " +
                  "Rileva ascolta alcuni punti del file e sceglie tra italiano e inglese."),
      el("div", { class: "modal-actions" },
        el("button", { class: "cancel", onclick: () => done(null) }, "Annulla"), ...buttons)));
    box.addEventListener("click", e => { if (e.target === box) done(null); });
    document.addEventListener("keydown", onKey, true);
    document.body.append(box);
    (buttons.find(b => b.classList.contains("primary")) || buttons[0]).focus();
  });
}

async function importFile(file) {
  if (!modelsReady()) return;
  if (["recording", "transcribing"].includes(recState.state) || uploading) {
    toast("Aspetta che finisca la registrazione o la trascrizione in corso.");
    return;
  }
  const lang = await askLanguage(file);
  $file.value = "";
  if (lang === null) return;
  importLang = lang;
  try { localStorage.setItem("importLang", lang); } catch (e) { /* not remembered */ }
  sendFile(file, lang);
}

function sendFile(file, lang) {
  // The raw file goes in the request body (no form encoding); progress from XHR.
  uploading = { name: file.name.replace(/\.[^.]+$/, ""), pct: 0 };
  renderRecorder();
  const params = new URLSearchParams({ filename: file.name, modified: String(file.lastModified) });
  if (lang) params.set("lang", lang);
  const xhr = new XMLHttpRequest();
  xhr.open("POST", `/api/import?${params}`);
  xhr.upload.onprogress = e => {
    if (!e.lengthComputable || !uploading) return;
    uploading.pct = Math.round((e.loaded / e.total) * 100);
    renderPending();
  };
  xhr.onload = () => {
    uploading = null;
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
  if (window.parolaNative) return;
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

// ---------------------------------------------------------------- first run: the models

// Asked once, before anything is downloaded (no network until the person says yes).
const MODELS = [
  ["Whisper large-v3-turbo", "La trascrizione · OpenAI, licenza MIT", "1,6 GB"],
  ["Parakeet v3", "La seconda opinione sulle parole dubbie · NVIDIA, CC BY 4.0", "2,5 GB"],
  ["Voci", "Chi parla quando · pyannote (MIT) e WeSpeaker (CC BY 4.0)", "33 MB"],
];
let models = { state: "ready" };
let setupLater = false;   // "Più tardi": the calls already here can still be read
let setupTimer = null;
const $setup = el("div", { class: "modal", hidden: true, role: "dialog", "aria-modal": "true",
                           "aria-labelledby": "setup-title" });
document.body.append($setup);

function modelsReady() {
  if (models.state === "ready") return true;
  setupLater = false;
  renderSetup();
  return false;
}

function renderSetup() {
  const st = models.state;
  $setup.hidden = st === "ready" || (setupLater && st !== "downloading");
  if ($setup.hidden) return;
  const card = el("div", { class: "modal-card" },
    el("h2", { id: "setup-title" }, "Prima di iniziare"),
    el("p", {}, "P.A.R.O.L.A. trascrive tutto su questo Mac. Per farlo le servono i modelli di " +
                `riconoscimento vocale: circa ${gigabytes(models.total)}, da scaricare una volta ` +
                "sola da Hugging Face e GitHub. Dopo, funziona senza rete."),
    el("ul", { class: "setup-models" }, ...MODELS.map(([name, what, size]) =>
      el("li", {}, el("span", {}, name, el("small", {}, what)), el("span", { class: "size" }, size)))));
  if (st === "downloading") {
    const pct = models.total ? Math.min(99, Math.floor((models.done / models.total) * 100)) : 0;
    const bar = el("i");
    bar.style.width = `${pct}%`;
    card.append(el("div", { class: "setup-bar" }, bar),
      el("div", { class: "setup-progress" },
         `${gigabytes(models.done)} di ${gigabytes(models.total)} · ${pct}%`),
      el("p", {}, "Puoi lasciare la finestra aperta e fare altro: il download continua."));
  } else {
    if (st === "error") {
      card.append(el("p", { class: "err" }, "Download non riuscito: controlla la connessione e " +
                                            "riprova. Quello già scaricato resta."),
                  el("p", { class: "setup-detail" }, models.message));
    }
    card.append(el("div", { class: "modal-actions" },
      el("button", { onclick: () => { setupLater = true; renderSetup(); } }, "Più tardi"),
      el("button", { class: "primary", onclick: startDownload },
         st === "error" ? "Riprova" : "Scarica i modelli")));
  }
  $setup.replaceChildren(card);
}

async function startDownload() {
  try { setModels(await postJSON("/api/models/download")); } catch (e) { toast(e.message); }
}

function setModels(st) {
  const was = models.state;
  models = st;
  renderSetup();
  if (was === "downloading" && st.state === "ready") toast("Modelli pronti: puoi registrare.");
  clearTimeout(setupTimer);
  if (st.state === "downloading") setupTimer = setTimeout(pollModels, 1000);
}

async function pollModels() {
  try { setModels(await getJSON("/api/models")); } catch (e) { setupTimer = setTimeout(pollModels, 3000); }
}

// ---------------------------------------------------------------- routing and keys

async function route() {
  const m = location.hash.match(/^#\/rec\/([^?]+)(?:\?(.*))?$/);
  try {
    if (m) {
      const name = decodeURIComponent(m[1]);
      const params = new URLSearchParams(m[2] || "");
      // Another hit in the call already open: no reload, the audio keeps its place.
      if (name === recState.name && recState.state === "transcribing" && !recState.preview) {
        showWaiting(name);
      } else if (name !== recName || !rec) await showRecording(name);
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
pollModels();
