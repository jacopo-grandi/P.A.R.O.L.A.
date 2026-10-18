# Long digital silence before Whisper — 2026-10-18

**Why.** On a one-minute test call recorded with the app, a video played twice on the system side: 11–27 s and 51–57 s, with exact digital zeros in between (nothing played). The second stretch was missing from the transcript, although the voice activity detection had found it (sound 50.8–57.0 s).

**What was measured.**

| Input to Whisper large-v3-turbo | Second stretch (51–57 s) |
|---|---|
| The whole system channel, as recorded | not transcribed; an invented "thank you" at 57 s instead |
| The channel from 48 s (2.8 s of zeros first) | not transcribed |
| The 7 s of the stretch alone | transcribed; Parakeet v3 gives the same words |
| The whole channel with every run of zeros over 3 s cut down to 1 s | transcribed, at 51.3–56.7 s on the original timeline |

So the speech itself is clear: Whisper skips it when its window opens on long digital silence.

**Change.** Runs of exact zeros at least 3 s long are shortened to 1 s before decoding (`parola.audio.silence`), and every segment and word time is mapped back to the original timeline; a segment starts on its first word.

**Effect on the test set.** None, by construction: the longest run of exact zeros in the four test-set recordings is 0.04 s (it-001, en-001) and 0.01 s (it-002, en-002), so no audio is changed and the fidelity WER stays as measured in `results/2026-10-15-vad.md`. Microphones always add some noise; exact zeros come from a call's system side when no app plays anything, or from the silence a device change fills in (under 2 s).

**Limits.** One test call. Silence that is near zero but not exactly zero (a quiet room through a virtual device, say) is not shortened.
