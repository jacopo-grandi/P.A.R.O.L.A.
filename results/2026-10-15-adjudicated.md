# Baseline — 2026-10-15

Commit `3644324`. Generato da `ilat eval`. Valori in %, tra parentesi l'intervallo di confidenza al 95% (bootstrap sui segmenti).

**Riferimenti** (2 file, 0.76 h): it-002 (it, 17 min, adjudicated), en-002 (en, 29 min, adjudicated).

## Sistemi

- `turbo`: large-v3-turbo, language detected
- `turbo-prompt`: large-v3-turbo, language detected, disfluency prompt
- `crisper-turbo-lang`: CrisperWhisper 2.0 turbo, verbatim mode, language forced (non-commercial weights)
- `parakeet-v3`: Parakeet TDT 0.6B v3 (MLX), language detected
- `large-v3-lang`: large-v3, language forced

## Risultati

| Sistema | Ambito | **WER di fedeltà** | sost. | WER letterale | WER verbatim | Filler recall | Filler precision | RTF |
|---|---|---|---|---|---|---|---|---|
| `turbo` | all | **5.1 [4.3-6.0]** | 1.9 | 8.1 [7.1-9.3] | 14.4 [12.9-16.0] | 0.4 | 100.0 | 0.047 |
| `turbo` | lang:en | **5.3 [4.3-6.5]** | 1.6 | 8.2 [6.7-9.8] | 16.5 [14.4-18.7] | 0.0 | — | 0.048 |
| `turbo` | lang:it | **4.8 [3.6-6.3]** | 2.5 | 8.0 [6.5-9.7] | 10.9 [9.3-12.6] | 2.4 | 100.0 | 0.046 |
| `turbo` | it-002 | **4.8 [3.6-6.3]** | 2.5 | 8.0 [6.5-9.7] | 10.9 [9.3-12.6] | 2.4 | 100.0 | 0.046 |
| `turbo` | en-002 | **5.3 [4.3-6.5]** | 1.6 | 8.2 [6.7-9.8] | 16.5 [14.4-18.7] | 0.0 | — | 0.048 |
| `turbo-prompt` | all | **7.8 [6.3-9.8]** | 2.9 | 10.5 [8.9-12.6] | 16.4 [14.5-18.6] | 1.9 | 90.0 | 0.049 |
| `turbo-prompt` | lang:en | **8.2 [6.0-11.0]** | 3.0 | 10.9 [8.4-13.8] | 18.8 [16.0-22.0] | 0.0 | — | 0.051 |
| `turbo-prompt` | lang:it | **7.2 [5.6-9.2]** | 2.8 | 9.9 [8.2-11.9] | 12.4 [10.8-14.4] | 10.7 | 90.0 | 0.046 |
| `turbo-prompt` | it-002 | **7.2 [5.6-9.2]** | 2.8 | 9.9 [8.2-11.9] | 12.4 [10.8-14.4] | 10.7 | 90.0 | 0.046 |
| `turbo-prompt` | en-002 | **8.2 [6.0-11.0]** | 3.0 | 10.9 [8.4-13.8] | 18.8 [16.0-22.0] | 0.0 | — | 0.051 |
| `crisper-turbo-lang` | all | **5.0 [4.0-6.1]** | 1.9 | 5.3 [4.3-6.6] | 5.8 [4.8-7.1] | 96.1 | 93.5 | 0.159 |
| `crisper-turbo-lang` | lang:en | **2.7 [2.0-3.6]** | 1.2 | 2.9 [2.1-4.1] | 3.4 [2.5-4.5] | 96.1 | 96.1 | 0.146 |
| `crisper-turbo-lang` | lang:it | **8.5 [6.4-10.7]** | 3.0 | 9.0 [6.9-11.2] | 9.8 [7.5-12.0] | 96.4 | 83.5 | 0.183 |
| `crisper-turbo-lang` | it-002 | **8.5 [6.4-10.7]** | 3.0 | 9.0 [6.9-11.2] | 9.8 [7.5-12.0] | 96.4 | 83.5 | 0.183 |
| `crisper-turbo-lang` | en-002 | **2.7 [2.0-3.6]** | 1.2 | 2.9 [2.1-4.1] | 3.4 [2.5-4.5] | 96.1 | 96.1 | 0.146 |
| `parakeet-v3` | all | **12.7 [11.3-14.2]** | 4.9 | 14.5 [13.0-16.1] | 16.1 [14.6-17.6] | 67.6 | 90.8 | 0.013 |
| `parakeet-v3` | lang:en | **10.1 [8.7-11.7]** | 3.8 | 10.8 [9.4-12.4] | 12.2 [10.8-13.7] | 82.5 | 90.8 | 0.012 |
| `parakeet-v3` | lang:it | **16.7 [14.3-19.0]** | 6.5 | 20.1 [17.6-22.5] | 22.4 [20.1-24.7] | 0.0 | — | 0.014 |
| `parakeet-v3` | it-002 | **16.7 [14.3-19.0]** | 6.5 | 20.1 [17.6-22.5] | 22.4 [20.1-24.7] | 0.0 | — | 0.014 |
| `parakeet-v3` | en-002 | **10.1 [8.7-11.7]** | 3.8 | 10.8 [9.4-12.4] | 12.2 [10.8-13.7] | 82.5 | 90.8 | 0.012 |
| `large-v3-lang` | all | **23.9 [15.8-35.0]** | 4.6 | 26.0 [18.2-36.8] | 29.8 [22.5-40.5] | 15.0 | 93.3 | 0.138 |
| `large-v3-lang` | lang:en | **21.9 [12.5-38.1]** | 3.4 | 23.8 [14.6-39.5] | 28.7 [20.3-43.2] | 18.1 | 95.8 | 0.141 |
| `large-v3-lang` | lang:it | **27.2 [16.3-42.3]** | 6.5 | 29.5 [18.8-44.0] | 31.6 [21.3-45.9] | 1.2 | 33.3 | 0.134 |
| `large-v3-lang` | it-002 | **27.2 [16.3-42.3]** | 6.5 | 29.5 [18.8-44.0] | 31.6 [21.3-45.9] | 1.2 | 33.3 | 0.134 |
| `large-v3-lang` | en-002 | **21.9 [12.5-38.1]** | 3.4 | 23.8 [14.6-39.5] | 28.7 [20.3-43.2] | 18.1 | 95.8 | 0.141 |

