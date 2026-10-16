# Comparison on the `adjudicated` references — 2026-10-15

References: it-002 (16 min) and en-002 (29 min), `adjudicated`. Every disagreement between the silver reference and CrisperWhisper was decided by ear by Jacopo, or by the automatic rule for repetitions, truncated words and fillers, checked on samples. Full reports: [seed 0](2026-10-15-adjudicated.md), [seed 1](2026-10-15-adjudicated-seed1.md), [seed 2](2026-10-15-adjudicated-seed2.md).

## Fidelity WER (primary metric, decision 0010)

| System | IT | EN | substitutions IT / EN | literal WER (all) | fillers kept |
|---|---|---|---|---|---|
| Whisper turbo | **4.8** [3.6–6.3] | 5.3 [4.3–6.5] (seeds 1–2: 5.4 / 7.9) | 2.5 / 1.6 | 8.1 | 2/466 |
| turbo with prompt | 7.2 | 8.2 (seeds: 5.5 / 5.9) | 2.8 / 3.0 | 10.5 | 9/466 |
| **CrisperWhisper 2.0 turbo** | 8.5 [6.4–10.7] | **2.7** [2.0–3.6] | 3.0 / **1.2** | **5.3** | **448/466** |
| Parakeet v3 | 16.7 | 10.1 | 6.5 / 3.8 | 14.5 | 315/466 |
| large-v3 | 27.2 | 21.9 | 6.5 / 3.4 | 26.0 | 70/466 |

## What they say

1. **Italian: Whisper turbo is the most faithful.** On the substitutions he listened to, Jacopo chose turbo's text (reference A) 68 times and CrisperWhisper's 22. CrisperWhisper also drops words that were spoken (12 cases out of 13 listened to).
2. **English: CrisperWhisper is the most faithful** (2.7% against 5.3–7.9% for turbo, depending on the seed). Consistent with its training (EN/DE).
3. **On kept speech CrisperWhisper always wins**: 96% of the fillers and 48 truncated words out of 49, against almost none for turbo.
4. **The disfluency prompt makes turbo worse** in Italian, and in English it does not improve it consistently.
5. **Parakeet and large-v3 are out of the running:** Parakeet rewords (6.5% substitutions in Italian), large-v3 generates loops.

## Limits

- **One file per language** (16 and 29 minutes): the intervals overlap little, but en-001 and it-001 are needed to confirm, even if only on samples.
- **it-002:** 38 CrisperWhisper insertions were not listened to and count as A, so they do not enter the reference. This penalises CrisperWhisper a little in Italian: in the sample check, 7 out of 8 were real.
- **en-002:** the fillers added by CrisperWhisper were accepted despite a check of 6 out of 9 (Jacopo's choice). They weigh only on the secondary metrics, not on fidelity.
- **The A references started from turbo's draft**, corrected by hand. On substitutions, listening makes the comparison fair, but where turbo and the reference agree because of anchoring, the error stays invisible.
- **CrisperWhisper's licence** is non-commercial (decision 0009).

## Implications (to be decided)

- **Default engine:** turbo (free, fast, the best in Italian). **CrisperWhisper as an option for English** and for those who want complete speech, for non-commercial use only.
- **Fine-tuning:** a LoRA on AMI and ICSI (English) would improve turbo where CrisperWhisper is already better, but not Italian, which is the main use case. Distilling CrisperWhisper for Italian would inherit its flaws. For now it does not look like a priority.
