// Hand-built cases for the pure UI helpers: every value here is written by hand.
// Run with `node --test tests/test_helpers.js`: Node's built-in runner, no packages.
"use strict";

const test = require("node:test");
const assert = require("node:assert/strict");

const { clock, minutes, speedLabel, gigabytes, dayOf, groupOf, shortWhen,
        fold, forms, findMatches, doubtfulRuns, pickRun, playbackGain } =
  require("../src/parola/app/static/helpers.js");

// ---------------------------------------------------------------- formatting

test("clock: mm:ss below one hour, h:mm:ss from there", () => {
  for (const [seconds, expected] of [
    [0, "00:00"],
    [7, "00:07"],
    [59.9, "00:59"],      // floored, never rounded up
    [61, "01:01"],
    [600, "10:00"],
    [3599, "59:59"],
    [3600, "1:00:00"],
    [3661, "1:01:01"],
    [36123, "10:02:03"],
    [-5, "00:00"],        // clamped: a seek can briefly go negative
    [undefined, "00:00"],
  ]) assert.equal(clock(seconds), expected, `clock(${seconds})`);
});

test("minutes: the sidebar duration, rounded to the minute", () => {
  for (const [seconds, expected] of [
    [0, "< 1 min"],
    [29, "< 1 min"],      // 0.48 min rounds to 0
    [30, "1 min"],        // 0.5 min rounds to 1
    [120, "2 min"],
    [3540, "59 min"],
    [3600, "1 h 0 min"],
    [5400, "1 h 30 min"],
    [7260, "2 h 1 min"],
    [undefined, "< 1 min"],
  ]) assert.equal(minutes(seconds), expected, `minutes(${seconds})`);
});

test("speedLabel: Italian decimal comma", () => {
  for (const [speed, expected] of [
    [1, "1×"], [0.75, "0,75×"], [1.25, "1,25×"], [2, "2×"],
  ]) assert.equal(speedLabel(speed), expected, `speedLabel(${speed})`);
});

test("gigabytes: one decimal, Italian comma", () => {
  for (const [bytes, expected] of [
    [1.6e9, "1,6 GB"],
    [4.13e9, "4,1 GB"],
    [33e6, "0,0 GB"],     // only totals are shown this way, never single small models
    [0, "0,0 GB"],
  ]) assert.equal(gigabytes(bytes), expected, `gigabytes(${bytes})`);
});

// ---------------------------------------------------------------- dates in the sidebar

// All date cases are pinned to this "now": Sunday 18 October 2026, mid-afternoon.
const NOW = new Date(2026, 9, 18, 15, 30);

test("dayOf: the calendar day, time of day dropped", () => {
  assert.equal(dayOf(new Date(2026, 9, 18, 23, 59)).getTime(),
               new Date(2026, 9, 18).getTime());
  assert.equal(dayOf(new Date(2026, 9, 18, 0, 0)).getTime(),
               new Date(2026, 9, 18).getTime());
});

test("groupOf: the sidebar groups, by calendar day", () => {
  for (const [date, expected] of [
    [new Date(2026, 9, 18, 0, 1), "Oggi"],
    [new Date(2026, 9, 17, 23, 59), "Ieri"],            // late yesterday is still "Ieri"
    [new Date(2026, 9, 12), "Ultimi 7 giorni"],         // 6 days ago
    [new Date(2026, 9, 11), "Ultimi 30 giorni"],        // 7 days ago: out of the week
    [new Date(2026, 8, 19), "Ultimi 30 giorni"],        // 29 days ago
    [new Date(2026, 8, 18), "settembre 2026"],          // 30 days ago: month and year
    [new Date(2025, 1, 3), "febbraio 2025"],
  ]) assert.equal(groupOf(date, NOW), expected, `groupOf(${date.toDateString()})`);
});

test("shortWhen: the time for today and yesterday, the date before that", () => {
  for (const [date, expected] of [
    [new Date(2026, 9, 18, 9, 5), "09:05"],
    [new Date(2026, 9, 17, 22, 40), "22:40"],
    [new Date(2026, 9, 16, 10, 0), "16 ott"],           // two days ago: date, not time
    [new Date(2026, 2, 2), "2 mar"],
  ]) assert.equal(shortWhen(date, NOW), expected, `shortWhen(${date.toDateString()})`);
});

