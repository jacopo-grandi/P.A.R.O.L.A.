"""Key phrases of a call and a title suggested from them, without a language model.

A RAKE-style extractor (Rose et al., 2010; decisions 0020, 0022, 0023). The text is cut into
candidate phrases at words that cannot belong to a topic:

- closed classes: articles, prepositions, pronouns, conjunctions, auxiliaries and modals,
  numbers; the fillers of docs/conventions.md and the usual discourse markers;
- the most frequent words of the language (Zipf frequency 6 or more, over one in a thousand
  words: "cosa", "think", "because"), the frequency-based stop list RAKE itself suggests;
- adverbs in -mente, punctuation, and doubtful words.

A phrase has one to three content words and may hold "di"/"of" ("raccolta delle olive", "number
of seeds"). It scores TF-IDF against the language: how often it is said, times how often its
words are said in the call weighted by how rare they are in Italian or English (wordfreq). So
"basil" or "DOP" beat "realtà" or "lavoro" without any list of generic words, also in calls
nobody looked at. Singular and plural count together.

The title is built like a title, not a tag list: the two best phrases joined by "e"/"and", and
two phrases with the same head coordinated ("peperoni rossi" + "peperoni gialli" -> "Peperoni
rossi e gialli").

A capital letter counts as a name only away from the start of a sentence, where the sentence
forces it. Whisper hallucinates "Thank you." on quiet stretches, one sentence per stretch, so
the capitalized "Thank" of a long call used to pass for a name and reach the title.

A doubtful word enters a phrase only if it was transcribed the same way at least
``DOUBTFUL_REPEATS`` times: once, it may be a mistake; ten identical "baking soda" are the subject
of the call. Nothing is added to the transcript; the title is only a suggestion the person can
change.
"""

from __future__ import annotations

import re
from collections import Counter
from dataclasses import dataclass
from functools import cache

from wordfreq import zipf_frequency

from parola.eval.normalize import FILLER_FORMS
from parola.schema import Transcript

MAX_WORDS = 3
TITLE_PHRASES = 2
TITLE_CHARS = 60
MIN_CONTENT_WORDS = 60  # below this a call is a test or a greeting: no title to suggest
DOUBTFUL_REPEATS = 3
# Zipf 6 = once per thousand words: the top of the language, where only function words and
# all-purpose words live.
FREQUENT_ZIPF = 6.0


def _words(text: str) -> list[str]:
    return text.split()


# Closed classes only: they can be listed in full, so the list does not depend on any call.
STOP_IT = frozenset(
    _words(
        """
a ad al allo ai agli all alla alle col coi con da dal dallo dai dagli dall dalla dalle di del
dello dei degli dell della delle in nel nello nei negli nell nella nelle su sul sullo sui sugli
sull sulla sulle per tra fra il lo la i gli le l un uno una e ed o od ma se che chi cui non né
ne ci vi si mi ti li me te ce ve io tu lui lei noi voi loro mio mia miei mie tuo tua tuoi tue
suo sua suoi sue nostro nostra nostri nostre vostro vostra vostri vostre questo questa questi
queste quello quella quelli quelle quel quei quegli qui qua lì là come dove quando quanto quanta
quanti quante più meno molto molta molti molte poco poca pochi poche tanto tanta tanti tante
tutto tutta tutti tutte altro altra altri altre ogni qualche qualcosa nulla niente sempre mai
già ancora anche pure solo proprio così dopo prima poi ora adesso oggi ieri domani sopra sotto
dentro fuori senza contro verso fino mentre perché perchè poiché però anzi oppure invece sì no
essere sono sei è siamo siete era eri erano ero sarà saranno sarei sarebbe stato stata stati
state sia siano fosse fossero avere ho hai ha abbiamo avete hanno avevo aveva avevano avuto avrà
avrei avrebbe abbia abbiano stare sto sta stai stiamo stanno stavo stava potere posso puoi può
possiamo potete possono potrebbe dovere devo devi deve dobbiamo dovete devono dovrebbe volere
voglio vuoi vuole vogliamo volete vogliono vorrei c' l' un' dell' all' nell' sull' dall' quest'
quell' po'
"""
    )
)
STOP_EN = frozenset(
    _words(
        """
a an the and or but if then so of to in on at by for with from into onto over under about as
than that this these those there here it its it's i me my we us our you your he him his she
her they them their what which who whom whose when where why how all any some no not only
also just very more most less much many few each every other another such own same is are was
were be been being am have has had having do does did doing done can could will would shall
should may might must let's i'm you're we're they're i've we've don't doesn't didn't can't
won't isn't aren't wasn't weren't yes no
"""
    )
)
# Words that carry the flow of speech, not its subject. Verbatim keeps them; titles do not.
DISCOURSE = frozenset(
    _words(
        """
allora quindi cioè insomma diciamo praticamente tipo comunque appunto ecco boh beh vabbe
vabbè magari forse ok okay va' be' mah uhm hmm basically literally anyway alright yeah oh
"""
    )
)
# Numbers said as words: "quattro vasi" names the pots, not the four.
NUMBERS = frozenset(
    _words(
        """
zero uno una due tre quattro cinque sei sette otto nove dieci undici dodici venti trenta
quaranta cinquanta cento mille milione milioni miliardo miliardi primo prima secondo seconda
terzo terza mezzo mezza one two three four five six seven eight nine ten hundred thousand
million first second third half
"""
    )
)
# Determiners and articulated prepositions: they select a noun phrase, so a phrase said after
# one of them is nominal ("il basilico", "the ripest tomato"); "esatto", "ciao" or "in realtà"
# never are. Closed classes, listed in full.
DETERMINERS = frozenset(
    _words(
        """
il lo la i gli le l un uno una un' del dello della dei degli delle dell al allo alla ai agli
alle all dal dallo dalla dai dagli dalle dall nel nello nella nei negli nelle nell sul sullo
sulla sui sugli sulle sull col coi questo questa questi queste quest quel quello quella quelli
quelle quei quegli quell mio mia miei mie tuo tua tuoi tue suo sua suoi sue nostro nostra
nostri nostre vostro vostra vostri vostre loro ogni qualche alcuni alcune ciascun nessun the a
an this that these those my your his her its our their every each some any no another
"""
    )
)
# Share of a phrase's occurrences that must follow a determiner for it to count as a topic.
NOMINAL_SHARE = 0.1
# "di"/"of" may join two content words inside a phrase: "raccolta delle olive".
CONNECTORS = frozenset(_words("di del della dei degli delle dello dell dell' d' of"))

