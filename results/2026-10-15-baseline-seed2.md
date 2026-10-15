# Baseline — 2026-10-15

Commit `0561d18`. Generato da `ilat eval`. Valori in %, tra parentesi l'intervallo di confidenza al 95% (bootstrap sui segmenti).

**Riferimenti** (2 file, 0.76 h): it-002 (it, 17 min, silver), en-002 (en, 29 min, silver).

## Sistemi

- `turbo`: large-v3-turbo, language detected
- `turbo-prompt`: large-v3-turbo, language detected, disfluency prompt

## Risultati

| Sistema | Ambito | **WER di fedeltà** | sost. | WER letterale | WER verbatim | Filler recall | Filler precision | RTF |
|---|---|---|---|---|---|---|---|---|
| `turbo` | all | **4.4 [2.9-6.5]** | 2.0 | 4.8 [3.1-6.9] | 9.3 [7.6-11.3] | 13.9 | 87.5 | 0.048 |
| `turbo` | lang:en | **6.0 [3.4-9.4]** | 2.4 | 6.6 [3.9-10.1] | 12.8 [10.3-15.9] | 15.4 | 87.0 | 0.049 |
| `turbo` | lang:it | **2.0 [1.2-2.9]** | 1.3 | 2.0 [1.2-2.9] | 3.7 [2.8-4.8] | 4.3 | 100.0 | 0.046 |
| `turbo` | it-002 | **2.0 [1.2-2.9]** | 1.3 | 2.0 [1.2-2.9] | 3.7 [2.8-4.8] | 4.3 | 100.0 | 0.046 |
| `turbo` | en-002 | **6.0 [3.4-9.4]** | 2.4 | 6.6 [3.9-10.1] | 12.8 [10.3-15.9] | 15.4 | 87.0 | 0.049 |
| `turbo-prompt` | all | **5.4 [4.4-6.5]** | 2.0 | 6.0 [4.9-7.2] | 11.0 [9.9-12.2] | 2.3 | 80.0 | 0.050 |
| `turbo-prompt` | lang:en | **4.5 [3.4-5.9]** | 1.6 | 4.7 [3.5-6.3] | 12.1 [10.7-13.8] | 0.0 | — | 0.053 |
| `turbo-prompt` | lang:it | **6.8 [5.2-8.6]** | 2.6 | 7.8 [6.2-9.7] | 9.2 [7.6-11.0] | 17.0 | 80.0 | 0.046 |
| `turbo-prompt` | it-002 | **6.8 [5.2-8.6]** | 2.6 | 7.8 [6.2-9.7] | 9.2 [7.6-11.0] | 17.0 | 80.0 | 0.046 |
| `turbo-prompt` | en-002 | **4.5 [3.4-5.9]** | 1.6 | 4.7 [3.5-6.3] | 12.1 [10.7-13.8] | 0.0 | — | 0.053 |

## Disfluenze conservate (tutti i file)

| Sistema | filler | truncated | repetition | false_start | edit_term | filler inventati |
|---|---|---|---|---|---|---|
| `turbo` | 49/352 | 0/1 | 0/0 | 0/0 | 0/0 | 7 |
| `turbo-prompt` | 8/352 | 0/1 | 0/0 | 0/0 | 0/0 | 2 |

## Come leggere i numeri

- **WER di fedeltà** è la metrica principale (decisione 0010): conta se le parole sono quelle dette, senza riscritture; esitazioni, ripetizioni, troncate e false partenze non contano. **sost.** = sostituzioni in % delle parole: il segnale diretto di reinterpretazione.
- **WER letterale**: tolte solo le esitazioni; ripetizioni e troncate contano.
- **RTF**: tempo di elaborazione / durata dell'audio, sul Mac (M4 Pro).
- **Riproducibilità**: seme casuale MLX fisso (0). Il temperature fallback di Whisper campiona a caso: senza seme due run dello stesso sistema danno numeri diversi.
- **Riferimenti silver**: parole verificate da una persona, esitazioni in gran parte proposte da Whisper large-v3-turbo. Le metriche sulle esitazioni sono ottimistiche per le varianti di turbo, soprattutto con prompt.
- **Ancoraggio**: i riferimenti partono dalla bozza di large-v3-turbo; i sistemi turbo sono avvantaggiati rispetto agli altri modelli.
- Con pochi riferimenti gli intervalli sono larghi: differenze dentro gli intervalli non sono significative.
