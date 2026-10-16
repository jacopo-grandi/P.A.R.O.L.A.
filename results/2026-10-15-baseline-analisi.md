# Baseline of 2026-10-15 — analysis

> **Update:** the primary metric is now the **fidelity WER**, that is the former "classic WER" with the same values. On the silver references: turbo 3.3% (1.4% substitutions), CrisperWhisper 9.1% (2.8%), Parakeet 14.1% (4.9%). Those references start from turbo: the final numbers will come with the `adjudicated` references. The tables below still use the literal WER, the primary metric until 0010.

References: it-002 (16 min) and en-002 (29 min), both `silver`. Full reports: [seed 0](2026-10-15-baseline.md), [seed 1](2026-10-15-baseline-seed1.md), [seed 2](2026-10-15-baseline-seed2.md).

## Literal WER (primary metric) as the seed changes

Seeds 0–2 are computed with the final normalisation (`okay` = `ok`); the "no seed" column with the previous one.

| System | Language | no seed | seed 0 | seed 1 | seed 2 |
|---|---|---|---|---|---|
| `turbo` | it | 2.0 | 2.0 | 2.0 | 2.0 |
| `turbo` | en | 3.2 | 4.5 | 4.7 | 6.6 |
| `turbo-prompt` | it | 7.8 | 7.8 | 7.8 | 7.8 |
| `turbo-prompt` | en | 3.2 | 5.6 | 3.4 | 4.7 |
| `large-v3-lang` | all | 19.1 | 25.4 | — | — |

## What the numbers say

1. **turbo without a prompt is the best.** Literal WER about 2% in Italian, between 3% and 7% in English depending on the seed, RTF about 0.05 (an hour of audio in about 3 minutes on the Mac).
2. **Forcing the language changes nothing:** `turbo` and `turbo-lang` give identical output, word for word, because language detection was already right. On mixed IT/EN files it could be different.
3. **The disfluency prompt makes Italian worse** (from 2.0% to 7.8%, stable across all seeds, intervals that do not overlap). The added errors are mostly **insertions**: text the reference does not have. It may be invented text, or real speech that the reference lost, because the reference starts from turbo's draft **without** the prompt. This needs checking by listening, for example it-002 at 408–414 s. In English the effect is within the variability between seeds.
4. **Whisper drops almost all fillers:** turbo keeps 2 out of 352 (0.6%), with the prompt 8 out of 352. The prompt is not a solution. This confirms the project's goal: fine-tuning is needed for the fillers, not for the words.
5. **large-v3 is much worse than turbo:** it generates hallucinated loops in stretches of silence or noise (up to 138 invented words in a 2 s segment), and it is about 3 times slower.
6. **English depends on chance.** When decoding fails, Whisper resamples at a higher temperature: the same system varies by about ±1.5 points from one seed to another. Italian on it-002, instead, is stable. The bootstrap intervals do not include this variability: comparing systems in English needs more seeds.

## Limits

- **Two files, both silver**, so wide intervals.
- **Anchoring:** the references start from turbo's draft (seed not fixed), and whoever corrects tends to confirm it. Turbo has an advantage over any other system, even over itself with the prompt.
- **The references' fillers** were mostly proposed by turbo with various windows and prompts, and checked on samples: the filler recall is optimistic for the turbo variants.
- On en-002 the final repetition "Bye-bye" in the reference may be a Whisper loop confirmed during review.

## Parakeet v3 and CrisperWhisper 2.0 turbo (seed 0)

| System | Literal WER IT | Literal WER EN | Fillers kept | "Invented" fillers | RTF |
|---|---|---|---|---|---|
| `turbo` | 2.0 | 4.5 | 2/352 | 0 | 0.047 |
| `parakeet-v3` | 16.9 | 14.7 | 252/352 (IT 0%) | 95 | **0.013** |
| `crisper-turbo-lang` | 15.5 | 11.0 | **322/352** | 157 | 0.16 |

7. **CrisperWhisper is the only one that keeps the fillers** (92%, 94% in Italian, even though it was built for EN/DE). Its high literal WER is made mostly of **insertions**: 507 out of 759 errors. Of these, **181 repeat a nearby word** ("sì sì", "the the") and **31 are truncated words** ("th-"). Almost certainly many are **real speech missing from the references**: the silver references start from turbo's draft, which drops repetitions and false starts. Much of the 157 "invented" fillers may be real too, because the references' fillers are incomplete by construction. Until a listening check, **CrisperWhisper's numbers are pessimistic and turbo's optimistic**.
8. **Parakeet rewords Italian:** "però" → "tuttavia" (6 times), "concentrerei" → "concentrare". This is the rewording that decision 0007 wants to avoid, and in Italian it drops all the fillers. In English it keeps them (83%). It is by far the fastest: an hour in less than a minute.
9. **Normalisation:** `okay`/`ok`, `perchè`/`perché` and similar now count as the same word (conventions §2.9).

## Listening check (update)

The check of 30 CrisperWhisper insertions ([2026-10-15-audit-crisper.md](2026-10-15-audit-crisper.md)) gives **93% real speech**, and 100% on the 22 non-filler ones. The silver references are missing about 8% of the words spoken. With corrected references, the estimates are **CrisperWhisper about 4–5% and turbo about 10–11%** literal WER: the ranking on this page is reversed.

## Next steps

- **Check the anchoring by listening:** a sample of CrisperWhisper's insertions (repetitions, truncated words, fillers), with audio clips. If they are real, the references must be corrected at those points, and CrisperWhisper becomes the best base to start from (drafts and fine-tuning). Mind its non-commercial licence, though.
- Complete the test set (en-001, it-001) and rerun with 3 seeds.
- Listen to a sample of `turbo-prompt`'s insertions on it-002.
