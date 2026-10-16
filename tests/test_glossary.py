from types import SimpleNamespace as NS

from ilat import glossary
from ilat.asr.mlx_whisper_backend import carried_prompt


def test_load_and_prompt(tmp_path):
    f = tmp_path / "g.txt"
    f.write_text("# comment\nLED\n\nbaking soda\nLED\nOrto-Lab\n")
    assert glossary.load(f) == ["LED", "baking soda", "Orto-Lab"]
    assert glossary.prompt_text(["LED", "baking soda"]) == "LED, baking soda."
    assert glossary.prompt_text([]) is None
    assert glossary.load(tmp_path / "missing.txt") == []


def test_prompt_is_cut_on_a_term_boundary():
    terms = [f"term{k:03d}" for k in range(100)]
    text = glossary.prompt_text(terms)
    assert len(text) <= glossary.MAX_CHARS and text.endswith(".") and "term0" in text


class FakeTokenizer:
    sot_prev = -1

    def encode(self, text):
        return [len(w) for w in text.split()]


def task(prompt):
    return NS(sot_sequence=(100, 101), tokenizer=FakeTokenizer(), n_ctx=12, sample_len=None,
              options=NS(prefix=None, prompt=prompt))  # fmt: skip


def test_carried_prompt_keeps_the_glossary_on_every_window():
    from mlx_whisper import decoding

    original = decoding.DecodingTask._get_initial_tokens
    with carried_prompt("aa bbb"):
        get = decoding.DecodingTask._get_initial_tokens
        # First window: no previous text, the glossary alone.
        assert get(task(None)) == (-1, 2, 3, 100, 101)
        # Later window: glossary + the most recent text that fits (n_ctx // 2 - 1 = 5 tokens).
        assert get(task([7, 8, 9, 10, 11])) == (-1, 2, 3, 9, 10, 11, 100, 101)
    assert decoding.DecodingTask._get_initial_tokens is original  # restored


def test_no_glossary_changes_nothing():
    from mlx_whisper import decoding

    original = decoding.DecodingTask._get_initial_tokens
    with carried_prompt(None):
        assert decoding.DecodingTask._get_initial_tokens is original
