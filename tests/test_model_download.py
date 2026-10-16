"""The first download of the models: asked for, counted in bytes, refused while missing."""

import time
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

from parola import models
from parola.app.server import create_app


def info(name, size, cached=False):
    return SimpleNamespace(filename=name, file_size=size, will_download=not cached)


@pytest.fixture
def hub(monkeypatch):
    """A fake Hugging Face Hub: each file reports its bytes in two chunks, as tqdm updates."""
    import huggingface_hub

    repos = {
        "mlx-community/whisper-large-v3-turbo": [info("config.json", 100, cached=True),
                                                 info("weights.safetensors", 1000)],
        "mlx-community/parakeet-tdt-0.6b-v3": [info("config.json", 50),
                                               info("model.safetensors", 2000),
                                               info("README.md", 7)],  # not read by parakeet
    }  # fmt: skip
    fetched = []

    def snapshot_download(repo, dry_run=False):
        assert dry_run
        return repos[repo]

    def hf_hub_download(repo, filename, tqdm_class):
        size = next(i.file_size for i in repos[repo] if i.filename == filename)
        with tqdm_class(total=size) as bar:
            bar.update(size // 2)
            bar.update_transfer(size)  # network bytes: not counted twice
            bar.set_postfix_str("10 MB/s")
            bar.update(size - size // 2)
        fetched.append((repo, filename))

    monkeypatch.setattr(huggingface_hub, "snapshot_download", snapshot_download)
    monkeypatch.setattr(huggingface_hub, "hf_hub_download", hf_hub_download)
    monkeypatch.delenv("HF_HUB_OFFLINE", raising=False)
    return fetched


def missing(monkeypatch, voices=True):
    monkeypatch.setattr(models, "models_ready", lambda: False)
    monkeypatch.setattr(models, "_diarization_ready", lambda: not voices)
    received = []

    def ensure_models(on_bytes):
        on_bytes(models.DIARIZATION_BYTES)
        received.append(True)

    monkeypatch.setattr("parola.diarize.ensure_models", ensure_models)
    return received


def wait(download, timeout=5.0):
    end = time.monotonic() + timeout
    while download.status()["state"] == "downloading" and time.monotonic() < end:
        time.sleep(0.01)
    return download.status()


def test_nothing_is_downloaded_before_asking(monkeypatch, hub):
    missing(monkeypatch)
    d = models.ModelDownload()
    assert d.status() == {"state": "missing", "done": 0, "total": models.APPROX_BYTES,
                          "message": ""}  # fmt: skip
    assert hub == []


def test_download_counts_the_bytes_of_the_files_still_missing(monkeypatch, hub):
    voices = missing(monkeypatch)
    d = models.ModelDownload()
    d.start()
    st = wait(d)
    assert st["state"] == "ready"
    # The cached config and the README parakeet never reads are skipped.
    assert hub == [("mlx-community/whisper-large-v3-turbo", "weights.safetensors"),
                   ("mlx-community/parakeet-tdt-0.6b-v3", "config.json"),
                   ("mlx-community/parakeet-tdt-0.6b-v3", "model.safetensors")]  # fmt: skip
    assert st["total"] == 1000 + 50 + 2000 + models.DIARIZATION_BYTES
    assert st["done"] == st["total"] and voices == [True]


def test_progress_is_bytes_written_not_bytes_twice(monkeypatch, hub):
    missing(monkeypatch, voices=False)
    d = models.ModelDownload()
    d._download()
    assert d.done == d.total == 1000 + 50 + 2000


def test_failure_can_be_retried(monkeypatch, hub):
    missing(monkeypatch, voices=False)
    monkeypatch.setenv("HF_HUB_OFFLINE", "1")
    d = models.ModelDownload()
    d.start()
    st = wait(d)
    assert st["state"] == "error" and "HF_HUB_OFFLINE" in st["message"]
    monkeypatch.delenv("HF_HUB_OFFLINE")
    d.start()
    assert wait(d)["state"] == "ready"


def test_ready_models_need_no_download(hub):
    d = models.ModelDownload()  # conftest: the models are on disk
    assert d.start()["state"] == "ready" and hub == []


def test_the_app_will_not_record_or_import_without_the_models(monkeypatch, tmp_path, hub):
    missing(monkeypatch)
    client = TestClient(create_app(tmp_path))
    assert client.get("/api/record/status").json()["models"] == "missing"
    assert client.post("/api/record/start", json={}).status_code == 409
    r = client.post("/api/import?filename=a.wav", content=b"RIFF")
    assert r.status_code == 409
    assert client.get("/api/models").json()["state"] == "missing"
