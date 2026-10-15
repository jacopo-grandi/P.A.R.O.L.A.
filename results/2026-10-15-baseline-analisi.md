# Baseline del 2026-10-15 — analisi

Riferimenti: it-002 (16 min) ed en-002 (29 min), entrambi `silver`. Report completi: [seme 0](2026-10-15-baseline.md), [seme 1](2026-10-15-baseline-seed1.md), [seme 2](2026-10-15-baseline-seed2.md).

## WER letterale (metrica principale) al variare del seme

| Sistema | Lingua | senza seme | seme 0 | seme 1 | seme 2 |
|---|---|---|---|---|---|
| `turbo` | it | 2,0 | 2,0 | 2,0 | 2,0 |
| `turbo` | en | 3,2 | 4,7 | 4,9 | 6,8 |
| `turbo-prompt` | it | 7,8 | 7,8 | 7,8 | 7,8 |
| `turbo-prompt` | en | 3,2 | 5,8 | 3,5 | 4,9 |
| `large-v3-lang` | tutte | 19,1 | 25,5 | — | — |

## Cosa dicono i numeri

1. **turbo senza prompt è il migliore.** WER letterale circa 2% in italiano, tra 3% e 7% in inglese a seconda del seme, RTF circa 0,05 (un'ora di audio in circa 3 minuti sul Mac).
2. **Forzare la lingua non cambia nulla:** `turbo` e `turbo-lang` danno un output identico, parola per parola, perché il rilevamento della lingua era già corretto. Sui file misti IT/EN potrebbe essere diverso.
3. **Il prompt con disfluenze peggiora l'italiano** (dal 2,0% al 7,8%, stabile su tutti i semi, intervalli che non si sovrappongono). Gli errori aggiunti sono soprattutto **inserzioni**: testo che il riferimento non ha. Può essere testo inventato, oppure parlato vero che il riferimento ha perso, perché il riferimento parte dalla bozza di turbo **senza** prompt. Va controllato ascoltando, per esempio it-002 a 408–414 s. In inglese l'effetto sta dentro la variabilità tra semi.
4. **Whisper toglie quasi tutte le esitazioni:** turbo ne conserva 2 su 352 (0,6%), con il prompt 8 su 352. Il prompt non è una soluzione. Conferma l'obiettivo del progetto: il fine-tuning serve per le esitazioni, non per le parole.
5. **large-v3 è molto peggio di turbo:** genera loop allucinati nei tratti di silenzio o rumore (fino a 138 parole inventate in un segmento di 2 s), ed è circa 3 volte più lento.
6. **L'inglese dipende dal caso.** Quando la decodifica fallisce, Whisper ricampiona con temperatura più alta: lo stesso sistema varia di circa ±1,5 punti tra un seme e l'altro. L'italiano su it-002 invece è stabile. Gli intervalli bootstrap non includono questa variabilità: per confrontare sistemi in inglese servono più semi.

## Limiti

- **Due file, entrambi silver**, quindi intervalli larghi.
- **Ancoraggio:** i riferimenti partono dalla bozza di turbo (seme non fissato), e chi corregge tende a confermarla. Turbo è avvantaggiato rispetto a qualsiasi altro sistema, anche contro se stesso con il prompt.
- **Esitazioni dei riferimenti** proposte in gran parte da turbo con varie finestre e prompt e verificate a campione: la filler recall è ottimistica per le varianti di turbo.
- Su en-002 la ripetizione finale "Bye-bye" del riferimento potrebbe essere un loop di Whisper confermato nella revisione.

## Prossimi passi

- Completare il test set (en-001, it-001) e rilanciare con 3 semi.
- Adattatori per **CrisperWhisper** (verbatim per costruzione) e **Parakeet v3**: è il confronto più interessante, ma servono torch o NeMo, da approvare.
- Ascoltare a campione le inserzioni di `turbo-prompt` su it-002, per capire quanto pesa l'ancoraggio.
