# Listening check of CrisperWhisper's insertions — 2026-10-15

**Question.** CrisperWhisper 2.0 turbo has a literal WER of 12.8% on the silver references (it-002, en-002), against 3.5% for Whisper turbo. Of this 12.8%, 507 errors out of 755 are **insertions**: words written by CrisperWhisper and missing from the reference. The references start from turbo's draft. Are the insertions invented words, or real speech that the references lost?

**Method.** `ilat audit build --system crisper-turbo-lang`: 30 insertions drawn at random with seed 0, by category. For each one a clip of about 4 s; Jacopo listened to all of them and marked "vero" (really said) or "falso" (invented).

## Result

| Category | real | invented | % real |
|---|---|---|---|
| repetitions ("to to", "we we") | 10 | 0 | 100% |
| truncated words ("m-", "li-") | 6 | 0 | 100% |
| fillers ("uh", "eh") | 6 | 2 | 75% |
| other words | 6 | 0 | 100% |
| **total** | **28** | **2** | **93%** |

All 22 non-filler insertions (the ones that count in the literal WER) were real speech. With 22 cases out of 22, the real share is at least 87% at 95% confidence (rule of three).

## What changes

If between 87% and 100% of the 507 insertions are real, the silver references **are missing 440–510 words that were actually spoken** (about 8%: repetitions, false starts, truncated words). With the references corrected, the estimated literal WER becomes:

| System | Literal WER on the silver references | estimate with corrected references |
|---|---|---|
| Whisper large-v3-turbo | 3.5% | **10–11%** |
| CrisperWhisper 2.0 turbo | 12.8% | **4–5%** |

The ranking **is reversed**. Turbo looked like the best because the references were built from its draft and inherited its cuts: this is the expected anchoring, and the check measures its size. The estimate assumes that turbo does not contain those words, and this is true by construction: the references come from its draft.

## Consequences

1. **The silver references are not literal.** They are fine for the vocabulary, but they are missing most of the repetitions and false starts. The metrics need references built by listening.
2. **The drafts for en-001 and it-001 are better made with CrisperWhisper**, not with turbo: they are already close to verbatim and need fewer corrections. The anchoring remains, but in favour of the real speech.
3. **CrisperWhisper is already close to the project's goal**, in Italian too. Its licence, however, is non-commercial: fine for personal use and research, not for commercial use of the app. Fine-tuning (Phases 3–5) is still useful to get a model with a free licence.
