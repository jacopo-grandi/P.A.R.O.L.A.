# Language detection — 2026-10-16

**Why.** en-001 (an hour in English, the speaker is Italian), imported with language "Auto", came out in Italian: Whisper translated and mangled it for a whole hour ("Il più famoso algoritmo di clustering…"), with almost every line marked as doubtful. The language was decided only once, on the first 30 s of speech glued together (the stretches with sound given by the VAD).

**How.** Language probabilities from Whisper large-v3-turbo (`mlx_whisper.decoding.detect_language`, fp16) on the 4 files of the test set, with three methods:

1. **glued** (the previous method): the stretches with sound from the first 30 s of speech, concatenated;
2. **first 30 s** as they are (Whisper's default behaviour);
3. **5 windows**: 30 s of audio as it is, starting from 5 stretches with sound taken at regular intervals in the list, probabilities averaged, only between `it` and `en`.

**Results.**

| File | Language | Glued | First 30 s | 5 windows (each) |
|---|---|---|---|---|
| it-001 | it | it (it 1.00) | it (it 1.00) | it (it 1.00): it it it it it |
| it-002 | it | it (it 1.00) | it (it 1.00) | it (it 1.00): it it it it it |
| en-001 | en | **it** (it 0.50, en 0.43) | en (en 0.92) | en (en 0.95): en en en en en |
| en-002 | en | en (en 1.00) | en (en 0.48, it 0.00) | en (en 0.76): en en en en en |

On en-001 the raw audio windows say English everywhere (0.86–1.00 on 14 windows from 0 to 3521 s), except the one at 30 s (en 0.55, it 0.39). Gluing moves the decision to Italian: short pieces joined together seem to weigh the accent more than the language.

**Decision.** 5 windows (decision [0030](../docs/decisions/0030-language-from-windows-and-asked-on-import.md)): 4 out of 4, always with a margin. The final module (`parola.asr.language.detect`), tried on the same 4 files, gives 4 out of 4. On it-002 and en-002, the two files with a reference, the chosen language does not change, so the measured WERs stay those of `results/2026-10-15-vad.md`.

**Limits.** Four files are few; there is no mixed IT/EN file in which the main language is uncertain. Cost measured on en-001: 1.9 s (reading the audio included, model already loaded) on an M4 Pro, against about 7 minutes of transcription.
