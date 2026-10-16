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

## Raggruppamento migliore sopra sherpa-onnx

**Metodo.** I pezzi di sherpa-onnx (soglia 0,5: tanti pezzi piccoli) vengono rianalizzati: ognuno è diviso in finestre, ogni finestra riceve un'impronta vocale (lo stesso WeSpeaker), e le impronte sono raggruppate con un clustering spettrale. Il numero di voci è stimato dal salto più grande tra gli autovalori (NME-SC, come in NeMo). Ogni pezzo prende la voce più frequente tra le sue finestre. Il prototipo è fuori dal progetto: solo numpy e scipy, nessuna dipendenza nuova.

| Configurazione | DER | IS1009a | ES2004a | Voci trovate (IS / ES) |
|---|---|---|---|---|
| sherpa-onnx, soglia 0,7 | 46,7% | 47,2% | 46,3% | 7 / 38 |
| sherpa-onnx, 4 voci date (oracolo) | 36,3% | 43,1% | 31,2% | 4 / 4 |
| **spettrale, finestre 3 s (passo 1,5)** | **30,0%** | 33,7% | 27,2% | 5 / 5 |
| spettrale, finestre 2 s (passo 1) | 31,9% | 34,5% | 30,0% | 4 / 5 |
| spettrale, ogni finestra decide (3 s) | 34,1% | 42,1% | 28,2% | 5 / 5 |
| spettrale, ogni finestra decide (1,5 s) | 39,0% | 44,3% | 35,1% | 4 / 5 |

L'errore scende dal 47% al 30%, e il numero di voci diventa quasi giusto: 4–5 per riunioni con 4 persone. Restano due componenti dell'errore. Le voci scambiate (10–18%) e il parlato perso o inventato (11–19%), che viene dalla segmentazione e non dal raggruppamento.

**Confronto con pyannote.** Il 17–19% di pyannote è misurato su tutte le 16 riunioni del set di test AMI, non su queste due: non è un confronto alla pari. IS1009a sembra la più difficile delle due. Per sapere quanto manca davvero, pyannote andrebbe misurato su queste stesse due riunioni.

**Limiti.** Sei configurazioni provate sulle stesse due riunioni (31,5 min): i parametri migliori potrebbero non valere altrove.
