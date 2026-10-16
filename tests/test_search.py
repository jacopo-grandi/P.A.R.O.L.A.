"""Search in the transcripts, on hand-built calls."""

from datetime import UTC, datetime

from parola.schema import Metadata, Segment, Transcript, Word
from parola.search import find, fold, forms


def call(*lines: str) -> Transcript:
    segments, t = [], 0.0
    for line in lines:
        words = []
        for tok in line.split():
            words.append(Word(text=tok, start=t, end=t + 0.3))
            t += 0.4
        segments.append(Segment(start=words[0].start, end=words[-1].end, text=line,
                                channel="system", words=words))  # fmt: skip
    meta = Metadata(audio_file="x.wav", duration=t, created_at=datetime(2026, 10, 16, tzinfo=UTC),
                    parola_version="0")  # fmt: skip
    return Transcript(metadata=meta, segments=segments)


def test_fold_ignores_case_accents_and_edge_punctuation():
    assert fold("Perché,") == "perche"
    assert fold("«Città»") == "citta"
    assert fold("dell'area") == "dell'area"


def test_elided_words_are_found_by_their_noun():
    assert forms("Dell'impatto.") == {"dell'impatto", "impatto"}
    hits = find(call("parliamo dell'impatto sul concime"), "impatto")
    assert [(h.segment, h.word, h.match) for h in hits] == [(0, 1, "dell'impatto")]


def test_every_hit_with_its_place_and_time():
    t = call("il mulching sale", "ehm il mulching, sì", "nessuno")
    hits = find(t, "MULCHING")
    assert [(h.segment, h.word) for h in hits] == [(0, 1), (1, 2)]
    assert hits[1].time == hits[1].time and hits[1].match == "mulching,"


def test_several_words_must_be_said_in_a_row():
    t = call("il baking soda della domenica", "baking e soda")
    hits = find(t, "baking soda")
    assert [(h.segment, h.word, h.length) for h in hits] == [(0, 1, 2)]


def test_snippet_has_context_on_both_sides():
    words = " ".join(f"w{i}" for i in range(20))
    (hit,) = find(call(words.replace("w10", "obiettivo")), "obiettivo")
    assert hit.before.split() == [f"w{i}" for i in range(2, 10)]
    assert hit.after.split() == [f"w{i}" for i in range(11, 19)]


def test_empty_query_finds_nothing():
    assert find(call("ciao a tutti"), "  ,  ") == []
