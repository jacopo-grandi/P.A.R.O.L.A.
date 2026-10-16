import os

import pytest

from parola import models


@pytest.fixture(autouse=True)
def restore_offline_flag():
    """offline_if_cached sets a process-wide flag: restore it after each test."""
    from huggingface_hub import constants

    before_env, before_const = os.environ.get("HF_HUB_OFFLINE"), constants.HF_HUB_OFFLINE
    yield
    if before_env is None:
        os.environ.pop("HF_HUB_OFFLINE", None)
    else:
        os.environ["HF_HUB_OFFLINE"] = before_env
    constants.HF_HUB_OFFLINE = before_const


def test_offline_when_everything_is_cached(monkeypatch):
    monkeypatch.delenv("HF_HUB_OFFLINE", raising=False)
    monkeypatch.setattr(models, "is_cached", lambda repo: True)
    assert models.offline_if_cached(["a", "b"]) is True
    assert os.environ["HF_HUB_OFFLINE"] == "1"


def test_online_for_the_first_download(monkeypatch, capsys):
    monkeypatch.delenv("HF_HUB_OFFLINE", raising=False)
    monkeypatch.setattr(models, "is_cached", lambda repo: repo == "a")
    assert models.offline_if_cached(["a", "b"]) is False
    assert "(first use only): b" in capsys.readouterr().err


def test_explicit_setting_is_respected(monkeypatch):
    monkeypatch.setenv("HF_HUB_OFFLINE", "0")
    monkeypatch.setattr(models, "is_cached", lambda repo: True)
    assert models.offline_if_cached(["a"]) is False
