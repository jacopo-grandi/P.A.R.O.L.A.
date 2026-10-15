# Come si annota un riferimento

Guida pratica per trascrivere a mano il test set secondo [conventions.md](conventions.md).

## Flusso

```bash
uv run ilat transcribe data/private/call.m4a          # -> call.json, call.txt (bozza del modello)
uv run ilat annotate draft data/private/call.json     # -> call.ann.txt (da correggere)
# ...correggi call.ann.txt ascoltando l'audio...
uv run ilat annotate import data/private/call.ann.txt # -> call.ref.json (riferimento validato)
```

1. Apri `call.ann.txt` in un editor e correggi **ascoltando l'audio**: testo, confini dei segmenti, lingua e codici.
2. Quando hai controllato tutto il file, cambia `# status: draft` in `# status: reviewed`. Finché resta `draft` l'import rifiuta il file: così l'output del modello non può finire nel test set per errore.
3. `import` controlla il file con le regole delle convenzioni. Se ci sono errori, non scrive nulla e indica il segmento e la parola da sistemare. Gli avvisi (per esempio cifre nel testo) non bloccano.
4. Aggiungi una riga al manifest `data/manifests/test.jsonl` e controlla tutto con:
   ```bash
   uv run ilat manifest check data/manifests/test.jsonl --files
   ```

Tutti i file restano in `data/private/`, che è ignorato da git.

## Formato

```
# ilat-annotation 1
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
- **sbaglia i confini dei segmenti:** vanno rifatti dove cambia il parlante o c'è una pausa di più di 1 s;
- **unisce o duplica le ripetizioni:** si sentono solo all'ascolto.