## Disfluenze conservate (tutti i file)

| Sistema | filler | truncated | repetition | false_start | edit_term | filler inventati |
|---|---|---|---|---|---|---|
| `turbo` | 2/466 | 0/49 | 0/0 | 0/0 | 0/0 | 0 |
| `turbo-prompt` | 9/466 | 0/49 | 0/0 | 0/0 | 0/0 | 1 |
| `crisper-turbo-lang` | 448/466 | 48/49 | 0/0 | 0/0 | 0/0 | 31 |
| `parakeet-v3` | 315/466 | 0/49 | 0/0 | 0/0 | 0/0 | 32 |
| `large-v3-lang` | 70/466 | 0/49 | 0/0 | 0/0 | 0/0 | 5 |

## Come leggere i numeri

- **WER di fedeltà** è la metrica principale (decisione 0010): conta se le parole sono quelle dette, senza riscritture; esitazioni, ripetizioni, troncate e false partenze non contano. **sost.** = sostituzioni in % delle parole: il segnale diretto di reinterpretazione.
- **WER letterale**: tolte solo le esitazioni; ripetizioni e troncate contano.
- **RTF**: tempo di elaborazione / durata dell'audio, sul Mac (M4 Pro).
- **Riproducibilità**: seme casuale MLX fisso (0). Il temperature fallback di Whisper campiona a caso: senza seme due run dello stesso sistema danno numeri diversi.
- **Riferimenti silver**: parole verificate da una persona, esitazioni in gran parte proposte da Whisper large-v3-turbo. Le metriche sulle esitazioni sono ottimistiche per le varianti di turbo, soprattutto con prompt.
- **Ancoraggio**: i riferimenti partono dalla bozza di large-v3-turbo; i sistemi turbo sono avvantaggiati rispetto agli altri modelli.
- Con pochi riferimenti gli intervalli sono larghi: differenze dentro gli intervalli non sono significative.
