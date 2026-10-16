// ilat local UI: list of recordings, transcript with doubtful words, click a word to listen.
"use strict";

const LABELS = { mic: "Io", system: "Altri" };
const LEAD = 0.25; // start playing a little before the word
const main = document.getElementById("main");
const audioBox = document.getElementById("audio");
let players = {};   // channel -> <audio>
let words = [];     // flat list of {el, channel, start, end, doubtful}
let current = null; // word element being played
let target = null;  // word chosen by click or N/P, until playback reaches it

function el(tag, attrs = {}, ...children) {
  const e = document.createElement(tag);
  for (const [k, v] of Object.entries(attrs)) {
    if (k === "class") e.className = v;
    else if (k.startsWith("on")) e.addEventListener(k.slice(2), v);
    else e.setAttribute(k, v);
  }
  for (const c of children) e.append(c);
  return e;
}

function clock(seconds) {
  const s = Math.max(0, Math.floor(seconds));
  const h = Math.floor(s / 3600), m = Math.floor((s % 3600) / 60), r = s % 60;
  const mm = String(m).padStart(2, "0"), ss = String(r).padStart(2, "0");
  return h ? `${h}:${mm}:${ss}` : `${mm}:${ss}`;
}

async function getJSON(url) {
  const r = await fetch(url);
  if (!r.ok) throw new Error(`${url}: ${r.status}`);
  return r.json();
}

function stopAll() {
  for (const p of Object.values(players)) p.pause();
}

// ---------------------------------------------------------------- list

async function showList() {
  stopAll();
  audioBox.replaceChildren();
  players = {};
  const recs = await getJSON("/api/recordings");
  if (!recs.length) {
    main.replaceChildren(el("p", { class: "empty" },
      "Nessuna registrazione. Registra una call con ", el("code", {}, "uv run ilat record"), "."));
    return;
  }
  const list = el("div", { class: "list" });
  for (const r of recs) {
    const when = new Date(r.started_at).toLocaleString("it-IT");
    const who = r.channels.map(c => LABELS[c] || c).join(" + ");
    const meta = `${when} · ${clock(r.duration)} · ${who} · ${r.words} parole`;
    list.append(el("a", { class: "rec", href: `#/rec/${encodeURIComponent(r.name)}` },
      el("div", { class: "name" }, r.name, " ",
        r.doubtful ? el("span", { class: "badge" }, `${r.doubtful} dubbie`) : ""),
      el("div", { class: "meta" }, meta)));
  }
  main.replaceChildren(list);
}

// ---------------------------------------------------------------- recording

let rec = null;      // recording being shown
let recName = null;
let runs = [];       // doubtful runs still to review: {seg, start, end, t, channel}
let editing = null;  // {seg, start, end}

function play(word) {
  const p = players[word.channel];
  if (!p) return;
  for (const [c, q] of Object.entries(players)) if (c !== word.channel) q.pause();
  p.currentTime = Math.max(0, word.start - LEAD);
  p.play().catch(() => {});
  target = word;
  mark(word.el);
}

function mark(e) {
  if (current) current.classList.remove("now");
  current = e;
  if (e) e.classList.add("now");
}

function follow(channel) {
  // Highlight the word being played on this channel.
  const t = players[channel].currentTime;
  // Playback starts LEAD seconds early: keep the chosen word highlighted until it is reached.
  if (target && target.channel === channel && t < target.start) return;
  target = null;
  const w = words.find(w => w.channel === channel && w.start <= t && t < w.end);
  if (w && w.el !== current) mark(w.el);
}

async function post(action, body) {
  const r = await fetch(`/api/recordings/${encodeURIComponent(recName)}/${action}`, {
    method: "POST", headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body || {}),
  });
  if (!r.ok) throw new Error((await r.json()).detail || r.status);
  return r.json();
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
  const input = el("input", { class: "edit", value: text, size: Math.max(8, text.length + 2),
                              title: "Invio: salva (senza modifiche: conferma) · Esc: annulla" });
  first.el.before(input);
  for (let k = start; k < end; k++) wordAt(seg, k).el.classList.add("editing");
  input.addEventListener("keydown", async e => {
    if (e.key === "Escape") { e.preventDefault(); closeEditor(); }
    else if (e.key === "Enter") {
      e.preventDefault();
      const after = await post("correct", { segment: seg, start, end, text: input.value });
      await render(after, { seg, start, auto: true });
    } else if (e.key === " " && e.ctrlKey) { e.preventDefault(); play(first); }
  });
  input.focus();
  input.select();
  first.el.scrollIntoView({ block: "center", behavior: "smooth" });
  if (autoplay) play(first);
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

