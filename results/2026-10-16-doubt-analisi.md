# Doubtful points: which second transcript best flags turbo's errors — 2026-10-16

**Question.** If we also transcribe every call with a second system and flag the Whisper turbo words that the second does not confirm, how many of turbo's errors do we catch, and how much has to be checked again?

**Method** (`ilat.doubt`).
- Turbo, the default engine, and the second transcript are aligned on fidelity tokens, that is without fillers and repetitions ([0010](../docs/decisions/0010-fidelity-metric.md)). A turbo word is flagged if the second transcript replaces it or does not have it, or if the second has extra words right next to it.
- Turbo's errors are computed the same way against the `adjudicated` references of it-002 and en-002: 374 words with an error out of 5761, that is **6.5%**. Flagging words at random, the precision would be exactly 6.5%.
- Window 1 = one word before and one after are flagged too, as a highlight in the interface would do.

## Results

| Second opinion | Licence | Turbo errors caught (IT / EN) | Correct flags | Words to check again |
|---|---|---|---|---|
| turbo, another seed | MIT | 2–29% (IT 0%) | 48–53% | 0.3–4% |
| turbo with prompt | MIT | 40% (50% / 33%) | 38% | 6.9% |
| **Parakeet v3** | **CC BY** | **66%** (65% / 66%) | **35%** | **12.4%** |
| large-v3 | MIT | 57% | 25% | 14.7% |
| Parakeet ∪ turbo with prompt | free | **79%** (78% / 79%) | 31% | 16.3% |
| CrisperWhisper (*) | non-commercial | 84% | 59% | 9.3% |

With window 1, Parakeet catches 77% of the errors (precision 20%, 25% of the words), and Parakeet ∪ turbo with prompt 86% (31% of the words).

(*) **CrisperWhisper has an advantage by construction:** the references were built precisely from the disagreements between the reference and CrisperWhisper. The numbers for Parakeet and turbo with prompt, instead, are fair: those systems played no part in building the references.

## What it means

1. **Parakeet is the right second opinion for default use.** It has a free licence, it is very fast (about 1 minute per hour of audio, almost nothing on top of turbo) and, by checking 12% of the words again, it catches two turbo errors out of three. Its flags are correct 5 times more often than random ones (35% against 6.5%). That it is a worse transcriber than turbo, and that it rewords Italian, is an advantage here: it makes mistakes in different places from turbo.
2. **Another turbo seed does not help:** in Italian turbo is deterministic, so two seeds give the same text and no flags.
3. **Adding turbo with prompt** brings the errors caught to 79%, but doubles the transcription time. It is an option for important calls.
4. **About a third of turbo's errors stay invisible:** they are the places where the second opinion makes the same mistake too. The same goes for errors shared by turbo and the reference, which this measure cannot see.

## Limits

- Two files (45 minutes), `adjudicated` references built starting from turbo and CrisperWhisper.
- The numbers depend on the definition of error: only fidelity tokens are counted, so fillers and repetitions do not count.
