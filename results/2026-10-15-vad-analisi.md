# Rilevamento della voce (VAD) prima di Whisper — 2026-10-15

**Problema.** Nella prima registrazione di prova (`ilat record`, 15 s) il canale "Altri" aveva 9,6 s di silenzio e poi uno spot. Whisper turbo ha scritto "Grazie a tutti." su tutti i 15 secondi: una frase inventata. Ha anche scelto la lingua sulla finestra iniziale, quasi tutta silenzio. In una call ogni canale è spesso in silenzio mentre parla l'altro, quindi il problema è strutturale.

**Metodo.** Ogni variante è un sistema `turbo-vad` in `ilat eval`, sui riferimenti `adjudicated` (it-002, en-002), e viene provata anche sulla registrazione di prova. Un rilevatore di livello (`ilat.audio.vad`) trova i tratti con suono. Copre 912 s contro 891 s di parlato nel riferimento di it-002, e 1633 s contro 1606 in en-002: non taglia parlato.

| Variante | WER di fedeltà (tutti) | it-002 | en-002 | "Grazie a tutti" nella prova |
|---|---|---|---|---|
| turbo senza VAD | **5,1** | 4,8 | 5,3 | sì |
| v1: solo i tratti con suono (`clip_timestamps`, 106–108 spezzoni) | 27,9 | 15,8 | 35,6 | no |
| v2: lingua sul parlato + `hallucination_silence_threshold` | 8,1 | 8,0 | 8,2 | — |
| v3: lingua sul parlato + scarto dei segmenti con poco suono | 5,2 | 5,0 | 5,3 | sì |
| v4: ogni blocco di suono (≤ 28 s) decodificato da solo | 10,2 | 10,8 | 9,8 | no |
| v5: tratti separati solo da silenzi ≥ 3 s | 8,7 | 9,5 | 8,2 | no |
| v6: decodifica dal primo suono (+ filtro) | 8,3 | **12,9** | 5,3 | no |
| **v7: lingua sul parlato + scarto dei segmenti senza parole sul suono** | **5,1** | 4,9 | 5,3 | sì |

## Cosa abbiamo imparato

1. **Whisper è fragile all'allineamento delle finestre.** In v6 l'unica differenza su it-002 è che la decodifica parte 4 secondi più tardi: Whisper salta un centinaio di parole vere (fino a 49 in un solo segmento) e la fedeltà passa da 4,8% a 12,9%. Su en-002 la stessa modifica non cambia nulla. Quindi ogni variante che sposta le finestre (v1, v4, v5, v6) è a rischio, e su un singolo file le differenze di qualche punto possono essere dovute al caso. Oltre ai semi, anche l'allineamento conta come fonte di variabilità.
2. **Il filtro va fatto sulle parole, non sulla durata del segmento.** Scartare i segmenti con poca quota di suono toglieva segmenti lunghi con poche parole vere. Il criterio "nessuna parola sul suono" è sicuro.
3. **Il rilevamento della lingua sul parlato è innocuo sul test set**, dove la lingua era già giusta. Serve quando un canale inizia con silenzio o musica.
4. **"Grazie a tutti" nella prova non sparisce con v7**, perché Whisper allinea le parole inventate sopra lo spot (suono vero). Per toglierla bisogna spostare la decodifica, ed è quello che rompe it-002.

## Scelta

- **`ilat record` usa v7** (`MLXWhisperBackend(vad=True)`): neutro sul test set, scarta i canali muti e i segmenti scritti sul silenzio, sceglie la lingua sul parlato.
- **Le frasi inventate sopra suono vero non sono risolte.** Da affrontare con la segnalazione dei punti dubbi, cioè due trascrizioni a confronto (vedi PLAN), non con altri ritocchi della decodifica.
