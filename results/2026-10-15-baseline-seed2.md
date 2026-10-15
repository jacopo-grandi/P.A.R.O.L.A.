# Baseline — 2026-10-15

Commit `90a7523`. Generato da `ilat eval`. Valori in %, tra parentesi l'intervallo di confidenza al 95% (bootstrap sui segmenti).

**Riferimenti** (2 file, 0.76 h): it-002 (it, 17 min, silver), en-002 (en, 29 min, silver).

## Sistemi

- `turbo`: large-v3-turbo, language detected
- `turbo-prompt`: large-v3-turbo, language detected, disfluency prompt

## Risultati

| Sistema | Ambito | WER letterale | WER classico | WER verbatim | Filler recall | Filler precision | RTF |
|---|---|---|---|---|---|---|---|
| `turbo` | all | 4.9 [3.2-7.0] | 4.6 [3.0-6.6] | 9.4 [7.7-11.4] | 13.9 | 87.5 | 0.048 |
| `turbo` | lang:en | 6.8 [4.0-10.3] | 6.2 [3.6-9.6] | 13.0 [10.4-16.1] | 15.4 | 87.0 | 0.049 |
| `turbo` | lang:it | 2.0 [1.2-2.9] | 2.0 [1.2-2.9] | 3.7 [2.8-4.8] | 4.3 | 100.0 | 0.046 |
| `turbo` | it-002 | 2.0 [1.2-2.9] | 2.0 [1.2-2.9] | 3.7 [2.8-4.8] | 4.3 | 100.0 | 0.046 |
| `turbo` | en-002 | 6.8 [4.0-10.3] | 6.2 [3.6-9.6] | 13.0 [10.4-16.1] | 15.4 | 87.0 | 0.049 |
| `turbo-prompt` | all | 6.1 [5.0-7.3] | 5.5 [4.5-6.6] | 11.1 [10.0-12.2] | 2.3 | 80.0 | 0.050 |
| `turbo-prompt` | lang:en | 4.9 [3.7-6.5] | 4.7 [3.6-6.0] | 12.2 [10.8-13.9] | 0.0 | — | 0.053 |
| `turbo-prompt` | lang:it | 7.8 [6.2-9.7] | 6.8 [5.2-8.6] | 9.2 [7.6-11.0] | 17.0 | 80.0 | 0.046 |
| `turbo-prompt` | it-002 | 7.8 [6.2-9.7] | 6.8 [5.2-8.6] | 9.2 [7.6-11.0] | 17.0 | 80.0 | 0.046 |
| `turbo-prompt` | en-002 | 4.9 [3.7-6.5] | 4.7 [3.6-6.0] | 12.2 [10.8-13.9] | 0.0 | — | 0.053 |

## Disfluenze conservate (tutti i file)

| Sistema | filler | truncated | repetition | false_start | edit_term | filler inventati |
|---|---|---|---|---|---|---|
| `turbo` | 49/352 | 0/1 | 0/0 | 0/0 | 0/0 | 7 |
| `turbo-prompt` | 8/352 | 0/1 | 0/0 | 0/0 | 0/0 | 2 |

## Come leggere i numeri

- **WER letterale** è la metrica principale (decisione 0007): tolte solo le esitazioni, tutto il resto conta parola per parola.
- **RTF**: tempo di elaborazione / durata dell'audio, sul Mac (M4 Pro).
- **Riproducibilità**: seme casuale MLX fisso (0). Il temperature fallback di Whisper campiona a caso: senza seme due run dello stesso sistema danno numeri diversi.
- **Riferimenti silver**: parole verificate da una persona, esitazioni in gran parte proposte da Whisper large-v3-turbo. Le metriche sulle esitazioni sono ottimistiche per le varianti di turbo, soprattutto con prompt.
- **Ancoraggio**: i riferimenti partono dalla bozza di large-v3-turbo; i sistemi turbo sono avvantaggiati rispetto agli altri modelli.
- Con pochi riferimenti gli intervalli sono larghi: differenze dentro gli intervalli non sono significative.
