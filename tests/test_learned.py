"""The glossary learned from corrections, on made-up calls: it starts empty and only suggests."""

from datetime import UTC, datetime

from parola import editing
from parola.learned import MIN_CORRECTIONS, is_term, learn, suggest
from parola.schema import Metadata, Segment, Transcript, Word


def call(*lines: str) -> Transcript:
    segments, t = [], 0.0
    for line in lines:
        words = []
        for tok in line.split():
            words.append(Word(text=tok, start=t, end=t + 0.3, doubtful=True))
            t += 0.4
        segments.append(Segment(start=words[0].start, end=words[-1].end, text=line, words=words))
    meta = Metadata(audio_file="x.wav", duration=t, created_at=datetime(2026, 10, 16, tzinfo=UTC),
                    parola_version="0")  # fmt: skip
    return Transcript(metadata=meta, segments=segments)


def corrected(lines, fixes) -> Transcript:
    """A call where each (segment, start, end, text) was corrected by the person."""
    t = call(*lines)
    for seg, start, end, text in fixes:
        editing.correct(t, seg, start, end, text)
    return t


def test_it_starts_empty():
    assert learn([]) == {}
    assert suggest("orto lap", learn([])) == []


def test_terms_are_names_acronyms_and_rare_words_not_grammar():
    assert is_term("Orto-Lab") and is_term("QX") and is_term("mulching") and is_term("Q4")
    assert not is_term("ha") and not is_term("perché") and not is_term("la riunione")


def test_rarity_is_measured_in_the_language_of_the_call():
    assert is_term("baking soda", "it")  # English business words in Italian speech
    assert not is_term("baking soda", "en")


def test_a_term_is_suggested_only_after_enough_corrections():
    once = [corrected(["parliamo di orto lap"], [(0, 2, 4, "Orto-Lab")])]
    assert suggest("orto lap", learn(once)) == []
    twice = [*once, corrected(["il orto lap va"], [(0, 1, 3, "Orto-Lab")])]
    terms = learn(twice)
    assert terms["ortolab"].count == MIN_CORRECTIONS
    (s,) = suggest("orto lap", terms)
    assert (s.text, s.term, s.exact) == ("Orto-Lab", "Orto-Lab", True)


def test_grammar_fixes_are_not_learned():
    t = [corrected(["lui a detto"], [(0, 1, 2, "ha")]) for _ in range(3)]
    assert learn(t) == {}


def test_a_close_spelling_is_suggested_too():
    t = [corrected(["il beking soda"], [(0, 1, 3, "baking soda")]) for _ in range(2)]
    t += [corrected(["i ki"], [(0, 1, 2, "QX")]) for _ in range(2)]
    (s, *_) = suggest("bakin soda", learn(t))
    assert s.term == "baking soda" and not s.exact


def test_the_suggestion_replaces_only_the_matching_words():
    t = [corrected(["il orto lap"], [(0, 1, 3, "Orto-Lab")]) for _ in range(2)]
    (s,) = suggest("il orto lap", learn(t))
    assert s.text == "il Orto-Lab"


def test_a_term_differing_only_in_case_and_dots_is_still_suggested():
    # "parola" corrected to "P.A.R.O.L.A.": same letters, but the correction IS the spelling.
    t = [corrected(["parliamo di parola adesso"], [(0, 2, 3, "P.A.R.O.L.A.")]) for _ in range(2)]
    terms = learn(t)
    assert terms["parola"].count == 2
    (s,) = suggest("parola", terms)
    assert (s.term, s.exact) == ("P.A.R.O.L.A.", True)
    assert suggest("P.A.R.O.L.A.", terms) == []  # already written that way
    assert suggest("P.A.R.O.L.A.,", terms) == []  # even with punctuation attached


def test_a_case_only_brand_correction_is_learned():
    # "zentrix" -> "Zentrix": same letters and sounds, but the brand's casing is the point.
    t = [corrected(["usiamo zentrix qui"], [(0, 1, 2, "Zentrix")]) for _ in range(2)]
    (s,) = suggest("zentrix", learn(t))
    assert (s.term, s.exact) == ("Zentrix", True)
    assert suggest("Zentrix", learn(t)) == []  # already written that way


def test_nothing_is_suggested_for_what_is_already_right():
    t = [corrected(["il orto lap"], [(0, 1, 3, "Orto-Lab")]) for _ in range(2)]
    assert suggest("Orto-Lab", learn(t)) == []


def test_an_undone_correction_is_forgotten():
    t = corrected(["il orto lap"], [(0, 1, 3, "Orto-Lab")])
    editing.undo(t)
    assert learn([t, t]) == {}


def test_glossary_command(tmp_path, capsys):
    from parola.cli import main

    assert main(["glossary", "--dir", str(tmp_path)]) == 0
    assert "nothing learned yet" in capsys.readouterr().out
    for i in range(2):
        corrected(["il orto lap"], [(0, 1, 3, "Orto-Lab")]).save(tmp_path / f"c{i}.json")
    assert main(["glossary", "--dir", str(tmp_path)]) == 0
    out = capsys.readouterr().out
    assert "Orto-Lab" in out and "suggested" in out and "orto lap (2)" in out
