"""Key phrases and suggested titles, on hand-built calls."""

from datetime import UTC, datetime
from itertools import product

from parola.keywords import key_phrases, suggest_title
from parola.schema import Metadata, Segment, Transcript, Word


def call(*lines: str, doubtful: set[str] = frozenset(), lang: str = "it") -> Transcript:
    """One segment per line; words in ``doubtful`` are flagged as doubtful."""
    segments = []
    t = 0.0
    for line in lines:
        words = []
        for tok in line.split():
            words.append(
                Word(text=tok, start=t, end=t + 0.3, doubtful=tok.strip(".,?") in doubtful)
            )
            t += 0.4
        segments.append(Segment(start=words[0].start, end=words[-1].end, text=line, lang=lang,
                                words=words))  # fmt: skip
    meta = Metadata(audio_file="x.wav", duration=t, created_at=datetime(2026, 10, 16, tzinfo=UTC),
                    parola_version="0")  # fmt: skip
    return Transcript(metadata=meta, segments=segments)


# Distinct content words, each said once: enough words for a title, none of them a key phrase.
FILLER = " ".join("k" + a + b for a, b in product("bcdfgjlmnpqrstvz", repeat=2))


def texts(t: Transcript, limit: int = 10) -> list[str]:
    return [p.text for p in key_phrases(t, limit)]


def test_stop_words_and_fillers_cut_phrases():
    t = call("allora eh il vaso rialzato è pronto", "quindi ehm il vaso rialzato di ottobre")
    assert texts(t)[0] == "vaso rialzato"
    assert not {"allora", "eh", "ehm", "quindi", "il", "è"} & {
        w for p in texts(t) for w in p.split()
    }


def test_punctuation_breaks_a_phrase():
    t = call("abbiamo il mulching. Raccolto tardivo", "il mulching, raccolto tardivo")
    assert "mulching raccolto tardivo" not in texts(t)
    assert {"mulching", "raccolto tardivo"} <= set(texts(t))


def test_repeated_phrase_beats_a_long_one_said_once():
    t = call("baking soda", "baking soda della domenica", "baking soda", "grande nuova idea strana")
    assert texts(t)[0] == "baking soda"


def test_elided_article_is_dropped():
    t = call("l'impatto sul concime", "dell'impatto sul concime")
    assert "impatto" in " ".join(texts(t)) and "l'impatto" not in texts(t)


def test_verbs_and_generic_nouns_do_not_name_a_call():
    t = call("stiamo spingendo il concime", "facciamo una cosa sul concime", "per esempio")
    words = {w for p in texts(t) for w in p.split()}
    assert (
        "concime" in words and not {"stiamo", "spingendo", "facciamo", "cosa", "esempio"} & words
    )


def test_a_doubtful_word_said_once_is_left_out_but_a_repeated_one_counts():
    once = call("parliamo di Ortolab oggi", "il concime", "il concime", doubtful={"Ortolab"})
    assert "Ortolab" not in " ".join(texts(once))
    lines = ["il mulching sale"] * 3
    repeated = call(*lines, doubtful={"mulching"})
    assert "mulching" in " ".join(texts(repeated))


def test_acronyms_and_names_keep_their_capitals():
    t = call("i LED di Giulia", "i LED di Giulia", "il mulching")
    assert {"LED", "Giulia"} <= set(texts(t)) or "LED" in texts(t)[0]
    assert all(p == p.lower() for p in texts(t) if p.startswith("mulching"))


def test_title_is_none_for_a_short_call():
    assert suggest_title(call("prova prova uno due tre", "prova")) is None


def test_title_from_the_top_phrases():
    filler = FILLER
    t = call(
        "il mulching naturale.", "il mulching naturale.", "il mulching naturale.",
        "i semi antichi.", "i semi antichi.", "il meteo.", "il meteo.", filler,
    )  # fmt: skip
    assert suggest_title(t) == "Mulching naturale e semi antichi"


def test_title_stays_short():
    long = "piattaforma integrazione sistemi"
    filler = FILLER
    t = call(*[f"{long}."] * 3, *["architettura distribuita."] * 3, *["roadmap trimestrale."] * 3,
             filler)  # fmt: skip
    title = suggest_title(t)
    assert title is not None and len(title) <= 60


def test_di_and_of_can_join_a_phrase():
    t = call("la raccolta delle olive.", "sulla raccolta delle olive.", "the number of seeds.",
             "number of seeds.")  # fmt: skip
    assert {"raccolta delle olive", "number of seeds"} <= set(texts(t))


def test_adverbs_do_not_name_a_call():
    t = call("semplicemente il concime.", "basically il concime.", "semplicemente")
    assert texts(t) == ["concime"]


def test_singular_and_plural_count_together():
    t = call("il pomodoro.", "i pomodori.", "i pomodori.", "un vaso.", "il glossario.")
    assert key_phrases(t, 1)[0].count == 3  # pomodoro + pomodori


def test_a_phrase_inside_a_longer_one_still_counts():
    t = call("il vaso rialzato.", "il vaso rialzato di ottobre.")
    assert key_phrases(t, 1)[0].text == "vaso rialzato"
    assert key_phrases(t, 1)[0].count == 2


def test_a_specific_phrase_said_twice_beats_its_head_word():
    t = call(*["la pizza."] * 5, "la pizza margherita.", "la pizza margherita.")
    assert texts(t)[0] == "pizza margherita"


def test_acronyms_written_in_capitals_once_stay_in_capitals():
    t = call("il dop.", "il DOP.", "il dop.")
    assert texts(t) == ["DOP"]


def test_title_coordinates_phrases_with_the_same_head():
    t = call(*["i peperoni rossi."] * 3, *["i peperoni gialli."] * 2, *["il meteo."] * 2, FILLER)
    assert suggest_title(t) == "Peperoni rossi e gialli"


def test_english_title_uses_and():
    lines = [*["the ripest tomato."] * 3, *["the number of seeds."] * 2, FILLER]
    assert suggest_title(call(*lines, lang="en")) == "Ripest tomato and number of seeds"
