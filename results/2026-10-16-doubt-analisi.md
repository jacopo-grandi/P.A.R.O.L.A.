# Punti dubbi: quale seconda trascrizione segnala meglio gli errori di turbo — 2026-10-16

**Domanda.** Se trascriviamo ogni call anche con un secondo sistema e segnaliamo le parole di Whisper turbo che il secondo non conferma, quanti errori di turbo intercettiamo, e quanto bisogna ricontrollare?

**Metodo** (`ilat.doubt`).
- Turbo, il motore predefinito, e la seconda trascrizione si allineano sui token di fedeltà, cioè senza esitazioni e ripetizioni ([0010](../docs/decisions/0010-fidelity-metric.md)). Una parola di turbo è segnalata se la seconda la sostituisce o non ce l'ha, o se la seconda ha parole in più proprio lì accanto.
- Gli errori di turbo si calcolano allo stesso modo contro i riferimenti `adjudicated` di it-002 ed en-002: 374 parole con errore su 5761, cioè il **6,5%**. Segnalando parole a caso, la precisione sarebbe proprio il 6,5%.
- Finestra 1 = si segnala anche una parola prima e una dopo, come farebbe un'evidenziazione nell'interfaccia.

## Risultati

| Seconda opinione | Licenza | Errori di turbo intercettati (IT / EN) | Segnalazioni corrette | Parole da ricontrollare |
|---|---|---|---|---|
| turbo, altro seme | MIT | 2–29% (IT 0%) | 48–53% | 0,3–4% |
| turbo con prompt | MIT | 40% (50% / 33%) | 38% | 6,9% |
| **Parakeet v3** | **CC BY** | **66%** (65% / 66%) | **35%** | **12,4%** |
| large-v3 | MIT | 57% | 25% | 14,7% |
| Parakeet ∪ turbo con prompt | libere | **79%** (78% / 79%) | 31% | 16,3% |
| CrisperWhisper (*) | non commerciale | 84% | 59% | 9,3% |

Con finestra 1, Parakeet intercetta il 77% degli errori (precisione 20%, 25% delle parole), e Parakeet ∪ turbo con prompt l'86% (31% delle parole).

(*) **CrisperWhisper è avvantaggiato per costruzione:** i riferimenti sono nati proprio dalle divergenze tra riferimento e CrisperWhisper. I numeri di Parakeet e di turbo con prompt invece sono equi: quei sistemi non sono intervenuti nella costruzione dei riferimenti.

## Cosa vuol dire

1. **Parakeet è la seconda opinione giusta per l'uso predefinito.** Ha licenza libera, è velocissimo (circa 1 minuto per un'ora di audio, quasi nulla in più rispetto a turbo) e, ricontrollando il 12% delle parole, intercetta due errori di turbo su tre. Le sue segnalazioni sono corrette 5 volte più spesso di quelle fatte a caso (35% contro 6,5%). Che come trascrittore sia peggiore di turbo, e che riscriva l'italiano, qui è un vantaggio: sbaglia in punti diversi da turbo.
2. **Un altro seme di turbo non serve:** in italiano turbo è deterministico, quindi due semi danno lo stesso testo e nessuna segnalazione.
3. **Aggiungere turbo con prompt** porta gli errori intercettati al 79%, ma raddoppia il tempo di trascrizione. È un'opzione per le call importanti.
4. **Circa un terzo degli errori di turbo resta invisibile:** sono i punti in cui anche la seconda opinione sbaglia allo stesso modo. Lo stesso vale per gli errori comuni a turbo e al riferimento, che questa misura non può vedere.

## Limiti

- Due file (45 minuti), riferimenti `adjudicated` costruiti a partire da turbo e CrisperWhisper.
- I numeri dipendono dalla definizione di errore: si contano solo i token di fedeltà, per cui esitazioni e ripetizioni non contano.
