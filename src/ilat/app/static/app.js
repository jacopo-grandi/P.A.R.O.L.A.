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

function jump(direction) {
  // In time order: segments of the two channels interleave and overlap.
  const doubts = words.filter(w => w.doubtful).sort((a, b) => a.start - b.start);
  if (!doubts.length) return;
  const at = current ? words.findIndex(w => w.el === current) : -1;
  const pos = at < 0 ? -1 : words[at].start;
  const next = direction > 0 ? doubts.find(w => w.start > pos + 0.01)
                             : [...doubts].reverse().find(w => w.start < pos - 0.01);
  const target = next || (direction > 0 ? doubts[0] : doubts[doubts.length - 1]);
  target.el.scrollIntoView({ block: "center", behavior: "smooth" });
  play(target);
}

async function showRecording(name) {
  stopAll();
  const rec = await getJSON(`/api/recordings/${encodeURIComponent(name)}`);
  players = {};
  audioBox.replaceChildren();
  for (const [channel, url] of Object.entries(rec.audio)) {
    const a = el("audio", { preload: "metadata", src: url });
    a.addEventListener("timeupdate", () => follow(channel));
    players[channel] = a;
    audioBox.append(a);
  }
  words = [];
  current = null;
  const body = el("div", { class: "transcript" });
  for (const seg of rec.segments) {
    const channel = seg.channel || "mic";
    const text = el("div", { class: "text" });
    const list = seg.words.length ? seg.words : [{ text: seg.text, start: seg.start, end: seg.end }];
    list.forEach((w, k) => {
      const start = w.start ?? seg.start, end = w.end ?? seg.end;
      const span = el("span", { class: "w" + (w.doubtful ? " doubt" : "") }, w.text);
      if (w.doubtful) span.title = "parola dubbia: la seconda trascrizione dice altro";
      const word = { el: span, channel, start, end, doubtful: !!w.doubtful };
      span.addEventListener("click", () => play(word));
      words.push(word);
      text.append(span, k < list.length - 1 ? " " : "");
    });
    const first = words[words.length - list.length];
    body.append(el("div", { class: `seg ${channel}`, "data-doubt": seg.words.some(w => w.doubtful) },
      el("span", { class: "time", onclick: () => play(first) }, clock(seg.start)),
      el("span", { class: "who" }, LABELS[channel] || channel),
      text));
  }
  const s = rec.summary;
  const onlyDoubts = el("input", { type: "checkbox" });
  onlyDoubts.addEventListener("change", () => {
    for (const row of body.children) {
      row.classList.toggle("hidden", onlyDoubts.checked && row.dataset.doubt !== "true");
    }
  });
  const bar = el("div", { class: "bar" },
    el("h1", {}, s.name),
    el("button", { onclick: () => {
      const p = current ? players[words.find(w => w.el === current).channel] : Object.values(players)[0];
      if (p) (p.paused ? p.play() : p.pause());
    } }, "▶︎ / ❚❚"),
    el("button", { onclick: () => jump(-1) }, "← dubbia"),
    el("button", { onclick: () => jump(1) }, "dubbia →"),
    el("label", { class: "toggle" }, onlyDoubts, " solo righe con dubbi"),
    el("a", { class: "btn", href: `/export/${encodeURIComponent(name)}.txt` }, "txt"),
    el("a", { class: "btn", href: `/export/${encodeURIComponent(name)}.md` }, "md"),
    el("a", { class: "btn", href: `/export/${encodeURIComponent(name)}.json` }, "json"),
    el("a", { class: "btn", href: "#/" }, "elenco"));
  const help = el("p", { class: "help" },
    `${clock(s.duration)} · ${s.words} parole · ${s.doubtful} dubbie (evidenziate: la seconda ` +
    "trascrizione non le conferma). Clic su una parola per ascoltare da lì. Tasti: spazio " +
    "play/pausa, N dubbia successiva, P precedente.");
  main.replaceChildren(bar, help, body);
  window.scrollTo(0, 0);
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

document.addEventListener("keydown", e => {
  if (e.target.tagName === "INPUT" && e.target.type !== "checkbox") return;
  if (!Object.keys(players).length) return;
  if (e.key === " ") {
    e.preventDefault();
    const channel = current ? words.find(w => w.el === current).channel : Object.keys(players)[0];
    const p = players[channel];
    p.paused ? p.play() : p.pause();
  } else if (e.key === "n" || e.key === "N") jump(1);
  else if (e.key === "p" || e.key === "P") jump(-1);
});

window.addEventListener("hashchange", route);
route();