// ---------------------------------------------------------------- find in the call

test("fold: lowercase, no accents, no punctuation at the edges", () => {
  for (const [text, expected] of [
    ["Ciao,", "ciao"],
    ["perché", "perche"],
    ["Però!", "pero"],
    ["«ok»", "ok"],
    ["E'", "e"],                         // a trailing apostrophe is edge punctuation
    ["dell'impatto", "dell'impatto"],    // an inner apostrophe is kept
    ["3,5", "3,5"],                      // inner punctuation is kept
    ["CITTÀ", "citta"],
    ["naïve", "naive"],
    ["...", ""],
  ]) assert.equal(fold(text), expected, `fold(${JSON.stringify(text)})`);
});

test("forms: an elided article is searchable with and without it", () => {
  for (const [text, expected] of [
    ["ciao", ["ciao"]],
    ["dell'impatto", ["dell'impatto", "impatto"]],
    ["Un'ora,", ["un'ora", "ora"]],
    ["L'HO", ["l'ho", "ho"]],
    ["dell’area", ["dell’area", "area"]],   // typographic apostrophe
    ["'sta", ["sta"]],                   // a leading apostrophe folds away: no elision left
    ["po'", ["po"]],
  ]) assert.deepEqual(forms(text), expected, `forms(${JSON.stringify(text)})`);
});

test("findMatches: single words, folded on both sides", () => {
  assert.deepEqual(findMatches("ciao", [["Ciao,", "mondo."]]),
                   [{ seg: 0, start: 0, end: 1 }]);
  // Accents are ignored in the query and in the text, in both directions.
  assert.deepEqual(findMatches("perche", [["perché"]]), [{ seg: 0, start: 0, end: 1 }]);
  assert.deepEqual(findMatches("perché", [["perche"]]), [{ seg: 0, start: 0, end: 1 }]);
  // Every occurrence is a hit of its own.
  assert.deepEqual(findMatches("sì", [["sì", "sì", "va", "bene"]]),
                   [{ seg: 0, start: 0, end: 1 }, { seg: 0, start: 1, end: 2 }]);
});

test("findMatches: elided articles", () => {
  const segs = [["parlo", "dell'impatto", "economico"]];
  assert.deepEqual(findMatches("impatto", segs), [{ seg: 0, start: 1, end: 2 }]);
  assert.deepEqual(findMatches("dell'impatto", segs), [{ seg: 0, start: 1, end: 2 }]);
  // "dell" alone would match too many things: it is not a form of "dell'impatto".
  assert.deepEqual(findMatches("dell", segs), []);
});

test("findMatches: phrases are consecutive words in one segment", () => {
  assert.deepEqual(findMatches("grande impatto", [["un", "grande", "impatto"]]),
                   [{ seg: 0, start: 1, end: 3 }]);
  assert.deepEqual(findMatches("grande   impatto", [["un", "grande", "impatto"]]),
                   [{ seg: 0, start: 1, end: 3 }]);
  // A phrase does not span two segments: they are different lines of the call.
  assert.deepEqual(findMatches("grande impatto", [["molto", "grande"], ["impatto", "forte"]]),
                   []);
  assert.deepEqual(findMatches("impatto", [["molto", "grande"], ["impatto", "forte"]]),
                   [{ seg: 1, start: 0, end: 1 }]);
});

test("findMatches: an empty or blank query matches nothing", () => {
  assert.deepEqual(findMatches("", [["ciao"]]), []);
  assert.deepEqual(findMatches("   ", [["ciao"]]), []);
  assert.deepEqual(findMatches("...", [["ciao"]]), []);  // folds to nothing
});

// ---------------------------------------------------------------- doubtful runs

function W(text, start, doubtful = false) {
  return { text, start, doubtful };
}

