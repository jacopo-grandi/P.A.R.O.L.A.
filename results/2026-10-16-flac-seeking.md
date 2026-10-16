# Seeking in the audio: FLAC in WebKit — 2026-10-16

**Why.** On en-001 (an hour) in the native app, text and audio did not match, even when clicking a word. The transcript's times are not the cause: transcribing 12 scattered points again with Whisper, cut with ffmpeg from the FLAC and from the original m4a, the two cuts give the same text at all 12 points (similarity with the transcribed text 0.45–1.00, identical between FLAC and m4a). The problem is where the player lands.

**How.** A one-hour test file (16 kHz mono, encoded like `parola compress`): loud noise from second 5 to 30 of each minute, quiet noise from 40 to 50, silence elsewhere, and a 0.3 s beep at 1 kHz exactly on every minute. A page jumps to a few seconds before a beep, starts the audio and listens with Web Audio for when the beep arrives. Tried in Chromium (the browser pane) and in a WKWebView like the app's.

**Results.**

| Engine | File | Jumps | Outcome |
|---|---|---|---|
| Chromium | FLAC | 5, from 5 to 59 min | exact beep: error 0.01–0.02 s |
| WebKit | WAV | 6, then 8 repeated | beep where expected (2.9–3.6 s after a 3 s jump); some readings at 0.5 s are the previous beep left in the test's buffer |
| WebKit | FLAC | 5 + 6 + 8 | beep almost never heard within 8 s; once 23 s later, once almost right (−0.9 s) |
| WebKit | FLAC with SEEKTABLE (360 points, one every 10 s, identical samples) | 6 | as without: beep never heard |

**Decision.** Calls stay FLAC on disk, and the player gets a WAV copy decoded when the call is opened. On en-001: 0.6 s the first time, then immediate.

**Limits.** The WebKit test measures with Web Audio inside the page, which adds a variable delay at start; this is why the WAV is "where expected" and not "exact to the hundredth". The whole chain (server → WAV → WebKit) was not measured with the beep; its pieces were.