_EDGE = '.,;:!?…"“”«»()[]{}'
_BREAK_AFTER = re.compile(r"[.,;:!?…]$")
_ELIDED = re.compile(r"^([a-zà-ù]+')(.+)$", re.IGNORECASE)


@dataclass(frozen=True)
class Phrase:
    text: str  # as said, with the most common spelling
    count: int  # times the phrase was said
    score: float


def _fillers() -> frozenset[str]:
    return frozenset(f for forms in FILLER_FORMS.values() for f in (*forms, *forms.values()))


_FILLERS = _fillers()


def _is_stop(word: str, lang: str = "it") -> bool:
    return (word in STOP_IT or word in STOP_EN or word in DISCOURSE or word in _FILLERS
            or word in NUMBERS or _looks_like_adverb(word)
            # Either language: calls mix them, and "because" in an Italian sentence is still
            # a function word.
            or max(_zipf(word, "it"), _zipf(word, "en")) >= FREQUENT_ZIPF)  # fmt: skip


@cache
def _zipf(word: str, lang: str) -> float:
    """How common the word is in the language: 7 for "the", 3 for "basil", 0 if unknown."""
    return zipf_frequency(word, lang if lang in ("it", "en") else "it")


def _rarity(word: str, lang: str) -> float:
    """IDF against the language: -log10 of the word's frequency (Zipf is log10 per billion)."""
    return max(0.0, 9.0 - _zipf(word, lang))


def _looks_like_adverb(word: str) -> bool:
    """ "semplicemente", "basically": about how something is said, not what."""
    return (len(word) > 7 and word.endswith("mente")) or (len(word) > 5 and word.endswith("ly"))


def fold(word: str) -> str:
    """Singular and plural counted as one: pomodoro/pomodori, seed/seeds."""
    if len(word) > 4 and word[-1] in "aeio" and word[-2] not in "aeiou":
        return word[:-1]
    if len(word) > 3 and word.endswith("s") and not word.endswith("ss"):
        return word[:-1]
    return word


def _key(text: str) -> str:
    surface = text.strip().strip(_EDGE)
    m = _ELIDED.match(surface)
    return (m.group(2) if m else surface).lower()


def _content(run: list[tuple[str, str]]) -> list[str]:
    return [w for w, _ in run if w not in CONNECTORS]


