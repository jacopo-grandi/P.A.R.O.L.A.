"""Key phrases of a call and a title suggested from them, without a language model.

A RAKE-style extractor (Rose et al., 2010; decision 0020): the text is cut at stop words,
fillers, discourse markers, punctuation and doubtful words; what is left between the cuts are
candidate phrases of one to three words. A phrase scores how often it is said times how often its
words are said, so a term repeated through the call ("baking soda", "mulching") beats a phrase said
once. It works on one call alone, with no archive to compare against.

A doubtful word enters a phrase only if it was transcribed the same way at least
``DOUBTFUL_REPEATS`` times: once, it may be a mistake; ten identical "baking soda" are the subject
of the call. Nothing is added to the transcript; the title is only a suggestion the person can
change.
"""

from __future__ import annotations

import re
from collections import Counter
from dataclasses import dataclass

from parola.eval.normalize import FILLER_FORMS
from parola.schema import Transcript

MAX_WORDS = 3
TITLE_PHRASES = 3
TITLE_CHARS = 60
MIN_CONTENT_WORDS = 60  # below this a call is a test or a greeting: no title to suggest
DOUBTFUL_REPEATS = 3


def _words(text: str) -> list[str]:
    return text.split()


# Function words. Hand-written, short on purpose: what matters is what breaks a phrase.
STOP_IT = frozenset(
    _words(
        """
a ad al allo ai agli all alla alle col coi con da dal dallo dai dagli dall dalla dalle di del
dello dei degli dell della delle in nel nello nei negli nell nella nelle su sul sullo sui sugli
sull sulla sulle per tra fra il lo la i gli le l un uno una un' e ed o od ma se che chi cui non
né ne ci vi si mi ti lo li me te se ce ve io tu lui lei noi voi loro mio mia miei mie tuo tua
tuoi tue suo sua suoi sue nostro nostra nostri nostre vostro vostra vostri vostre questo questa
questi queste quello quella quelli quelle quel quei quegli qui qua lì là come dove quando quanto
quanta quanti quante più meno molto molta molti molte poco poca pochi poche tanto tanta tanti
tante tutto tutta tutti tutte altro altra altri altre ogni qualche qualcosa nulla niente sempre
mai già ancora anche pure solo proprio così dopo prima poi ora adesso oggi ieri domani sopra
sotto dentro fuori senza contro verso fino mentre perché perchè poiché però anzi oppure invece
sia essere sono sei è siamo siete era eri erano ero sarà saranno sarei sarebbe stato stata stati
state stare sto sta stai stanno stavo stava avere ho hai ha abbiamo avete hanno avevo aveva
avevano avuto avrà avrei avrebbe fare faccio fai fa facciamo fate fanno fatto fatta fatti
facendo dire dico dici dice diciamo dite dicono detto andare vado vai va andiamo andate vanno
andato potere posso puoi può possiamo potete possono potrebbe dovere devo devi deve dobbiamo
dovete devono dovrebbe volere voglio vuoi vuole vogliamo volete vogliono vorrei sapere so sai
sa sappiamo sanno vedere vedo vedi vede vediamo vedete vedono visto metto metti mette mettiamo
messo dare do dai dà diamo danno dato venire vengo vieni viene veniamo vengono venuto pensare
penso pensi pensa pensiamo credo credi crede crediamo sembra sembrano pare parlare parlo parli
parla parliamo parlano capire capisco capito sentire sento sente abbia abbiano sia siano fosse
fossero stiamo state stanno facciamo serve servono bisogna c' l' un' dell' all' nell' sull' dall'
quest' quell' po' sì si no ok okay vabbè va' be'
"""
    )
)
# Endings that are verbs in Italian: "stiamo", "facendo", "spingere". Nouns rarely end so.
_VERB_ENDINGS = ("iamo", "iate", "ando", "endo", "are", "ere", "ire", "ate", "ete", "ite")
_NOT_VERBS = frozenset(
    _words(
        """
mare dare piacere potere sapere dovere carattere livello cliente fornitore partner area
software hardware share here there where care core more store score rete sete parete
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
won't isn't aren't wasn't weren't yes yeah ok okay oh like get got go going gone say said
thing things way really actually now well right
"""
    )
)
# Words that carry the flow of speech, not its subject. Verbatim keeps them; titles do not.
DISCOURSE = frozenset(
    _words(
        """
allora quindi cioè insomma diciamo praticamente tipo comunque appunto ecco boh beh vabbe
vabbè magari forse chiaramente ovviamente sicuramente fondamentalmente sostanzialmente
eventualmente esattamente assolutamente perfetto bene benissimo grazie scusa scusate ciao
guarda guardate senti sentite dai niente vero infatti mah uhm hmm basically like literally
anyway okay alright sorry thanks please esatto certo giusto chiaro sisi nono
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
# Nouns too generic to name a call.
GENERIC = frozenset(
    _words(
        """
volta volte parte parti modo punto punti tempo momento esempio caso fatto fatti persona persone
roba discorso domanda domande problema cosa cose giorno giorni settimana anno anni minuto minuti
secondo pezzo idea senso lato tipo time thing things stuff point part people way question
"""
    )
)

_EDGE = '.,;:!?…"“”«»()[]{}'
_BREAK_AFTER = re.compile(r"[.,;:!?…]$")
_ELIDED = re.compile(r"^([a-zà-ù]+')(.+)$", re.IGNORECASE)


@dataclass(frozen=True)
class Phrase:
    text: str  # as said, with the most common spelling of each word
    count: int  # times the phrase was said
    score: float


def _fillers() -> frozenset[str]:
    return frozenset(f for forms in FILLER_FORMS.values() for f in (*forms, *forms.values()))


_FILLERS = _fillers()


def _is_stop(word: str) -> bool:
    return (word in STOP_IT or word in STOP_EN or word in DISCOURSE or word in _FILLERS
            or word in GENERIC or word in NUMBERS or _looks_like_verb(word))  # fmt: skip


def _looks_like_verb(word: str) -> bool:
    return len(word) >= 6 and word.endswith(_VERB_ENDINGS) and word not in _NOT_VERBS


def _runs(t: Transcript) -> tuple[list[list[str]], dict[str, Counter]]:
    """Runs of content words (lowercased) between breaks, and the spellings seen for each."""
    runs: list[list[str]] = []
    spellings: dict[str, Counter] = {}
    doubtful = Counter(_key(w.text) for s in t.segments for w in s.words if w.doubtful)
    for seg in t.segments:
        run: list[str] = []
        for w in seg.words:
            raw = w.text.strip()
            surface = raw.strip(_EDGE)
            # "l'impatto" -> "impatto": the article is a stop word.
            if m := _ELIDED.match(surface):
                if run:
                    runs.append(run)
                run = []
                surface = m.group(2)
            word = surface.lower()
            acronym = len(surface) >= 2 and surface.isupper() and surface.isalpha()
            trusted = not w.doubtful or doubtful[_key(w.text)] >= DOUBTFUL_REPEATS
            content = (word and trusted and not _is_stop(word)
                       and not any(c.isdigit() for c in word)
                       and (len(word) >= 3 or acronym))  # fmt: skip
            if content:
                run.append(word)
                spellings.setdefault(word, Counter())[surface] += 1
            elif run:
                runs.append(run)
                run = []
            if run and _BREAK_AFTER.search(raw):
                runs.append(run)
                run = []
        if run:
            runs.append(run)
    return runs, spellings


def _key(text: str) -> str:
    surface = text.strip().strip(_EDGE)
    m = _ELIDED.match(surface)
    return (m.group(2) if m else surface).lower()


def key_phrases(t: Transcript, limit: int = 10) -> list[Phrase]:
    """The call's key phrases, best first."""
    runs, spellings = _runs(t)
    freq = Counter(w for run in runs for w in run)
    phrases: Counter[tuple[str, ...]] = Counter()
    for run in runs:
        if len(run) <= MAX_WORDS:
            phrases[tuple(run)] += 1
        else:  # a long run: its words still count, as single-word candidates
            for w in run:
                phrases[(w,)] += 1

    # Said often, made of words said often; a phrase of two or three words weighs a bit more,
    # since "baking soda" names a subject better than "key" or "result" alone.
    scored = sorted(
        (
            (n * sum(freq[w] for w in p) * (1 + 0.5 * (len(p) - 1)), n, p)
            for p, n in phrases.items()
        ),
        key=lambda x: (-x[0], -x[1], x[2]),
    )
    out: list[Phrase] = []
    taken: set[str] = set()
    for score, n, p in scored:
        if set(p) <= taken:  # all its words are already in a better phrase
            continue
        out.append(Phrase(" ".join(_common(spellings[w]) for w in p), n, float(score)))
        taken |= set(p)
        if len(out) == limit:
            break
    return out


def _common(spellings: Counter) -> str:
    """The usual spelling, lowercase unless the word is always written in capitals."""
    word, _ = spellings.most_common(1)[0]
    if all(s.isupper() for s in spellings) and len(word) >= 2:
        return word
    if all(s[:1].isupper() for s in spellings):  # a name: "Giulia", "Torino"
        return word[:1].upper() + word[1:].lower()
    return word.lower()


def suggest_title(t: Transcript) -> str | None:
    """A title made of the top key phrases, or None when the call is too short to tell."""
    runs, _ = _runs(t)
    if sum(len(r) for r in runs) < MIN_CONTENT_WORDS:
        return None
    phrases = [p for p in key_phrases(t, limit=TITLE_PHRASES * 2) if p.count >= 2]
    if not phrases:
        return None
    parts: list[str] = []
    for p in phrases:
        if len(parts) == TITLE_PHRASES or len(" · ".join([*parts, p.text])) > TITLE_CHARS:
            break
        parts.append(p.text)
    if not parts:
        return None
    first = parts[0]
    parts[0] = first[:1].upper() + first[1:]
    return " · ".join(parts)
