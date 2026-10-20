# Titles: the hedges of meeting speech — 2026-10-20

The first imported real meeting broke the suggested title. On a 43-minute public English
meeting (a work meeting from YouTube) the two best key phrases were *kind* (said 22 times,
score 3280) and *things* (19, 2106), so the title was **"Kind and things"**, while the actual
subject sat right below: *Gitlab*, *competitors*, *vulnerability management*, *tier*.

## Cause

The frequency stop list cuts a word at Zipf ≥ 6 (`FREQUENT_ZIPF`, wordfreq). wordfreq counts
**written** text, and the hedges of meeting speech — *kind* (5.45), *things* (5.74), *look*
(5.81), *little* (5.75), *guys* (5.41), *year* (5.96); *lavoro* (5.91), *momento* (5.69) — sit
just under the bar at Zipf 5.4–6 while being said far more often than written. Their term
frequency in an hour of talk beats any real topic, so they top the TF-IDF score.

## Candidates compared

Per the procedure in METHODOLOGY ("Measuring it on new calls"): recompute the suggestion for
every call of the title set (6 calls, 5.5 hours, 1 Italian + 5 English; one renamed by hand,
which makes its chosen title a reference) and read the titles and top phrases side by side.

| Candidate | Measured case | Renamed call | Kept titles |
|---|---|---|---|
| baseline (bar 6) | "Kind and things" | misses the reference | kept |
| bar 5.5, call's language | "Kind and competitors" — *kind* is 5.45, still in | misses | kept |
| **bar 5.4, call's language** | **"Competitors and Gitlab"** | **reproduces the chosen title word for word** | equal or better on all 4 |
| bar 5.2, call's language | "Competitors and Gitlab" | reproduces it | equal or better, but legitimate words at 5.2–5.4 die too (*record* 5.21, *points* 5.23, *stuff* aside) |
| declared hedge stop list | "Competitors and Gitlab" | misses (keeps *rule set*, *number of rules*) | kept, but *little*, *thought*, *end* climb into the top phrases: the class is bigger than any list |
| bar 5.4 + hedge list | same as bar 5.4 | same | same titles; no gain at title level |

## Choice: Zipf ≥ 5.4 in the language of the segment itself (`SPOKEN_ZIPF`)

Added to the existing bar (Zipf ≥ 6 in either language), not replacing it. The lower bar
applies only in the language a word was said in: a word merely common in the *other* language
can still name a call.

Per-call outcome (titles of the two public YouTube imports reproduced; the other calls are
private or test-set material):

| Call | Before | After |
|---|---|---|
| public meeting, en, 43 min | "Kind and things" | **"Competitors and Gitlab"**; top phrases now *competitors*, *Gitlab*, *vulnerability management*, *stage*, *tier* |
| public council meeting, en, 104 min | "Councils and year" | "Councils and region" |
| renamed call, en, 97 min | missed the chosen title ("… and Thank") | reproduces it word for word |
| test-set lecture, en, 60 min | kept | equal or better (*point* → *clusters*) |
| test-set lecture, en, 29 min | kept | same but for singular/plural |
| trial recording, it, 1.5 min | kept | better (a country name replaces *paese*) |

## What dies at 5.4, what stays

The 5.4–6 band holds only all-purpose words in both languages: *year, look, little, things,
team, number, set, week, point, kind, means, guys*; *lavoro, casa, mondo, anno, momento,
problema, paese, sistema, settimana*. Topic words sit below it and stay: *data* (5.34),
*market* (5.29), *security* (5.20), *model* (5.13); *progetto* (5.35), *dati* (5.33),
*sicurezza* (5.30), *mercato* (5.24). The closest real loss is *team* (5.67) — alone it would
make a vague title anyway. Hedges **below** 5.4 (*stuff* 5.14, *sort* 5.00) survive the bar
but never reached a title in the set; if they do, a declared stop list remains the fallback.

Hand-built cases for the hedge class are in `tests/test_keywords.py`
(`test_spoken_hedges_do_not_name_an_english_call`, `..._italian_call`).