def _runs(
    t: Transcript,
) -> tuple[list[list[tuple[str, str]]], dict[str, Counter], list[bool], dict[str, Counter]]:
    """Runs of (lowercase word, spelling as said) between breaks, the languages each word was said
    in, for each run whether a determiner comes right before it, and the spellings of each word
    away from the start of a sentence. A connector stays in a run only between two content
    words."""
    runs: list[list[tuple[str, str]]] = []
    starts: list[bool] = []
    langs: dict[str, Counter] = {}
    free: dict[str, Counter] = {}  # spellings where the sentence does not force a capital
    doubtful = Counter(_key(w.text) for s in t.segments for w in s.words if w.doubtful)

    def close(run: list[tuple[str, str]], det: bool) -> None:
        if _content(run):
            runs.append(run)
            starts.append(det)

    for seg in t.segments:
        lang = seg.lang or "it"
        run: list[tuple[str, str]] = []
        pending: list[tuple[str, str]] = []  # a connector waiting for the next content word
        det = False  # the run being built started right after a determiner
        before = ""  # the previous word, lowercase
        for w in seg.words:
            raw = w.text.strip()
            surface = raw.strip(_EDGE)
            initial = not before  # first word of a sentence: its capital is forced
            after_det = before in DETERMINERS
            # "l'impatto" -> "impatto"; "dell'impatto" may continue a phrase as "dell' impatto".
            if m := _ELIDED.match(surface):
                lead = m.group(1).lower()
                after_det = lead.rstrip("'") in DETERMINERS
                if run and lead in CONNECTORS:
                    pending = [(lead, m.group(1))]
                else:
                    close(run, det)
                    run, pending = [], []
                surface = m.group(2)
            before = surface.lower()
            word = surface.lower()
            acronym = len(surface) >= 2 and surface.isupper() and surface.isalpha()
            trusted = not w.doubtful or doubtful[_key(w.text)] >= DOUBTFUL_REPEATS
            content = (word and trusted and not _is_stop(word, lang)
                       and not any(c.isdigit() for c in word)
                       and (len(word) >= 3 or acronym))  # fmt: skip
            ends = bool(_BREAK_AFTER.search(raw))
            if content:
                if not run:
                    det = after_det
                run += [*pending, (word, surface)]
                pending = []
                langs.setdefault(word, Counter())[lang] += 1
                if not initial:
                    free.setdefault(word, Counter())[surface] += 1
            elif run and word in CONNECTORS and not pending and not ends:
                pending = [(word, surface)]
            else:
                close(run, det)
                run, pending = [], []
            if run and ends:
                close(run, det)
                run, pending = [], []
            if ends:
                before = ""
        close(run, det)
    return runs, langs, starts, free


def _spell(spellings: Counter, free: Counter) -> str:
    """The usual spelling: capitals for an acronym written so at least once (DOP), a capital
    initial for a name always written so where the sentence does not force it (Giulia), lowercase
    otherwise. A capital at the start of a sentence says nothing: a hallucinated "Thank you." on
    a quiet stretch is a sentence, not a name."""
    word, _ = spellings.most_common(1)[0]
    if any(s.isupper() and 2 <= len(s) <= 6 for s in spellings):
        return next(s for s in spellings if s.isupper())
    if free and all(s[:1].isupper() for s in free):
        return word[:1].upper() + word[1:].lower()
    return word.lower()


def _show(words: tuple[str, ...], spellings: dict[str, Counter], free: dict[str, Counter]) -> str:
    out = ""
    for w in words:
        text = w if w in CONNECTORS else _spell(spellings[w], free.get(w, Counter()))
        out += text if out.endswith("'") or not out else " " + text
    return out


def _inner_phrases(words: list[str]) -> list[tuple[int, list[str]]]:
    """Shorter stretches of a phrase that start and end on content words and hold two or more,
    with where they start."""
    out = []
    n = len(words)
    for i in range(n):
        for j in range(i + 1, n + 1):
            if (i, j) == (0, n) or words[i] in CONNECTORS or words[j - 1] in CONNECTORS:
                continue
            if len([w for w in words[i:j] if w not in CONNECTORS]) >= 2:
                out.append((i, words[i:j]))
    return out


