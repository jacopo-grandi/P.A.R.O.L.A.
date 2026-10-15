# Verifica all'ascolto delle inserzioni di CrisperWhisper — 2026-10-15

**Domanda.** CrisperWhisper 2.0 turbo ha un WER letterale del 12,8% sui riferimenti silver (it-002, en-002), contro il 3,5% di Whisper turbo. Di questo 12,8%, 507 errori su 755 sono **inserzioni**: parole scritte da CrisperWhisper e assenti dal riferimento. I riferimenti partono dalla bozza di turbo. Le inserzioni sono parole inventate o parlato vero che i riferimenti hanno perso?

**Metodo.** `ilat audit build --system crisper-turbo-lang`: 30 inserzioni estratte a caso con seme 0, per categoria. Per ognuna una clip di circa 4 s; Jacopo le ha ascoltate tutte e ha segnato "vero" (detta davvero) o "falso" (inventata).

## Risultato

| Categoria | vero | falso | % vero |
|---|---|---|---|
| ripetizioni ("to to", "we we") | 10 | 0 | 100% |
| troncate ("m-", "li-") | 6 | 0 | 100% |
| esitazioni ("uh", "eh") | 6 | 2 | 75% |
| altre parole | 6 | 0 | 100% |
| **totale** | **28** | **2** | **93%** |

Tutte le 22 inserzioni non di esitazione (quelle che contano nel WER letterale) erano parlato vero. Con 22 casi su 22, la quota vera è almeno l'87% al 95% di confidenza (regola del tre).

## Cosa cambia

Se le 507 inserzioni sono vere tra l'87% e il 100%, i riferimenti silver **mancano di 440–510 parole effettivamente dette** (circa l'8%: ripetizioni, false partenze, troncate). Corretti i riferimenti, il WER letterale stimato diventa:

| Sistema | WER letterale sui silver | stima con riferimenti corretti |
|---|---|---|
| Whisper large-v3-turbo | 3,5% | **10–11%** |
| CrisperWhisper 2.0 turbo | 12,8% | **4–5%** |

La classifica **si ribalta**. Turbo sembrava il migliore perché i riferimenti sono stati costruiti a partire dalla sua bozza e ne hanno ereditato i tagli: è l'ancoraggio previsto, e la verifica ne misura la dimensione. La stima assume che turbo non contenga quelle parole, ed è così per costruzione: i riferimenti nascono dalla sua bozza.

## Conseguenze

1. **I riferimenti silver non sono letterali.** Vanno bene per il lessico, ma mancano di gran parte delle ripetizioni e delle false partenze. Per le metriche servono riferimenti costruiti all'ascolto.
2. **Le bozze per en-001 e it-001 conviene farle con CrisperWhisper**, non con turbo: sono già vicine al verbatim e richiedono meno correzioni. Resta l'ancoraggio, ma a favore del parlato vero.
3. **CrisperWhisper è già vicino all'obiettivo del progetto**, anche in italiano. La sua licenza però è non commerciale: va bene per uso personale e ricerca, non per l'app sulle call di lavoro. Il fine-tuning (Fasi 3–5) resta utile per avere un modello con licenza libera.
