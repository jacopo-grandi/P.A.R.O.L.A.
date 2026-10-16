# Riconoscimento di chi parla con sherpa-onnx — prova leggera, 2026-10-16

**Domanda.** Quanto sbaglia sherpa-onnx (segmentazione pyannote 3.0 + modello di voce WeSpeaker VoxCeleb ResNet34-LM + raggruppamento semplice) nel dire chi parla, prima di usarlo nell'app?

**Dati.** Due riunioni del set di test AMI (IS1009a, 14 min; ES2004a, 17,5 min; 4 persone ciascuna, audio Mix-Headset), con i riferimenti `only_words` di pyannote/AMI-diarization-setup. AMI è sotto CC BY 4.0, i riferimenti sotto Apache-2.0.

**Metrica.** DER (diarization error rate) su frame da 10 ms, senza tolleranza ai bordi, con le sovrapposizioni incluse: tempo perso + inventato + attribuito alla persona sbagliata, diviso il tempo di parlato del riferimento (`parola.eval.diarization`, con test costruiti a mano). È lo stesso modo in cui pyannote riporta i suoi numeri.

**Risultati** (sherpa-onnx 1.13.8, 4 thread sulla CPU di un M4 Pro, circa 100 s per 31,5 min di audio).

| Configurazione | DER | IS1009a | ES2004a | Voci trovate (IS / ES) |
|---|---|---|---|---|
| soglia 0,5 (predefinita) | 61,2% | 51,3% | 68,7% | 16 / 67 |
| soglia 0,7 | 46,7% | 47,2% | 46,3% | 7 / 38 |
| soglia 0,8 | 39,6% | 49,1% | 32,4% | 3 / 20 |
| soglia 0,9 | 33,8% | 42,4% | 27,2% | 2 / 12 |
| 4 voci date (oracolo) | 36,3% | 43,1% | 31,2% | 4 / 4 |

Il parlato perso (7–12%) e quello inventato (4–7%) sono nella norma. Quasi tutto l'errore è **voce attribuita alla persona sbagliata** (11–52%). Per confronto, pyannote dichiara il 18,8% su AMI (IHM) con la pipeline 3.1, che usa la stessa segmentazione e lo stesso modello di voce, e il 17,0% con community-1: la differenza sta nel raggruppamento delle voci.

**Sulla riunione vera** (canale "Altri" della riunione di prova, 30 min): soglia 0,5 → 11 voci, 0,7 → 4, 0,9 → 2. Senza un riferimento non si sa quale sia giusto. Memoria: 0,55 GB di picco. Tempo: circa 2 minuti.

**Cosa vuol dire.** Così com'è, sherpa-onnx confonde troppo le voci per l'app: una battuta su tre andrebbe all'interlocutore sbagliato. Il modello di voce e la segmentazione non sembrano il problema, perché sono gli stessi di pyannote. Il problema è il raggruppamento.

**Limiti.** Solo due riunioni (31,5 min), in inglese, registrate in sala nel 2005: nessun audio di Meet e niente italiano.
