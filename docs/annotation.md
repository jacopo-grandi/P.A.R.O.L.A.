# Come si annota un riferimento

Guida pratica per trascrivere a mano il test set secondo [conventions.md](conventions.md).

## Flusso

```bash
uv run parola transcribe data/private/call.m4a          # -> call.json, call.txt (bozza del modello)
uv run parola annotate draft data/private/call.json     # -> call.ann.txt (da correggere)
# ...correggi call.ann.txt ascoltando l'audio...
uv run parola annotate import data/private/call.ann.txt # -> call.ref.json (riferimento validato)
```

1. Apri `call.ann.txt` in un editor e correggi **ascoltando l'audio**: testo, confini dei segmenti, lingua e codici.
2. Quando hai controllato tutto il file, cambia `# status: draft` in `# status: reviewed`. Finché resta `draft` l'import rifiuta il file: così l'output del modello non può finire nel test set per errore.
3. `import` controlla il file con le regole delle convenzioni. Se ci sono errori, non scrive nulla e indica il segmento e la parola da sistemare. Gli avvisi (per esempio cifre nel testo) non bloccano.
4. Nel manifest `data/manifests/test.jsonl`, nella riga del file, imposta `"reference": "data/private/testset/<id>.ref.json"` e `"reference_quality": "gold"` (o `"silver"` se le disfluenze non sono state verificate ascoltando tutto l'audio; vedi conventions.md §4) (o aggiungi una riga nuova per una registrazione nuova). Poi controlla tutto con:
   ```bash
   uv run parola manifest check data/manifests/test.jsonl --files
   ```

Tutti i file restano in `data/private/`, che è ignorato da git.

## Formato

```
# parola-annotation 1
# status: reviewed
# audio_file: call.m4a
# duration: 362.240

[00:00:00.000 - 00:00:04.200] lang=it channel=system speaker=A
Ehm, ci vediamo lunedì,|fs no|ed martedì per la call|en.

[00:00:04.300 - 00:00:05.000] lang=it bc
Sì,|red sì.
```

- **Intestazione del segmento:** `[inizio - fine]`, poi `lang=it|en` (obbligatorio). Opzionali: `channel=mic|system|mixed`, `speaker=…`, e i flag `overlap` e `bc` (tutto il segmento è un backchannel).
- **Testo:** può occupare più righe. Un blocco si separa dal successivo con una riga vuota.
- **Segmenti:** per spezzarne uno, copia l'intestazione e aggiusta i tempi. Per eliminarne uno, cancella tutto il blocco.

### Codici per parola

Si aggiungono con `|` subito dopo la parola, prima o dopo la punteggiatura (`lunedì,|fs` e `lunedì|fs,` sono equivalenti). Una parola può averne più di uno: `call|en|rep`.

| Codice | Tag | Esempio |
|---|---|---|
| `f` | filler (solo per `ah`, `oh`, che non sono automatici) | `ah|f` |
| `-f` | annulla il filler automatico | `eh|-f` (es. "eh" con valore di risposta) |
| `rep` | repetition | `il,|rep il progetto` |
| `red` | reduplication | `sì,|red sì` |
| `fs` | false_start | `lunedì,|fs no|ed martedì` |
| `ed` | edit_term | (vedi sopra) |
| `bc` | backchannel (singola parola) | `mh|bc` |
| `en` / `it` | lingua diversa da quella del segmento | `call|en` |

`{più parole}|fs` applica i codici a tutte le parole tra le graffe: `{Perché noi abbiamo}|fs... il cliente`.

### Tag automatici

L'import aggiunge da solo questi tag:

- `truncated` alle parole che finiscono con `-` (`propo-`);
- `nonverbal` a `[risata]`, `[tosse]`, `[rumore]`, `[silenzio]`;
- `uncertain` a `(parola?)` o `(due parole?)`, salvando nel JSON le parole senza parentesi;
- `filler` a `eh`, `ehm`, `mh`, `uh`, `um`, `hmm`, ma non quando sono seguiti da `?` o stanno in un segmento `bc`.

`[inaudibile]` non prende tag.

### Cosa controllare nella bozza del modello

Whisper sbaglia tipicamente in questi punti:

- **toglie le esitazioni:** vanno reinserite, perché sono l'obiettivo principale del test set;
- **scrive "okay" o "OK":** va scritto `ok`;
- **scrive i numeri in cifre:** vanno in lettere;
- **sbaglia nomi e termini inglesi** (`Mistral`, `Le Chat`): vanno corretti e marcati `|en`;
- **sbaglia i confini dei segmenti:** `annotate draft` unisce già i segmenti separati da pause fino a 1 s (al massimo 30 s; `--no-merge` per disattivarlo), ma **non sa dove cambia il parlante**: lì il segmento va spezzato a mano;
- **unisce o duplica le ripetizioni:** si sentono solo all'ascolto.

## Riferimenti `adjudicated` (ascolto solo delle divergenze)

Invece di correggere tutta una bozza, si ascoltano solo i punti in cui due trascrizioni non sono d'accordo ([decisione 0009](decisions/0009-two-models-and-crisperwhisper-license.md), [verifica](../results/2026-10-15-audit-crisper.md)).

```bash
uv run parola adjudicate build it-002          # pagina in data/private/adjudicate/it-002/index.html
uv run parola adjudicate apply it-002 ~/Downloads/adjudication-it-002.json
```

- Se il file ha già un riferimento, si confronta quello (A) con CrisperWhisper (B). Altrimenti si parte da CrisperWhisper (A) e lo si confronta con Whisper turbo (B).
- **Regola automatica** (Jacopo, 2026-10-15): le divergenze in cui CrisperWhisper aggiunge una ripetizione, una troncata o parole in più al testo di A sono accettate (B) senza ascolto. Le aggiunte di altre parole e di esitazioni sono accettate con un controllo a campione (una su sei), mentre le sostituzioni e le parole tolte si ascoltano sempre. Se un controllo dà meno del 90% di accordo con B, `apply` si ferma: si rigenera con `--listen <tipo>` e le risposte già date restano.
- Per ogni divergenza: <kbd>spazio</kbd> riascolta, <kbd>1</kbd> A, <kbd>2</kbd> B, <kbd>3</kbd> scrivi il testo giusto. Senza risposta vale A.
- `apply` scrive `<id>.ref.json` (il riferimento precedente resta come `<id>.ref.<qualità>.json`) e aggiorna il manifest: `reference_quality: adjudicated` e `derived_from: ["crisperwhisper"]`. Le esitazioni prese da CrisperWhisper sono ricondotte all'inventario della lingua (`um` → `ehm` in italiano).
