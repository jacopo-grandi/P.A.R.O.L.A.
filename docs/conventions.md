# Transcription conventions

Status: **v0.1 approved** by Jacopo on 2026-10-15.

These rules apply to the hand-written references (test set), to the corpus converters (Phase 3) and to evaluation (Phase 2). The clean layer (Phase 6) can do only what is listed in [§3](#3-clean-layer).

The examples are made up.

## 1. Principles

1. **Write what was said**, not what was meant: fillers, repetitions, truncated words, false starts and colloquial forms stay.
2. **The text stays readable.** Structural information (disfluency type, language, overlap) goes in the JSON tags, not in markers inside the text. The only exceptions are the ones listed here: the hyphen of truncated words, `[evento]`, `[inaudibile]`, `(parola?)`.
3. **The rules are mechanical where possible.** When a rule needs judgement, it says so explicitly.
4. **If in doubt, transcribe and mark as uncertain** with `(parola?)`, instead of leaving it out.

## 2. Verbatim layer

### 2.1 Segments

- A segment is an utterance by a single speaker. A new segment starts when the speaker changes or after a pause of more than 1 s.
- Maximum length of a segment: 30 s. Beyond that, it is split at the nearest pause.
- Every segment has `lang`, the main language (`it` or `en`), and `channel` (`mic`, `system` or `mixed`).
- **Exception for single-channel recordings** (decided on 2026-10-15): if separating the turns of several speakers by hand is not practical, a segment can hold more than one, with an empty `speaker`. The metrics are computed on the text of the whole file, so segment boundaries do not affect them. In the app's two-channel recordings (Phase 7) turns are separated by channel.

### 2.2 Fillers (`filler`)

A **closed inventory** is used. Every filler is mapped to the closest form:

| Language | Allowed forms | Variants to map |
|---|---|---|
| IT | `eh`, `ehm`, `mh`, `ah`, `oh` | eeh, eee → `eh`; ehmm, uhm, emm → `ehm`; mmm, hmm → `mh` |
| EN | `uh`, `um`, `hmm` | uhh, er → `uh`; umm, erm → `um`; mmm → `hmm` |

- The `filler` tag is used only when the form fills a planning pause.
- These are normal words, without `filler`:
  - interrogative `eh?`: "eh? non ho sentito";
  - `ah` of understanding or surprise: "ah, sì, ho capito";
  - exclamatory `oh`.
- `mh mh` said as agreement is a backchannel ([§2.13](#213-backchannel-backchannel)), not a filler.
- The language of a filler is the segment's.

> Ehm, allora, eh, partiamo dalla ricetta.
> → `Ehm` and `eh` have the `filler` tag.

### 2.3 Truncated words (`truncated`)

- The spoken part ends with a hyphen, attached and without a space: `propo-`.
- If the word is then completed, both are written.

> Abbiamo mandato la propo- la proposta ieri.
> → `propo-` has the `truncated` tag.

- A fragment too short to tell which word it was is still written with the hyphen: `p-`.

### 2.4 Repetitions (`repetition`)

- **All** occurrences are written; the comma between them is optional.
- The `repetition` tag goes on all occurrences **except the last**: the clean layer removes the marked words and keeps the last one.
- This applies to single words and to repeated sequences.

> Il, il, il progetto parte lunedì.
> → the first two `il` have the `repetition` tag.
>
> Se vuoi, se vuoi ci sentiamo dopo.
> → the first `se vuoi` has the `repetition` tag.

- **Emphatic or formulaic repetitions are not disfluencies.** For example "sì, sì, sì", "ciao ciao", "no no no".
  - They get the `reduplication` tag instead of `repetition`, again on all occurrences except the last.
  - The clean layer reduces them the same way, but the disfluency metric does not count them.
  - **Needs judgement:** the repetition is emphatic if it is intended and fluent; it is a `repetition` if there is a filler in between ("il... il progetto"). If in doubt, use `repetition`.

> Sì, sì, sì, ho capito.
> → the first two `sì` have the `reduplication` tag.

### 2.5 False starts and self-corrections (`false_start`, `edit_term`)

- **False start:** a sentence started and abandoned. It is transcribed in full and the abandoned words have the `false_start` tag.
- **Self-correction:** the speaker retracts something and replaces it.
  - The retracted part has the `false_start` tag.
  - The correction signal, if any (`no`, `anzi`, `cioè`, `scusa`, `I mean`, `sorry`), has the `edit_term` tag, but only when it really introduces a correction.

> Ci vediamo lunedì, no, martedì.
> → `lunedì` has the `false_start` tag, `no` has the `edit_term` tag.
>
> Perché noi abbiamo... il cliente vuole la demo.
> → `Perché noi abbiamo` has the `false_start` tag.

- **Needs judgement** to tell a self-correction from an addition ("lunedì, anzi anche martedì" is not a correction). If in doubt, no tags are added.

### 2.6 Punctuation and capitals

- **Light** punctuation, guided by prosody: comma, full stop, `?`, `!` and `...` for an interruption.
- Capital letter at the start of an utterance and in proper names.
- The metrics ignore punctuation and capitals: they do not need to be perfect, but they must stay consistent.

### 2.7 Numbers

- **In words, as spoken.** Examples: `quattromila`, `ventitré`, `duemilaventisei`, `tre e mezza`, `dieci per cento`, `four thousand`.
- Italian compound numbers are written as a single word, following standard spelling.
- Write what was said: "quattro k" is written `quattro k`, not `quattromila`.

### 2.8 Code-switching (language per word)

- English words are written with **standard English spelling**, without markers in the text.
- In the JSON every word has `lang` (`it` or `en`).
- Mechanical rule: a word with unadapted English spelling has `lang=en`, even if it is a common loanword. For example `ok`, `call`, `task`, `meeting`, `email`.
- Fillers take the language of the segment.

> Ti mando il recap della call dopo il meeting.
> → `recap`, `call` and `meeting` have `lang=en`; the segment has `lang=it`.

- **Italianised hybrids:** written as spoken, with the English root and the Italian ending, and they have `lang=it`. For example `brainstormare`, `pushare`, `trainato`, `deployato`.

### 2.9 Colloquial forms

- Transcribed as said, **without grammatical corrections**: `a me mi piace`, `te lo dico`, `'sta roba`.
- Recurring forms have a fixed spelling:

| Allowed spelling | Do not use |
|---|---|
| `vabbè` | va be', vabbe', vabbé |
| `beh`, `boh`, `mah` | be', bo, ma' |
| `'sta`, `'sto`, `'ste`, `'sti` | sta, sto (ambiguous with the verb stare) |
| `ok` | okay, OK, o.k. |
| `perché`, `poiché`, `né` | perchè |
| `sennò` | se no (when it means "otherwise") |
| `c'ho`, `c'hai`, `c'ha` | ciò, ci ho (when pronounced /tʃɔ/) |

The list can be extended: every new form must be added here.

### 2.10 Proper names, brands, acronyms

- The **correct spelling** is used when the reference is clear, even if the pronunciation is imprecise. For example "Mistra" is written `Mistral`; for the others: `ChatGPT`, `Le Chat`, `Google Meet`.
- Acronyms are written in capitals, in the standard form: `GPU`, `AGI`, `API`.
- If the reference is not clear, write it as heard and mark it as uncertain: `(Coastra?)`.

### 2.11 Non-verbal events (`nonverbal`)

- Only these tags are used: `[risata]`, `[tosse]`, `[rumore]`, `[silenzio]`. `[silenzio]` applies only to pauses of more than 3 s inside a segment.
- They are tokens of their own, with the `nonverbal` tag, and are **excluded from the WER**.
- If a person speaks while laughing, the words are transcribed, without `[risata]`.

### 2.12 Inaudible or uncertain speech (`uncertain`)

- `[inaudibile]` replaces a stretch that cannot be understood, whatever its length. It is a single token, without a language tag.
- `(parola?)` marks an uncertain guess; in the JSON the text is `parola` and it has the `uncertain` tag. The parentheses can hold more than one word: `(Le Chat?)`.
- In the metric the uncertain parts are excluded or weighted separately (to be defined in Phase 2).

### 2.13 Backchannel (`backchannel`)

- A backchannel is a short agreement or interjection said while the other person has the turn: `sì`, `mh mh`, `ok`, `esatto`, `certo`, `ah ok`.
- **It is transcribed** with the `backchannel` tag, usually in a segment of its own.
- If instead it takes the turn ("Esatto, e poi...") it is a normal word.

### 2.14 Overlaps (`overlap`)

- **On different channels** (mic and system) overlaps are not marked: they follow from the timestamps.
- **On the same channel** (two people among "the others"):
  - both voices are transcribed, in separate segments with overlapping times, each with the `overlap` segment flag;
  - these segments are **excluded from the primary WER** and measured separately.
- If one of the two voices cannot be understood, use `[inaudibile]`.

### 2.15 Summary of the tags

| Tag | Level | Meaning |
|---|---|---|
| `filler` | word | filler from the closed inventory |
| `truncated` | word | truncated word (`propo-`) |
| `repetition` | word | repeated occurrence, except the last |
| `reduplication` | word | emphatic or formulaic repetition, except the last |
| `false_start` | word | abandoned or retracted part |
| `edit_term` | word | self-correction signal (`no`, `anzi`, `cioè`...) |
| `backchannel` | word | short agreement while the other person speaks |
| `nonverbal` | word | `[risata]`, `[tosse]`, `[rumore]`, `[silenzio]` |
| `uncertain` | word | uncertain guess `(parola?)` |
| `overlap` | segment | overlap on the same channel |
| `lang` | word and segment | `it` or `en` (field, not tag) |

`[inaudibile]` is a token without a disfluency tag.

## 3. Clean layer

The clean layer is **derived** from the verbatim one and is a normalised subset of it. Every clean sentence gives the indices of the verbatim words it comes from.

### 3.1 What it can remove

| What | How |
|---|---|
| Fillers | remove the words with the `filler` tag |
| Truncated words | remove the words with the `truncated` tag |
| Repetitions | remove the words with the `repetition` or `reduplication` tags: the last occurrence stays |
| Self-corrections and false starts | remove `false_start` and `edit_term`: only the correction stays ("lunedì, no, martedì" → "martedì") |
| Empty discourse markers | `cioè`, `tipo`, `nel senso`, `praticamente`, `diciamo`, `boh`, `vabbè`, `insomma`, `like`, `you know`, but **only if they carry no meaning** |

The last row needs judgement, which the LLM makes. For example "tipo, adesso partiamo" becomes "adesso partiamo", while "costa tipo dieci euro" (where "tipo" means "about") stays as it is. If in doubt, the word is kept.

**Not removed:** backchannels, non-verbal events, `[inaudibile]` and uncertain words. Uncertain words only lose the parentheses and the `?`.

### 3.2 What it can normalise

1. **Numbers as digits**: `quattromila GPU` → `4000 GPU`, `dieci per cento` → `10%`.
2. **Punctuation and capitals**, fixed according to grammar.
3. **Colloquial grammar, with a closed list** (every new entry must be added here):

| Verbatim | Clean |
|---|---|
| `a me mi` | `a me` |
| clitic `te` (`te lo dico`, `te dirò`) | `ti` |
| `'sta`, `'sto`, `'ste`, `'sti` | `questa`, `questo`, `queste`, `questi` |
| `c'ho`, `c'hai`, `c'ha` (possession) | `ho`, `hai`, `ha` |

### 3.3 What it can never do

- Add words that are not in the verbatim, except those produced by the normalisations of [§3.2](#32-what-it-can-normalise).
- Rephrase, change the word order, translate or summarise.
- Correct the content, for example a wrong figure stated by the speaker.
- Remove meaningful words to "slim down" the sentence.

These rules are checked by automated tests (Phase 6).

## 4. Effects on the metrics (preview of Phase 2)

- **Fidelity WER** (primary metric): `filler`, `truncated`, `repetition`, `reduplication`, `false_start`, `edit_term`, non-verbal events and `[inaudibile]` are removed, and immediate repetitions are collapsed. Numbers, spellings, capitals and punctuation are normalised. What counts is whether the words are the ones spoken: rewrites, paraphrases and grammatical "corrections" are errors. The report shows substitutions separately.
- **Verbatim WER:** only non-verbal events and `[inaudibile]` are removed; everything else counts.
- **Literal WER**: fillers, non-verbal events and `[inaudibile]` are removed; repetitions, false starts, truncated words and grammatical errors count. Only capitals and punctuation are normalised.
- **Disfluencies:** for `filler`, `truncated`, `repetition`, `false_start` and `edit_term`, we measure how many of the words marked in the reference the model keeps and how many it invents. `reduplication` and `backchannel` are reported separately, not as disfluencies.
- **Excluded from all metrics:** `overlap` segments (measured separately); `uncertain` words are excluded or weighted separately.
- **Quality of the references** (`reference_quality` field of the manifest):
  - `gold`: words and tags checked by listening to all the audio. Valid for all metrics.
  - `silver`: words checked by a person, but disfluency tags not fully checked (for example fillers proposed by a model and spot-checked). Valid for all metrics (decision of 2026-10-15), but the report always states which references each number is computed on. If the candidates were proposed by a model, that model's disfluency metrics are optimistic.
- The segment thresholds ([§2.1](#21-segments)) are revised on the first test set, if needed.
