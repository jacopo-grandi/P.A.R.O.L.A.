// Pure helpers for the UI: no DOM, no fetch, no shared state. index.html loads this file
// right before app.js (same global scope, no build step); tests/test_helpers.js runs the
// same file in Node, so every function here must stay runnable outside the browser.
"use strict";

// ---------------------------------------------------------------- formatting

function clock(seconds) {
  const s = Math.max(0, Math.floor(seconds || 0));
  const h = Math.floor(s / 3600), m = Math.floor((s % 3600) / 60), r = s % 60;
  const mm = String(m).padStart(2, "0"), ss = String(r).padStart(2, "0");
  return h ? `${h}:${mm}:${ss}` : `${mm}:${ss}`;
}

function minutes(seconds) {
  const m = Math.round((seconds || 0) / 60);
  return m < 1 ? "< 1 min" : m < 60 ? `${m} min` : `${Math.floor(m / 60)} h ${m % 60} min`;
}

function speedLabel(v) {
  return `${String(v).replace(".", ",")}×`;
}

function gigabytes(bytes) {
  return (bytes / 1e9).toLocaleString("it-IT", { minimumFractionDigits: 1,
                                                 maximumFractionDigits: 1 }) + " GB";
}

// ---------------------------------------------------------------- dates in the sidebar

function dayOf(d) { return new Date(d.getFullYear(), d.getMonth(), d.getDate()); }

// `now` exists so the tests can pin the day; the app never passes it.
function groupOf(date, now = new Date()) {
  const days = Math.round((dayOf(now) - dayOf(date)) / 86400000);
  if (days <= 0) return "Oggi";
  if (days === 1) return "Ieri";
  if (days < 7) return "Ultimi 7 giorni";
  if (days < 30) return "Ultimi 30 giorni";
  return date.toLocaleDateString("it-IT", { month: "long", year: "numeric" });
}

function shortWhen(date, now = new Date()) {
  const days = Math.round((dayOf(now) - dayOf(date)) / 86400000);
  return days < 2 ? date.toLocaleTimeString("it-IT", { hour: "2-digit", minute: "2-digit" })
                  : date.toLocaleDateString("it-IT", { day: "numeric", month: "short" });
}

// ---------------------------------------------------------------- find in the call

function fold(text) {
  // Same as parola.search.fold: lowercase, no accents, no punctuation at the edges.
  return text.normalize("NFKD").replace(/[̀-ͯ]/g, "").toLowerCase()
    .replace(/^[^\p{L}\p{N}_]+|[^\p{L}\p{N}_]+$/gu, "");
}

