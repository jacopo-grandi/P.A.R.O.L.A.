# Confronto sui riferimenti `adjudicated` — 2026-10-15

Riferimenti: it-002 (16 min) ed en-002 (29 min), `adjudicated`. Ogni divergenza tra il riferimento silver e CrisperWhisper è stata decisa all'ascolto da Jacopo, oppure dalla regola automatica per ripetizioni, troncate ed esitazioni, verificata a campione. Report completi: [seme 0](2026-10-15-adjudicated.md), [seme 1](2026-10-15-adjudicated-seed1.md), [seme 2](2026-10-15-adjudicated-seed2.md).

## WER di fedeltà (metrica principale, decisione 0010)

| Sistema | IT | EN | sostituzioni IT / EN | WER letterale (tutti) | esitazioni conservate |
|---|---|---|---|---|---|
| Whisper turbo | **4,8** [3,6–6,3] | 5,3 [4,3–6,5] (semi 1–2: 5,4 / 7,9) | 2,5 / 1,6 | 8,1 | 2/466 |
| turbo con prompt | 7,2 | 8,2 (semi: 5,5 / 5,9) | 2,8 / 3,0 | 10,5 | 9/466 |
| **CrisperWhisper 2.0 turbo** | 8,5 [6,4–10,7] | **2,7** [2,0–3,6] | 3,0 / **1,2** | **5,3** | **448/466** |
| Parakeet v3 | 16,7 | 10,1 | 6,5 / 3,8 | 14,5 | 315/466 |
| large-v3 | 27,2 | 21,9 | 6,5 / 3,4 | 26,0 | 70/466 |

## Cosa dicono

1. **Italiano: Whisper turbo è il più fedele.** Sulle sostituzioni ascoltate Jacopo ha scelto il testo di turbo (riferimento A) 68 volte e CrisperWhisper 22. CrisperWhisper inoltre toglie parole dette (12 casi su 13 ascoltati).
2. **Inglese: CrisperWhisper è il più fedele** (2,7% contro 5,3–7,9% di turbo a seconda del seme). Coerente con il suo training (EN/DE).
3. **Sul parlato conservato vince sempre CrisperWhisper**: 96% delle esitazioni e 48 troncate su 49, contro quasi zero di turbo.
4. **Il prompt con disfluenze peggiora turbo** in italiano, e in inglese non lo migliora in modo stabile.
5. **Parakeet e large-v3 sono fuori gara:** Parakeet riscrive (sostituzioni 6,5% in italiano), large-v3 genera loop.

## Limiti

- **Un file per lingua** (16 e 29 minuti): gli intervalli si sovrappongono poco, ma servono en-001 e it-001, anche solo a campione, per confermare.
- **it-002:** 38 inserzioni di CrisperWhisper non sono state ascoltate e valgono A, cioè non entrano nel riferimento. Questo penalizza un po' CrisperWhisper in italiano: nel controllo a campione erano vere 7 su 8.
- **en-002:** le esitazioni aggiunte da CrisperWhisper sono state accettate nonostante un controllo di 6 su 9 (scelta di Jacopo). Pesano solo sulle metriche secondarie, non sulla fedeltà.
- **I riferimenti A partivano dalla bozza di turbo**, corretta a mano. Sulle sostituzioni l'ascolto rende il confronto equo, ma dove turbo e il riferimento coincidono per ancoraggio l'errore resta invisibile.
- **La licenza di CrisperWhisper** è non commerciale (decisione 0009).

## Implicazioni (da decidere)

- **Motore predefinito:** turbo (libero, veloce, il migliore in italiano). **CrisperWhisper come opzione per l'inglese** e per chi vuole il parlato completo, solo per uso non commerciale.
- **Fine-tuning:** un LoRA su AMI e ICSI (inglese) migliorerebbe turbo dove CrisperWhisper è già meglio, ma non l'italiano, che è il caso d'uso principale. Distillare CrisperWhisper per l'italiano ne erediterebbe i difetti. Per ora non sembra prioritario.
