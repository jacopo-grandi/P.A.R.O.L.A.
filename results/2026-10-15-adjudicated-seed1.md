# Baseline — 2026-10-15

Commit `3644324`. Generato da `ilat eval`. Valori in %, tra parentesi l'intervallo di confidenza al 95% (bootstrap sui segmenti).

**Riferimenti** (2 file, 0.76 h): it-002 (it, 17 min, adjudicated), en-002 (en, 29 min, adjudicated).

## Sistemi

- `turbo`: large-v3-turbo, language detected
- `turbo-prompt`: large-v3-turbo, language detected, disfluency prompt

## Risultati

| Sistema | Ambito | **WER di fedeltà** | sost. | WER letterale | WER verbatim | Filler recall | Filler precision | RTF |
|---|---|---|---|---|---|---|---|---|
| `turbo` | all | **5.2 [4.3-6.1]** | 2.1 | 8.3 [7.2-9.5] | 14.5 [12.9-16.1] | 0.4 | 100.0 | 0.049 |
| `turbo` | lang:en | **5.4 [4.4-6.7]** | 1.8 | 8.4 [6.8-10.4] | 16.7 [14.6-19.0] | 0.0 | — | 0.051 |
| `turbo` | lang:it | **4.8 [3.6-6.3]** | 2.5 | 8.0 [6.5-9.7] | 10.9 [9.3-12.6] | 2.4 | 100.0 | 0.046 |
| `turbo` | it-002 | **4.8 [3.6-6.3]** | 2.5 | 8.0 [6.5-9.7] | 10.9 [9.3-12.6] | 2.4 | 100.0 | 0.046 |
| `turbo` | en-002 | **5.4 [4.4-6.7]** | 1.8 | 8.4 [6.8-10.4] | 16.7 [14.6-19.0] | 0.0 | — | 0.051 |
| `turbo-prompt` | all | **6.2 [5.2-7.3]** | 2.0 | 9.1 [7.8-10.7] | 15.2 [13.7-17.1] | 1.9 | 90.0 | 0.047 |
| `turbo-prompt` | lang:en | **5.5 [4.3-6.7]** | 1.5 | 8.6 [6.8-10.8] | 16.9 [14.6-19.4] | 0.0 | — | 0.047 |
| `turbo-prompt` | lang:it | **7.2 [5.6-9.2]** | 2.8 | 9.9 [8.2-11.9] | 12.4 [10.8-14.4] | 10.7 | 90.0 | 0.046 |
| `turbo-prompt` | it-002 | **7.2 [5.6-9.2]** | 2.8 | 9.9 [8.2-11.9] | 12.4 [10.8-14.4] | 10.7 | 90.0 | 0.046 |
| `turbo-prompt` | en-002 | **5.5 [4.3-6.7]** | 1.5 | 8.6 [6.8-10.8] | 16.9 [14.6-19.4] | 0.0 | — | 0.047 |

## Disfluenze conservate (tutti i file)

| Sistema | filler | truncated | repetition | false_start | edit_term | filler inventati |
|---|---|---|---|---|---|---|
| `turbo` | 2/466 | 0/49 | 0/0 | 0/0 | 0/0 | 0 |
| `turbo-prompt` | 9/466 | 0/49 | 0/0 | 0/0 | 0/0 | 1 |

## Come leggere i numeri

- **WER di fedeltà** è la metrica principale (decisione 0010): conta se le parole sono quelle dette, senza riscritture; esitazioni, ripetizioni, troncate e false partenze non contano. **sost.** = sostituzioni in % delle parole: il segnale diretto di reinterpretazione.
- **WER letterale**: tolte solo le esitazioni; ripetizioni e troncate contano.
- **RTF**: tempo di elaborazione / durata dell'audio, sul Mac (M4 Pro).
- **Riproducibilità**: seme casuale MLX fisso (0). Il temperature fallback di Whisper campiona a caso: senza seme due run dello stesso sistema danno numeri diversi.
- **Riferimenti silver**: parole verificate da una persona, esitazioni in gran parte proposte da Whisper large-v3-turbo. Le metriche sulle esitazioni sono ottimistiche per le varianti di turbo, soprattutto con prompt.
- **Ancoraggio**: i riferimenti partono dalla bozza di large-v3-turbo; i sistemi turbo sono avvantaggiati rispetto agli altri modelli.
- Con pochi riferimenti gli intervalli sono larghi: differenze dentro gli intervalli non sono significative.
