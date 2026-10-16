# How to annotate a reference

A practical guide to transcribing the test set by hand according to [conventions.md](conventions.md).

## Workflow

```bash
uv run parola transcribe data/private/call.m4a          # -> call.json, call.txt (model draft)
uv run parola annotate draft data/private/call.json     # -> call.ann.txt (to correct)
# ...correct call.ann.txt while listening to the audio...
uv run parola annotate import data/private/call.ann.txt # -> call.ref.json (validated reference)
```

1. Open `call.ann.txt` in an editor and correct it **while listening to the audio**: text, segment boundaries, language and codes.
2. When you have checked the whole file, change `# status: draft` to `# status: reviewed`. As long as it stays `draft`, the import refuses the file: this way the model's output cannot end up in the test set by mistake.
3. `import` checks the file against the rules of the conventions. If there are errors, it writes nothing and points to the segment and the word to fix. Warnings (for example digits in the text) do not block it.
4. In the manifest `data/manifests/test.jsonl`, in the file's row, set `"reference": "data/private/testset/<id>.ref.json"` and `"reference_quality": "gold"` (or `"silver"` if the disfluencies were not checked by listening to all the audio; see conventions.md §4) (or add a new row for a new recording). Then check everything with:
   ```bash
   uv run parola manifest check data/manifests/test.jsonl --files
   ```

All files stay in `data/private/`, which is ignored by git.

## Format

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

- **Segment header:** `[start - end]`, then `lang=it|en` (required). Optional: `channel=mic|system|mixed`, `speaker=…`, and the flags `overlap` and `bc` (the whole segment is a backchannel).
- **Text:** it can span several lines. A block is separated from the next one by an empty line.
- **Segments:** to split one, copy the header and adjust the times. To delete one, delete the whole block.

### Codes per word

They are added with `|` right after the word, before or after the punctuation (`lunedì,|fs` and `lunedì|fs,` are equivalent). A word can have more than one: `call|en|rep`.

| Code | Tag | Example |
|---|---|---|
| `f` | filler (only for `ah`, `oh`, which are not automatic) | `ah|f` |
| `-f` | cancels the automatic filler | `eh|-f` (e.g. "eh" used as an answer) |
| `rep` | repetition | `il,|rep il progetto` |
| `red` | reduplication | `sì,|red sì` |
| `fs` | false_start | `lunedì,|fs no|ed martedì` |
| `ed` | edit_term | (see above) |
| `bc` | backchannel (single word) | `mh|bc` |
| `en` / `it` | language other than the segment's | `call|en` |

`{several words}|fs` applies the codes to all the words between the braces: `{Perché noi abbiamo}|fs... il cliente`.

### Automatic tags

The import adds these tags by itself:

- `truncated` to words ending in `-` (`propo-`);
- `nonverbal` to `[risata]`, `[tosse]`, `[rumore]`, `[silenzio]`;
- `uncertain` to `(parola?)` or `(due parole?)`, saving the words without parentheses in the JSON;
- `filler` to `eh`, `ehm`, `mh`, `uh`, `um`, `hmm`, but not when they are followed by `?` or are in a `bc` segment.

`[inaudibile]` gets no tag.

### What to check in the model draft

Whisper typically makes mistakes in these places:

- **it removes fillers:** they must be put back, because they are the main goal of the test set;
- **it writes "okay" or "OK":** it must be written `ok`;
- **it writes numbers as digits:** they go in words;
- **it gets names and English terms wrong** (`Mistral`, `Le Chat`): they must be corrected and marked `|en`;
- **it gets segment boundaries wrong:** `annotate draft` already joins segments separated by pauses of up to 1 s (at most 30 s; `--no-merge` to turn it off), but **it does not know where the speaker changes**: there the segment must be split by hand;
- **it merges or duplicates repetitions:** you only hear them by listening.

## `adjudicated` references (listening only to the disagreements)

Instead of correcting a whole draft, you listen only to the points where two transcripts do not agree ([audit](../results/2026-10-15-audit-crisper.md)).

```bash
uv run parola adjudicate build it-002          # page in data/private/adjudicate/it-002/index.html
uv run parola adjudicate apply it-002 ~/Downloads/adjudication-it-002.json
```

- If the file already has a reference, that one (A) is compared with CrisperWhisper (B). Otherwise it starts from CrisperWhisper (A) and compares it with Whisper turbo (B).
- **Automatic rule** (Jacopo, 2026-10-15): disagreements where CrisperWhisper adds a repetition, a truncated word or extra words to A's text are accepted (B) without listening. Additions of other words and of fillers are accepted with a spot check (one in six), while substitutions and removed words are always listened to. If a check gives less than 90% agreement with B, `apply` stops: rebuild with `--listen <kind>`, and the answers already given are kept.
- For each disagreement: <kbd>space</kbd> plays it again, <kbd>1</kbd> A, <kbd>2</kbd> B, <kbd>3</kbd> type the right text. With no answer, A applies.
- `apply` writes `<id>.ref.json` (the previous reference is kept as `<id>.ref.<quality>.json`) and updates the manifest: `reference_quality: adjudicated` and `derived_from: ["crisperwhisper"]`. Fillers taken from CrisperWhisper are mapped to the language's inventory (`um` → `ehm` in Italian).
