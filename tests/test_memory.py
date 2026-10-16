"""Releasing the speech models: the caches are emptied, the next run loads again."""

import sys
import types

from parola.asr import release_models


def test_release_empties_both_model_caches(monkeypatch):
    holder = types.SimpleNamespace(model="whisper", model_path="turbo")
    monkeypatch.setitem(
        sys.modules, "mlx_whisper.transcribe", types.SimpleNamespace(ModelHolder=holder)
    )
    cleared = []
    fake_mx = types.SimpleNamespace(clear_cache=lambda: cleared.append("mlx"))
    monkeypatch.setitem(sys.modules, "mlx.core", fake_mx)
    from parola.asr import parakeet_backend

    calls = []
    monkeypatch.setattr(
        parakeet_backend, "_load", types.SimpleNamespace(cache_clear=lambda: calls.append(1))
    )
    release_models()
    assert holder.model is None and holder.model_path is None
    assert calls == [1] and cleared == ["mlx"]


def test_release_works_before_anything_was_loaded(monkeypatch):
    monkeypatch.delitem(sys.modules, "mlx_whisper.transcribe", raising=False)
    release_models()  # nothing to free, no error