async function render(data, after) {
  rec = data;
  words = [];
  runs = [];
  current = null;
  editing = null;
  const body = el("div", { class: "transcript" });
  rec.segments.forEach((seg, si) => {
    const channel = seg.channel || "mic";
    const text = el("div", { class: "text" });
    const list = seg.words.length ? seg.words : [{ text: seg.text, start: seg.start, end: seg.end }];
    list.forEach((w, k) => {
      const start = w.start ?? seg.start, end = w.end ?? seg.end;
      const cls = "w" + (w.doubtful ? " doubt" : "") + (w.checked ? " checked" : "");
      const span = el("span", { class: cls }, w.text);
      if (w.doubtful) span.title = "parola dubbia: la seconda trascrizione dice altro (N per rivederla)";
      else if (w.checked) span.title = "verificata da te";
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
    body.append(el("div", { class: `seg ${channel}`, "data-doubt": seg.words.some(w => w.doubtful) },
      el("span", { class: "time", onclick: () => play(first) }, clock(seg.start)),
      el("span", { class: "who" }, LABELS[channel] || channel),
      text));
  });
  const s = rec.summary;
  const onlyDoubts = el("input", { type: "checkbox" });
  onlyDoubts.addEventListener("change", () => {
    for (const row of body.children) {
      row.classList.toggle("hidden", onlyDoubts.checked && row.dataset.doubt !== "true");
    }
  });
  const exp = f => el("a", { class: "btn", href: `/export/${encodeURIComponent(recName)}.${f}` }, f);
  const bar = el("div", { class: "bar" },
    el("h1", {}, s.name),
    el("span", { class: "todo" }, runs.length ? `${runs.length} da rivedere` : "tutto rivisto ✓"),
    el("button", { onclick: () => jump(-1) }, "← P"),
    el("button", { onclick: () => jump(1) }, "N →"),
    el("button", { onclick: async () => {
      try { await render(await post("undo"), {}); } catch (e) { alert(e.message); }
    } }, "annulla ⌘Z"),
    el("label", { class: "toggle" }, onlyDoubts, " solo righe con dubbi"),
    exp("txt"), exp("md"), exp("docx"), exp("json"),
    el("button", { onclick: () => window.print() }, "PDF"),
    el("a", { class: "btn", href: "#/" }, "elenco"));
  const help = el("p", { class: "help" },
    `${clock(s.duration)} · ${s.words} parole · ${s.doubtful} dubbie · ${s.checked} verificate. ` +
    "Clic su una parola: ascolta da lì. N: prossima dubbia (si ascolta e si apre in modifica), " +
    "Invio salva (senza modifiche la conferma) e passa alla successiva, Esc annulla, " +
    "doppio clic: modifica qualsiasi parola, ⌘Z: annulla l'ultima modifica, spazio: play/pausa.");
  const y = window.scrollY;
  main.replaceChildren(bar, help, body);
  if (after && after.seg !== undefined) {
    window.scrollTo(0, y);
    if (after.auto) {
      const w = wordAt(after.seg, Math.min(after.start, rec.segments[after.seg].words.length - 1));
      const from = w ? w.start - 0.02 : undefined;
      const r = nextRun(1, from);
      if (r) openEditor(r.seg, r.start, r.end, true);
    }
  } else if (!after) window.scrollTo(0, 0);
}

async function showRecording(name) {
  stopAll();
  recName = name;
  const data = await getJSON(`/api/recordings/${encodeURIComponent(name)}`);
  players = {};
  audioBox.replaceChildren();
  for (const [channel, url] of Object.entries(data.audio)) {
    const a = el("audio", { preload: "metadata", src: url });
    a.addEventListener("timeupdate", () => follow(channel));
    players[channel] = a;
    audioBox.append(a);
  }
  await render(data);
}

// ---------------------------------------------------------------- routing and keys

async function route() {
  const m = location.hash.match(/^#\/rec\/(.+)$/);
  try {
    if (m) await showRecording(decodeURIComponent(m[1]));
    else await showList();
  } catch (e) {
    main.replaceChildren(el("p", { class: "empty" }, `Errore: ${e.message}`));
  }
}

document.addEventListener("keydown", async e => {
  if (e.target.tagName === "INPUT" && e.target.type !== "checkbox") return;
  if (!Object.keys(players).length) return;
  if (e.key === " ") {
    e.preventDefault();
    const w = current && words.find(w => w.el === current);
    const p = players[w ? w.channel : Object.keys(players)[0]];
    p.paused ? p.play() : p.pause();
  } else if (e.key === "n" || e.key === "N") { e.preventDefault(); jump(1); }
  else if (e.key === "p" || e.key === "P") { e.preventDefault(); jump(-1); }
  else if ((e.metaKey || e.ctrlKey) && e.key === "z") {
    e.preventDefault();
    try { await render(await post("undo"), {}); } catch (err) { /* nothing to undo */ }
  }
});

window.addEventListener("hashchange", route);
route();
