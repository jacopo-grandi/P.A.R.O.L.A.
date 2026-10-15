# Convenzioni di trascrizione

Stato: **v0.1 approvata** da Jacopo il 2026-10-15.

Queste regole valgono per i riferimenti scritti a mano (test set), per i convertitori dei corpora (Fase 3) e per la valutazione (Fase 2). Il livello pulito (Fase 6) può fare solo ciò che è elencato in [§3](#3-livello-pulito).

Gli esempi sono inventati.

## 1. Principi

1. **Si scrive ciò che è stato detto**, non ciò che si voleva dire: esitazioni, ripetizioni, parole troncate, false partenze e forme colloquiali restano.
2. **Il testo resta leggibile.** Le informazioni strutturali (tipo di disfluenza, lingua, sovrapposizione) vanno nei tag del JSON, non in marcatori dentro il testo. Le uniche eccezioni sono quelle elencate qui: trattino delle troncate, `[evento]`, `[inaudibile]`, `(parola?)`.
3. **Le regole sono meccaniche dove possibile.** Quando una regola richiede un giudizio, lo dice esplicitamente.
4. **Se hai un dubbio, trascrivi e marca come incerto** con `(parola?)`, invece di omettere.

## 2. Livello verbatim

### 2.1 Segmenti

- Un segmento è un enunciato di un solo parlante. Si apre un nuovo segmento al cambio di parlante o dopo una pausa di più di 1 s.
- Durata massima di un segmento: 30 s. Oltre, si spezza alla pausa più vicina.
- Ogni segmento ha `lang`, la lingua prevalente (`it` o `en`), e `channel` (`mic`, `system` o `mixed`).

### 2.2 Esitazioni (`filler`)

Si usa un **inventario chiuso**. Ogni esitazione va ricondotta alla forma più vicina:

| Lingua | Forme ammesse | Varianti da ricondurre |
|---|---|---|
| IT | `eh`, `ehm`, `mh`, `ah`, `oh` | eeh, eee → `eh`; ehmm, uhm, emm → `ehm`; mmm, hmm → `mh` |
| EN | `uh`, `um`, `hmm` | uhh, er → `uh`; umm, erm → `um`; mmm → `hmm` |

- Il tag `filler` si mette solo quando la forma riempie una pausa di pianificazione.
- Sono parole normali, senza `filler`:
  - `eh?` interrogativo: "eh? non ho sentito";
  - `ah` di comprensione o sorpresa: "ah, sì, ho capito";
  - `oh` esclamativo.
- `mh mh` detto come assenso è un backchannel ([§2.13](#213-backchannel-backchannel)), non un'esitazione.
- La lingua dell'esitazione è quella del segmento.

> Ehm, allora, eh, partiamo dalla ricetta.
> → `Ehm` e `eh` hanno il tag `filler`.

### 2.3 Parole troncate (`truncated`)

- La parte pronunciata si chiude con un trattino, attaccato e senza spazio: `propo-`.
- Se la parola viene poi completata, si scrivono entrambe.

> Abbiamo mandato la propo- la proposta ieri.
> → `propo-` ha il tag `truncated`.

- Un frammento troppo breve per capire che parola fosse si scrive comunque con il trattino: `p-`.

### 2.4 Ripetizioni (`repetition`)

- Si scrivono **tutte** le occorrenze; la virgola tra una e l'altra è facoltativa.
- Il tag `repetition` va su tutte le occorrenze **tranne l'ultima**: il livello pulito toglie le parole marcate e tiene l'ultima.
- Vale per parole singole e per sequenze ripetute.

> Il, il, il progetto parte lunedì.
> → i primi due `il` hanno il tag `repetition`.
>
> Se vuoi, se vuoi ci sentiamo dopo.
> → il primo `se vuoi` ha il tag `repetition`.

- **Le ripetizioni enfatiche o formulari non sono disfluenze.** Per esempio "sì, sì, sì", "ciao ciao", "no no no".
  - Ricevono il tag `reduplication` invece di `repetition`, sempre su tutte le occorrenze tranne l'ultima.
  - Il livello pulito le riduce allo stesso modo, ma la metrica delle disfluenze non le conta.
  - **Serve giudizio:** la ripetizione è enfatica se è voluta e scorrevole, è un `repetition` se c'è un'esitazione nel mezzo ("il... il progetto"). Nel dubbio si usa `repetition`.

> Sì, sì, sì, ho capito.
> → i primi due `sì` hanno il tag `reduplication`.

### 2.5 False partenze e autocorrezioni (`false_start`, `edit_term`)

- **Falsa partenza:** una frase iniziata e abbandonata. Si trascrive per intero e le parole abbandonate hanno il tag `false_start`.
- **Autocorrezione:** chi parla ritratta qualcosa e lo sostituisce.
  - La parte ritrattata ha il tag `false_start`.
  - L'eventuale segnale di correzione (`no`, `anzi`, `cioè`, `scusa`, `I mean`, `sorry`) ha il tag `edit_term`, ma solo quando introduce davvero una correzione.

> Ci vediamo lunedì, no, martedì.
> → `lunedì` ha il tag `false_start`, `no` ha il tag `edit_term`.
>
> Perché noi abbiamo... il cliente vuole la demo.
> → `Perché noi abbiamo` ha il tag `false_start`.

- **Serve giudizio** per distinguere un'autocorrezione da un'aggiunta ("lunedì, anzi anche martedì" non è una correzione). Nel dubbio non si mettono tag.

### 2.6 Punteggiatura e maiuscole

- Punteggiatura **leggera**, guidata dalla prosodia: virgola, punto, `?`, `!` e `...` per un'interruzione.
- Maiuscola a inizio enunciato e nei nomi propri.
- Le metriche ignorano punteggiatura e maiuscole: non serve che siano perfette, ma devono restare coerenti.

### 2.7 Numeri

- **In lettere, come pronunciati.** Gli esempi: `quattromila`, `ventitré`, `duemilaventisei`, `tre e mezza`, `dieci per cento`, `four thousand`.
- I numeri composti italiani si scrivono in una parola sola, secondo l'ortografia standard.
- Si scrive ciò che è stato detto: "quattro k" si scrive `quattro k`, non `quattromila`.

### 2.8 Code-switching (lingua per parola)

- Le parole inglesi si scrivono con la **grafia inglese standard**, senza marcatori nel testo.
- Nel JSON ogni parola ha `lang` (`it` o `en`).
- Regola meccanica: una parola con grafia inglese non adattata ha `lang=en`, anche se è un prestito comune. Per esempio `ok`, `call`, `task`, `meeting`, `email`.
- Le esitazioni prendono la lingua del segmento.

> Ti mando il recap della call dopo il meeting.
> → `recap`, `call` e `meeting` hanno `lang=en`; il segmento ha `lang=it`.

- **Ibridi italianizzati:** si scrivono come pronunciati, con la radice inglese e la desinenza italiana, e hanno `lang=it`. Per esempio `brainstormare`, `pushare`, `trainato`, `deployato`.

### 2.9 Forme colloquiali

- Si trascrivono come dette, **senza correzioni grammaticali**: `a me mi piace`, `te lo dico`, `'sta roba`.
- Le forme ricorrenti hanno una grafia fissa:

| Grafia ammessa | Da non usare |
|---|---|
| `vabbè` | va be', vabbe', vabbé |
| `beh`, `boh`, `mah` | be', bo, ma' |
| `'sta`, `'sto`, `'ste`, `'sti` | sta, sto (ambigui con il verbo stare) |
| `ok` | okay, OK, o.k. |
| `perché`, `poiché`, `né` | perchè |
| `sennò` | se no (quando vuol dire "altrimenti") |
| `c'ho`, `c'hai`, `c'ha` | ciò, ci ho (quando si pronuncia /tʃɔ/) |

La lista si può estendere: ogni nuova forma va aggiunta qui.

### 2.10 Nomi propri, marchi, sigle

- Si usa la **grafia corretta** quando il riferimento è chiaro, anche se la pronuncia è imprecisa. Per esempio "Mistra" si scrive `Mistral`; per gli altri: `ChatGPT`, `Le Chat`, `Google Meet`.
- Le sigle si scrivono in maiuscolo, nella forma standard: `GPU`, `AGI`, `API`.
- Se il riferimento non è chiaro, si scrive come sentito e si marca come incerto: `(Coastra?)`.

### 2.11 Eventi non verbali (`nonverbal`)

- Si usano solo questi tag: `[risata]`, `[tosse]`, `[rumore]`, `[silenzio]`. `[silenzio]` vale solo per pause di più di 3 s dentro un segmento.
- Sono token a sé, con il tag `nonverbal`, e sono **esclusi dal WER**.
- Se una persona parla ridendo si trascrivono le parole, senza `[risata]`.

### 2.12 Parlato inaudibile o incerto (`uncertain`)

- `[inaudibile]` sostituisce un tratto che non si capisce, qualunque sia la sua lunghezza. È un solo token, senza tag di lingua.
- `(parola?)` indica un'ipotesi incerta; nel JSON il testo è `parola` e ha il tag `uncertain`. Le parentesi possono contenere più parole: `(Le Chat?)`.
- Nella metrica le parti incerte si escludono o si pesano a parte (da definire in Fase 2).

### 2.13 Backchannel (`backchannel`)

- Un backchannel è un assenso o un'interiezione breve detta mentre l'altro ha il turno: `sì`, `mh mh`, `ok`, `esatto`, `certo`, `ah ok`.
- **Si trascrive** con il tag `backchannel`, di solito in un segmento a sé.
- Se invece prende il turno ("Esatto, e poi...") è una parola normale.

### 2.14 Sovrapposizioni (`overlap`)

- **Su canali diversi** (mic e system) le sovrapposizioni non vanno marcate: si ricavano dai timestamp.
- **Sullo stesso canale** (due persone tra "gli altri"):
  - si trascrivono entrambe le voci, in segmenti separati con tempi che si sovrappongono, ognuno con il flag di segmento `overlap`;
  - questi segmenti sono **esclusi dal WER principale** e misurati a parte.
- Se una delle due voci non si capisce si usa `[inaudibile]`.

### 2.15 Riepilogo dei tag

| Tag | Livello | Significato |
|---|---|---|
| `filler` | parola | esitazione dell'inventario chiuso |
| `truncated` | parola | parola troncata (`propo-`) |
| `repetition` | parola | occorrenza ripetuta, tranne l'ultima |
| `reduplication` | parola | ripetizione enfatica o formulare, tranne l'ultima |
| `false_start` | parola | parte abbandonata o ritrattata |
| `edit_term` | parola | segnale di autocorrezione (`no`, `anzi`, `cioè`...) |
| `backchannel` | parola | assenso breve mentre parla l'altro |
| `nonverbal` | parola | `[risata]`, `[tosse]`, `[rumore]`, `[silenzio]` |
| `uncertain` | parola | ipotesi incerta `(parola?)` |
| `overlap` | segmento | sovrapposizione sullo stesso canale |
| `lang` | parola e segmento | `it` o `en` (campo, non tag) |

`[inaudibile]` è un token senza tag di disfluenza.

## 3. Livello pulito

Il livello pulito è **derivato** dal verbatim e ne è un sottoinsieme normalizzato. Ogni frase pulita indica gli indici delle parole verbatim da cui deriva.

### 3.1 Cosa può togliere

| Cosa | Come |
|---|---|
| Esitazioni | via le parole con il tag `filler` |
| Parole troncate | via le parole con il tag `truncated` |
| Ripetizioni | via le parole con i tag `repetition` o `reduplication`: resta l'ultima occorrenza |
| Autocorrezioni e false partenze | via `false_start` ed `edit_term`: resta solo la correzione ("lunedì, no, martedì" → "martedì") |
| Segnali discorsivi vuoti | `cioè`, `tipo`, `nel senso`, `praticamente`, `diciamo`, `boh`, `vabbè`, `insomma`, `like`, `you know`, ma **solo se non hanno valore semantico** |

L'ultima riga richiede un giudizio, che fa l'LLM. Per esempio "tipo, adesso partiamo" diventa "adesso partiamo", mentre "costa tipo dieci euro" (dove "tipo" vuol dire "circa") resta com'è. Nel dubbio la parola si tiene.

**Non si tolgono:** backchannel, eventi non verbali, `[inaudibile]` e parole incerte. Le parole incerte perdono solo le parentesi e il `?`.

### 3.2 Cosa può normalizzare

1. **Numeri in cifre**: `quattromila GPU` → `4000 GPU`, `dieci per cento` → `10%`.
2. **Punteggiatura e maiuscole**, da sistemare secondo la grammatica.
3. **Grammatica colloquiale, con una lista chiusa** (ogni voce nuova va aggiunta qui):

| Verbatim | Pulito |
|---|---|
| `a me mi` | `a me` |
| `te` clitico (`te lo dico`, `te dirò`) | `ti` |
| `'sta`, `'sto`, `'ste`, `'sti` | `questa`, `questo`, `queste`, `questi` |
| `c'ho`, `c'hai`, `c'ha` (possesso) | `ho`, `hai`, `ha` |

### 3.3 Cosa non può mai fare

- Aggiungere parole che non sono nel verbatim, salvo quelle prodotte dalle normalizzazioni di [§3.2](#32-cosa-può-normalizzare).
- Riformulare, cambiare l'ordine delle parole, tradurre o riassumere.
- Correggere il contenuto, per esempio un dato sbagliato detto da chi parla.
- Togliere parole con significato per "snellire" la frase.

Queste regole sono verificate da test automatici (Fase 6).

## 4. Effetti sulle metriche (anticipo della Fase 2)

- **WER classico:** si tolgono `filler`, `truncated`, `repetition`, `reduplication`, `false_start`, `edit_term`, eventi non verbali e `[inaudibile]`; numeri e grafie vengono normalizzati.
- **WER verbatim:** si tolgono solo eventi non verbali e `[inaudibile]`; tutto il resto conta.
- **Disfluenze:** si misura, per `filler`, `truncated`, `repetition`, `false_start` ed `edit_term`, quante delle parole marcate nel riferimento il modello conserva e quante ne inventa. `reduplication` e `backchannel` vengono riportati a parte, non come disfluenze.
- **Esclusi in tutte le metriche:** i segmenti `overlap` (misurati a parte); le parole `uncertain` sono escluse o pesate a parte.
- Le soglie dei segmenti ([§2.1](#21-segmenti)) si rivedono sul primo test set, se servono.
