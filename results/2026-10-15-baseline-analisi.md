# Baseline del 2026-10-15 — analisi

Riferimenti: it-002 (16 min) ed en-002 (29 min), entrambi `silver`. Report completi: [seme 0](2026-10-15-baseline.md), [seme 1](2026-10-15-baseline-seed1.md), [seme 2](2026-10-15-baseline-seed2.md).

## WER letterale (metrica principale) al variare del seme

I semi 0–2 sono calcolati con la normalizzazione finale (`okay` = `ok`); la colonna "senza seme" con quella precedente.

| Sistema | Lingua | senza seme | seme 0 | seme 1 | seme 2 |
|---|---|---|---|---|---|
| `turbo` | it | 2,0 | 2,0 | 2,0 | 2,0 |
| `turbo` | en | 3,2 | 4,5 | 4,7 | 6,6 |
| `turbo-prompt` | it | 7,8 | 7,8 | 7,8 | 7,8 |
| `turbo-prompt` | en | 3,2 | 5,6 | 3,4 | 4,7 |
| `large-v3-lang` | tutte | 19,1 | 25,4 | — | — |

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

## Parakeet v3 e CrisperWhisper 2.0 turbo (seme 0)

| Sistema | WER letterale IT | WER letterale EN | Esitazioni conservate | Esitazioni "inventate" | RTF |
|---|---|---|---|---|---|
| `turbo` | 2,0 | 4,5 | 2/352 | 0 | 0,047 |
| `parakeet-v3` | 16,9 | 14,7 | 252/352 (IT 0%) | 95 | **0,013** |
| `crisper-turbo-lang` | 15,5 | 11,0 | **322/352** | 157 | 0,16 |

7. **CrisperWhisper è l'unico che conserva le esitazioni** (92%, in italiano 94%, nonostante sia nato per EN/DE). Il suo WER letterale alto è fatto soprattutto di **inserzioni**: 507 su 759 errori. Tra queste, **181 ripetono una parola vicina** ("sì sì", "the the") e **31 sono troncate** ("th-"). Quasi certamente molte sono **parlato vero mancante nei riferimenti**: i riferimenti silver partono dalla bozza di turbo, che toglie ripetizioni e false partenze. Anche gran parte delle 157 esitazioni "inventate" può essere vera, perché le esitazioni dei riferimenti sono incomplete per costruzione. Fino a una verifica all'ascolto, **i numeri di CrisperWhisper sono pessimistici e quelli di turbo ottimistici**.
8. **Parakeet riscrive l'italiano:** "però" → "tuttavia" (6 volte), "concentrerei" → "concentrare". È la reinterpretazione che la decisione 0007 vuole evitare, e in italiano toglie tutte le esitazioni. In inglese le conserva (83%). È di gran lunga il più veloce: un'ora in meno di un minuto.
9. **Normalizzazione:** `okay`/`ok`, `perchè`/`perché` e simili ora valgono come la stessa parola (convenzioni §2.9).

## Verifica all'ascolto (aggiornamento)

La verifica di 30 inserzioni di CrisperWhisper ([2026-10-15-audit-crisper.md](2026-10-15-audit-crisper.md)) dà il **93% di parlato vero**, e il 100% sulle 22 non di esitazione. I riferimenti silver mancano di circa l'8% delle parole dette. Con riferimenti corretti, le stime sono **CrisperWhisper circa 4–5% e turbo circa 10–11%** di WER letterale: la classifica di questa pagina si ribalta.

## Prossimi passi

- **Verificare l'ancoraggio all'ascolto:** un campione delle inserzioni di CrisperWhisper (ripetizioni, troncate, esitazioni), con clip audio. Se sono vere, i riferimenti vanno corretti in quei punti, e CrisperWhisper diventa la base migliore da cui partire (bozze e fine-tuning). Attenzione però alla sua licenza non commerciale.
- Completare il test set (en-001, it-001) e rilanciare con 3 semi.
- Ascoltare a campione le inserzioni di `turbo-prompt` su it-002.
