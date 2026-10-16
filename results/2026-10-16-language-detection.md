# Rilevamento della lingua — 2026-10-16

**Perché.** en-001 (un'ora in inglese, chi parla è italiano) importata con lingua "Auto" è uscita in italiano: Whisper l'ha tradotta e storpiata per un'ora intera ("Il più famoso algoritmo di clustering…"), quasi ogni riga segnata come dubbia. La lingua veniva decisa una volta sola, sui primi 30 s di parlato incollati insieme (i tratti con suono dati dal VAD).

**Come.** Probabilità di lingua di Whisper large-v3-turbo (`mlx_whisper.decoding.detect_language`, fp16) sui 4 file del test set, con tre metodi:

1. **incollato** (il metodo di prima): i tratti con suono dei primi 30 s di parlato, concatenati;
2. **primi 30 s** così come sono (il comportamento predefinito di Whisper);
3. **5 finestre**: 30 s di audio così com'è a partire da 5 tratti con suono presi a distanza regolare nell'elenco, probabilità mediate, solo tra `it` ed `en`.

**Risultati.**

| File | Lingua | Incollato | Primi 30 s | 5 finestre (ognuna) |
|---|---|---|---|---|
| it-001 | it | it (it 1,00) | it (it 1,00) | it (it 1,00): it it it it it |
| it-002 | it | it (it 1,00) | it (it 1,00) | it (it 1,00): it it it it it |
| en-001 | en | **it** (it 0,50, en 0,43) | en (en 0,92) | en (en 0,95): en en en en en |
| en-002 | en | en (en 1,00) | en (en 0,48, it 0,00) | en (en 0,76): en en en en en |

Su en-001 le finestre di audio grezzo dicono inglese ovunque (0,86–1,00 su 14 finestre da 0 a 3521 s), tranne quella a 30 s (en 0,55, it 0,39). L'incollato sposta la decisione sull'italiano: i pezzi brevi uniti sembrano contare più l'accento che la lingua.

**Scelta.** 5 finestre (decisione [0030](../docs/decisions/0030-language-from-windows-and-asked-on-import.md)): 4 su 4, sempre con margine. Il modulo finale (`parola.asr.language.detect`), provato sugli stessi 4 file, dà 4 su 4. Su it-002 ed en-002, i due file con riferimento, la lingua scelta non cambia, quindi i WER misurati restano quelli di `results/2026-10-15-vad.md`.

**Limiti.** Quattro file sono pochi; manca un file misto IT/EN in cui la lingua prevalente sia incerta. Costo misurato su en-001: 1,9 s (lettura dell'audio compresa, modello già caricato) su un M4 Pro, contro circa 7 minuti di trascrizione.
