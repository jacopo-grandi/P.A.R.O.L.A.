# Baseline — 2026-10-15

Commit `6147475`. Generato da `ilat eval`. Valori in %, tra parentesi l'intervallo di confidenza al 95% (bootstrap sui segmenti).

**Riferimenti** (2 file, 0.76 h): it-002 (it, 17 min, silver), en-002 (en, 29 min, silver).

## Sistemi

- `turbo`: large-v3-turbo, language detected
- `turbo-prompt`: large-v3-turbo, language detected, disfluency prompt

## Risultati

| Sistema | Ambito | WER letterale | WER classico | WER verbatim | Filler recall | Filler precision | RTF |
|---|---|---|---|---|---|---|---|
| `turbo` | all | 3.7 [2.8-4.7] | 3.4 [2.6-4.3] | 8.8 [7.6-10.1] | 0.6 | 100.0 | 0.049 |
| `turbo` | lang:en | 4.7 [3.4-6.6] | 4.4 [3.2-5.7] | 12.0 [10.4-13.8] | 0.0 | — | 0.051 |
| `turbo` | lang:it | 2.0 [1.2-2.9] | 2.0 [1.2-2.9] | 3.7 [2.8-4.8] | 4.3 | 100.0 | 0.046 |
| `turbo` | it-002 | 2.0 [1.2-2.9] | 2.0 [1.2-2.9] | 3.7 [2.8-4.8] | 4.3 | 100.0 | 0.046 |
| `turbo` | en-002 | 4.7 [3.4-6.6] | 4.4 [3.2-5.7] | 12.0 [10.4-13.8] | 0.0 | — | 0.051 |
| `turbo-prompt` | all | 5.1 [3.9-6.5] | 4.4 [3.3-5.5] | 10.2 [9.0-11.6] | 2.3 | 80.0 | 0.047 |
| `turbo-prompt` | lang:en | 3.4 [1.9-5.3] | 2.8 [1.8-4.2] | 10.9 [9.3-12.9] | 0.0 | — | 0.047 |
| `turbo-prompt` | lang:it | 7.8 [6.2-9.7] | 6.8 [5.2-8.6] | 9.2 [7.6-11.0] | 17.0 | 80.0 | 0.046 |
| `turbo-prompt` | it-002 | 7.8 [6.2-9.7] | 6.8 [5.2-8.6] | 9.2 [7.6-11.0] | 17.0 | 80.0 | 0.046 |
| `turbo-prompt` | en-002 | 3.4 [1.9-5.3] | 2.8 [1.8-4.2] | 10.9 [9.3-12.9] | 0.0 | — | 0.047 |

## Disfluenze conservate (tutti i file)

| Sistema | filler | truncated | repetition | false_start | edit_term | filler inventati |
|---|---|---|---|---|---|---|
| `turbo` | 2/352 | 0/1 | 0/0 | 0/0 | 0/0 | 0 |
| `turbo-prompt` | 8/352 | 0/1 | 0/0 | 0/0 | 0/0 | 2 |

## Come leggere i numeri

- **WER letterale** è la metrica principale (decisione 0007): tolte solo le esitazioni, tutto il resto conta parola per parola.
- **RTF**: tempo di elaborazione / durata dell'audio, sul Mac (M4 Pro).
- **Riproducibilità**: seme casuale MLX fisso (0). Il temperature fallback di Whisper campiona a caso: senza seme due run dello stesso sistema danno numeri diversi.
- **Riferimenti silver**: parole verificate da una persona, esitazioni in gran parte proposte da Whisper large-v3-turbo. Le metriche sulle esitazioni sono ottimistiche per le varianti di turbo, soprattutto con prompt.
- **Ancoraggio**: i riferimenti partono dalla bozza di large-v3-turbo; i sistemi turbo sono avvantaggiati rispetto agli altri modelli.
- Con pochi riferimenti gli intervalli sono larghi: differenze dentro gli intervalli non sono significative.