test("doubtfulRuns: consecutive doubtful words become one run", () => {
  // No doubtful words: nothing to review.
  assert.deepEqual(doubtfulRuns([W("ciao", 1), W("a", 2), W("tutti", 3)], 0, "mic", 1), []);
  // One doubtful word in the middle.
  assert.deepEqual(doubtfulRuns([W("ciao", 1), W("a", 2, true), W("tutti", 3)], 4, "mic", 1),
                   [{ seg: 4, start: 1, end: 2, t: 2, channel: "mic" }]);
  // Three in a row are one run, timed at the first word.
  assert.deepEqual(
    doubtfulRuns([W("ok", 1), W("la", 2, true), W("bozza", 3, true), W("va", 4, true),
                  W("bene", 5)], 0, "system", 1),
    [{ seg: 0, start: 1, end: 4, t: 2, channel: "system" }]);
  // A sure word splits two runs; the edges of the segment count too.
  assert.deepEqual(
    doubtfulRuns([W("mah", 1, true), W("sì", 2), W("boh", 3, true)], 2, "mic", 1),
    [{ seg: 2, start: 0, end: 1, t: 1, channel: "mic" },
     { seg: 2, start: 2, end: 3, t: 3, channel: "mic" }]);
});

test("doubtfulRuns: a word without a start falls back to the segment start", () => {
  assert.deepEqual(doubtfulRuns([W("ehm", undefined, true)], 0, "mic", 7.5),
                   [{ seg: 0, start: 0, end: 1, t: 7.5, channel: "mic" }]);
});

// ---------------------------------------------------------------- picking the next run

// Three runs, deliberately out of order: pickRun must sort by time itself.
const RUNS = [{ t: 20 }, { t: 5 }, { t: 10 }];

test("pickRun: the next or previous run, wrapping at the ends", () => {
  assert.equal(pickRun(RUNS, 1, 7).t, 10);
  assert.equal(pickRun(RUNS, -1, 7).t, 5);
  assert.equal(pickRun(RUNS, 1, 25).t, 5);     // past the last: wrap to the first
  assert.equal(pickRun(RUNS, -1, 2).t, 20);    // before the first: wrap to the last
  assert.equal(pickRun(RUNS, 1, -1).t, 5);     // nothing played yet: start from the top
});

test("pickRun: the run just reached is not offered again", () => {
  // Standing exactly on t=10, "next" moves on and "previous" moves back.
  assert.equal(pickRun(RUNS, 1, 10).t, 20);
  assert.equal(pickRun(RUNS, -1, 10).t, 5);
});

test("pickRun: no runs, nothing to pick", () => {
  assert.equal(pickRun([], 1, 0), null);
});

// ---------------------------------------------------------------- playback gain

test("playbackGain: a quiet channel is raised to -18 LUFS", () => {
  // -38 LUFS needs +20 dB: a linear gain of 10.
  assert.ok(Math.abs(playbackGain(-38) - 10) < 1e-9);
  // -24 LUFS needs +6 dB: very close to 2.
  assert.ok(Math.abs(playbackGain(-24) - 1.995) < 0.01);
});

test("playbackGain: never more than +30 dB", () => {
  // -49 LUFS (a real headset mic) would need +31 dB; the boost stops at 10^(30/20).
  assert.ok(Math.abs(playbackGain(-49) - 31.623) < 0.01);
  assert.equal(playbackGain(-60), playbackGain(-69.9));
});

test("playbackGain: a loud channel is never lowered", () => {
  assert.equal(playbackGain(-16), 1);   // the system track of a real call
  assert.equal(playbackGain(-18), 1);   // exactly on target
  assert.equal(playbackGain(-3), 1);
});

test("playbackGain: unknown or silent plays as recorded", () => {
  assert.equal(playbackGain(undefined), 1);
  assert.equal(playbackGain(null), 1);
  assert.equal(playbackGain(NaN), 1);
  assert.equal(playbackGain("-40"), 1);        // a string is not a measurement
  assert.equal(playbackGain(-70), 1);          // ebur128's floor: an empty track
  assert.equal(playbackGain(-Infinity), 1);
});