def key_phrases(t: Transcript, limit: int = 10) -> list[Phrase]:
    """The call's key phrases, best first."""
    runs, langs, starts, free = _runs(t)
    spellings: dict[str, Counter] = {}
    for run in runs:
        for w, surface in run:
            if w not in CONNECTORS:
                spellings.setdefault(w, Counter())[surface] += 1
    freq = Counter(fold(w) for run in runs for w in _content(run))
    # How rare each (folded) word is in the language, from its most common form and language.
    forms: dict[str, Counter] = {}
    for w, spelled in spellings.items():
        forms.setdefault(fold(w), Counter())[w] += sum(spelled.values())
    rarity = {}
    for key, ws in forms.items():
        word = ws.most_common(1)[0][0]
        rarity[key] = _rarity(word, langs[word].most_common(1)[0][0])
    counts: Counter[tuple[str, ...]] = Counter()
    nominal: Counter[tuple[str, ...]] = Counter()  # times said right after a determiner
    seen: dict[tuple[str, ...], Counter] = {}  # folded phrase -> the forms it was said in
    for run, det in zip(runs, starts, strict=True):
        words = [w for w, _ in run]
        # A long run: its words still count, as single-word candidates.
        if len(_content(run)) <= MAX_WORDS:
            candidates = [(words, det)]
            # A phrase of two or more words also counts where it is said inside a longer one:
            # "vaso rialzato" in "vaso rialzato di ottobre".
            candidates += [(c, det and i == 0) for i, c in _inner_phrases(words)]
        else:
            candidates = [([w], det and k == 0) for k, w in enumerate(_content(run))]
        for c, after_det in candidates:
            key = tuple(w if w in CONNECTORS else fold(w) for w in c)
            counts[key] += 1
            nominal[key] += after_det
            seen.setdefault(key, Counter())[tuple(c)] += 1

    def is_topic(key: tuple[str, ...]) -> bool:
        """A noun phrase: said after a determiner often enough, or a name or an acronym (names
        go without articles: "Italy", "Portogallo")."""
        if nominal[key] >= NOMINAL_SHARE * counts[key]:
            return True
        shown = _show(seen[key].most_common(1)[0][0], spellings, free)
        return any(w[:1].isupper() for w in shown.split() if w not in CONNECTORS)

    counts = Counter({k: n for k, n in counts.items() if is_topic(k)})

    def score(key: tuple[str, ...], n: int) -> float:
        # TF-IDF against the language: said often, made of words said often in this call and
        # rare in Italian or English.
        return n * sum(freq[w] * rarity[w] for w in key if w not in CONNECTORS)

    ranked = sorted(counts.items(), key=lambda kv: (-score(*kv), -kv[1], kv[0]))
    chosen: list[tuple[tuple[str, ...], int]] = []
    for key, n in ranked:
        words = {w for w in key if w not in CONNECTORS}
        inside = [
            i for i, (k, _) in enumerate(chosen) if {w for w in k if w not in CONNECTORS} <= words
        ]
        if inside and n >= 2:
            # A longer phrase said at least twice replaces a better one it contains:
            # "pizza margherita" over "pizza".
            chosen[inside[0]] = (key, n)
            continue
        if inside or any(words <= {w for w in k if w not in CONNECTORS} for k, _ in chosen):
            continue
        chosen.append((key, n))
        if len(chosen) == limit:
            break
    return [
        Phrase(_show(seen[key].most_common(1)[0][0], spellings, free), n, float(score(key, n)))
        for key, n in chosen
    ]


def _language(t: Transcript) -> str:
    langs = Counter(s.lang for s in t.segments if s.lang)
    return langs.most_common(1)[0][0] if langs else "it"


def suggest_title(t: Transcript) -> str | None:
    """A title from the two best key phrases, or None when the call is too short to tell."""
    if sum(len(_content(r)) for r in _runs(t)[0]) < MIN_CONTENT_WORDS:
        return None
    phrases = [p.text for p in key_phrases(t, limit=6) if p.count >= 2]
    if not phrases:
        return None
    conj = " and " if _language(t) == "en" else " e "
    parts: list[str] = []
    used: set[int] = set()
    for i, a in enumerate(phrases):
        if i in used:
            continue
        head, *rest = a.split()
        # Same head, different modifier: "peperoni rossi" + "peperoni gialli".
        for j in range(i + 1, len(phrases)):
            b_head, *b_rest = phrases[j].split()
            if j not in used and rest and b_rest and fold(head.lower()) == fold(b_head.lower()):
                a = a + conj + " ".join(b_rest)
                used.add(j)
                break
        candidate = conj.join([*parts, a])
        if parts and (len(candidate) > TITLE_CHARS or conj in a):
            break  # one coordination per title: "A e B e C e D" no longer reads as a title
        parts.append(a)
        if len(parts) == TITLE_PHRASES or conj in a:
            break
    title = conj.join(parts)
    if len(title) > TITLE_CHARS:
        title = parts[0]
    return title[:1].upper() + title[1:]
