# Voice activity detection (VAD) before Whisper — 2026-10-15

**Problem.** In the first test recording (`ilat record`, 15 s) the "Altri" channel had 9.6 s of silence and then an advert. Whisper turbo wrote "Grazie a tutti." over all 15 seconds: an invented sentence. It also chose the language on the first window, almost all silence. In a call each channel is often silent while the other one speaks, so the problem is structural.

**Method.** Each variant is a `turbo-vad` system in `ilat eval`, on the `adjudicated` references (it-002, en-002), and is also tried on the test recording. A level detector (`ilat.audio.vad`) finds the stretches with sound. It covers 912 s against 891 s of speech in the it-002 reference, and 1633 s against 1606 in en-002: it does not cut speech.

| Variant | Fidelity WER (all) | it-002 | en-002 | "Grazie a tutti" in the test |
|---|---|---|---|---|
| turbo without VAD | **5.1** | 4.8 | 5.3 | yes |
| v1: only the stretches with sound (`clip_timestamps`, 106–108 pieces) | 27.9 | 15.8 | 35.6 | no |
| v2: language on speech + `hallucination_silence_threshold` | 8.1 | 8.0 | 8.2 | — |
| v3: language on speech + dropping segments with little sound | 5.2 | 5.0 | 5.3 | yes |
| v4: each block of sound (≤ 28 s) decoded on its own | 10.2 | 10.8 | 9.8 | no |
| v5: stretches split only by silences ≥ 3 s | 8.7 | 9.5 | 8.2 | no |
| v6: decoding from the first sound (+ filter) | 8.3 | **12.9** | 5.3 | no |
| **v7: language on speech + dropping segments with no words over sound** | **5.1** | 4.9 | 5.3 | yes |

## What we learned

1. **Whisper is sensitive to how the windows are aligned.** In v6 the only difference on it-002 is that decoding starts 4 seconds later: Whisper skips about a hundred real words (up to 49 in a single segment) and fidelity goes from 4.8% to 12.9%. On en-002 the same change makes no difference. So every variant that shifts the windows (v1, v4, v5, v6) is at risk, and on a single file differences of a few points can be down to chance. Besides seeds, alignment is also a source of variability.
2. **The filter must work on the words, not on the segment's duration.** Dropping segments with a small share of sound removed long segments with few real words. The criterion "no words over sound" is safe.
3. **Detecting the language on speech is harmless on the test set**, where the language was already right. It helps when a channel starts with silence or music.
4. **"Grazie a tutti" in the test does not go away with v7**, because Whisper aligns the invented words over the advert (real sound). Removing it would mean shifting the decoding, and that is what breaks it-002.

## Decision

- **`ilat record` uses v7** (`MLXWhisperBackend(vad=True)`): neutral on the test set, it drops silent channels and segments written over silence, and chooses the language on speech.
- **Invented sentences over real sound are not solved.** To be tackled by flagging doubtful points, that is two transcripts compared (see PLAN), not by further tweaks to decoding.