function forms(text) {
  // "dell'impatto" is found by itself and by "impatto".
  const f = fold(text);
  const m = f.match(/^[\p{L}\p{N}_]+['’]([\p{L}\p{N}_].*)$/u);
  return m ? [f, m[1]] : [f];
}

function findMatches(q, segTexts) {
  // Where the query appears: `segTexts` holds each segment's words as plain text, and a
  // match is a run of consecutive words in one segment, as {seg, start, end} indices.
  const tokens = q.split(/\s+/).map(fold).filter(Boolean);
  if (!tokens.length) return [];
  const matches = [];
  segTexts.forEach((texts, seg) => {
    const alts = texts.map(forms);
    for (let k = 0; k + tokens.length <= texts.length; k++) {
      if (tokens.every((t, i) => alts[k + i].includes(t))) {
        matches.push({ seg, start: k, end: k + tokens.length });
      }
    }
  });
  return matches;
}

// ---------------------------------------------------------------- doubtful runs

function doubtfulRuns(list, seg, channel, segStart) {
  // Consecutive doubtful words are reviewed as one run; `t` is where it starts in the audio.
  const found = [];
  for (let k = 0; k < list.length; k++) {
    if (list[k].doubtful && !(k > 0 && list[k - 1].doubtful)) {
      let e = k;
      while (e < list.length && list[e].doubtful) e++;
      found.push({ seg, start: k, end: e, t: list[k].start ?? segStart, channel });
    }
  }
  return found;
}

// Whisper writes the same line over and over on long noise ("Thank you." every window of a
// noisy break): the transcript keeps every line, the view shows the first with "× N".
const REPEAT_MIN = 3;

function repeatUnit(texts) {
  // A line's smallest repeating unit, so "Thank you. Thank you." folds with "Thank you.":
  // folded words in, the unit out as one string.
  const t = texts.filter(Boolean);
  for (let len = 1; len <= t.length; len++) {
    if (t.length % len) continue;
    if (t.every((w, i) => w === t[i % len])) return t.slice(0, len).join(" ");
  }
  return t.join(" ");
}

function repeatedRuns(segs) {
  // `segs` holds per segment: its shown text, whether every word is doubtful, and the
  // channel/speaker key that must not change inside a run. Ranges as {start, end} indices.
  const out = [];
  let s = 0;
  for (let i = 1; i <= segs.length; i++) {
    const same = i < segs.length && segs[i].doubtful && segs[s].doubtful
      && segs[i].text === segs[s].text && segs[i].key === segs[s].key;
    if (!same) {
      if (segs[s].doubtful && i - s >= REPEAT_MIN) out.push({ start: s, end: i });
      s = i;
    }
  }
  return out;
}

// The other hallucination shape: one segment looping a phrase ("and check out this page and
// check out this page and..."). The repeats after the first fold behind the same "× N" badge.
const LOOP_MIN_REPEATS = 3;
const LOOP_MIN_HIDDEN = 10; // folded words; "no no no" is speech, thirty "check out this page" not

function wordLoop(ws) {
  // `ws` holds per word its folded text and whether it is doubtful. The loop that hides the
  // most words, as {start, len, repeats}, or null: only doubtful words may loop away.
  const t = ws.map(w => w.text);
  let best = null;
  for (let len = 1; len <= 8; len++) {
    for (let i = 0; i + 2 * len <= t.length; i++) {
      let end = i;
      while (end + len <= t.length
             && t.slice(end, end + len).every((w, k) => w === t[i + k] && ws[end + k].doubtful)) {
        end += len;
      }
      const repeats = (end - i) / len;
      const hidden = (repeats - 1) * len;
      if (repeats >= LOOP_MIN_REPEATS && hidden >= LOOP_MIN_HIDDEN
          && (!best || hidden > (best.repeats - 1) * best.len)) {
        best = { start: i, len, repeats };
      }
    }
  }
  return best;
}

function pickRun(runs, direction, pos) {
  // The next (or previous) run after `pos` seconds, wrapping around at the ends. The small
  // tolerance keeps the run just opened from being offered again.
  if (!runs.length) return null;
  const ordered = [...runs].sort((a, b) => a.t - b.t);
  const found = direction > 0 ? ordered.find(r => r.t > pos + 0.01)
                              : [...ordered].reverse().find(r => r.t < pos - 0.01);
  return found || (direction > 0 ? ordered[0] : ordered[ordered.length - 1]);
}

// ---------------------------------------------------------------- playback gain

// A quiet channel is raised towards TARGET_LUFS at playback (in a recorded call the mic
// track can sit 30 dB under the others'); a loud one is never lowered. The server measures
// (parola.audio.loudness), this decides: the whole policy in one testable place.
const TARGET_LUFS = -18;
const MAX_BOOST_DB = 30;

function playbackGain(lufs) {
  // Linear gain for a channel measured at `lufs` integrated; 1 when unknown or silent
  // (-70 is ebur128's floor: an empty track, where a boost would only raise the hiss).
  if (typeof lufs !== "number" || !isFinite(lufs) || lufs <= -70) return 1;
  const db = Math.min(Math.max(TARGET_LUFS - lufs, 0), MAX_BOOST_DB);
  return Math.pow(10, db / 20);
}

// ---------------------------------------------------------------- recorder state

function startedRecording(prevState, newState) {
  // The moment a recording begins, from any side (button, menu bar, CLI): the recorder's
  // state is polled, so only the transition counts — pausing inside a recording does not.
  return newState === "recording" && prevState !== "recording";
}

// In the browser these are plain globals shared with app.js; in Node the tests import them.
if (typeof module !== "undefined" && module.exports) {
  module.exports = { clock, minutes, speedLabel, gigabytes, dayOf, groupOf, shortWhen,
                     fold, forms, findMatches, doubtfulRuns, repeatUnit, repeatedRuns,
                     wordLoop, pickRun, playbackGain, startedRecording };
}
