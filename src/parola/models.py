"""Keep model loading offline once the weights are cached.

huggingface_hub contacts the Hub every time a model is loaded, even when it is already cached,
to look for updates. CLAUDE.md allows the network only for the first download, so parola switches
the Hub to offline mode whenever every model it needs is already on disk.
"""

from __future__ import annotations

import os
import sys


def is_cached(repo: str) -> bool:
    from huggingface_hub import snapshot_download

    try:
        snapshot_download(repo, local_files_only=True)
    except Exception:
        return False
    return True


def offline_if_cached(repos: list[str]) -> bool:
    """Set HF_HUB_OFFLINE=1 if all ``repos`` are cached; otherwise allow the first download.

    Returns True when offline. An explicit HF_HUB_OFFLINE set by the user is respected."""
    if "HF_HUB_OFFLINE" in os.environ:
        return os.environ["HF_HUB_OFFLINE"] not in ("", "0", "false")
    missing = [r for r in repos if not is_cached(r)]
    if missing:
        print(f"downloading models (first use only): {', '.join(missing)}", file=sys.stderr)
        return False
    os.environ["HF_HUB_OFFLINE"] = "1"
    # huggingface_hub reads the variable at import: update the already imported constant too.
    try:
        from huggingface_hub import constants

        constants.HF_HUB_OFFLINE = True
    except ImportError:
        pass
    return True


# ---------------------------------------------------------------- the first download

# What a transcription needs, with the files each library reads. mlx-whisper loads the whole
# snapshot; parakeet-mlx only these two files.
SPEECH_FILES = {
    "mlx-community/whisper-large-v3-turbo": None,
    "mlx-community/parakeet-tdt-0.6b-v3": ["config.json", "model.safetensors"],
}
# Measured on 2026-10-16, to say how much will be downloaded before asking (no network yet):
# Whisper 1.61 GB, Parakeet 2.51 GB, the two voice models 33.5 MB.
APPROX_BYTES = 1_613_980_000 + 2_508_533_000 + 33_489_000
DIARIZATION_BYTES = 33_489_000


def _speech_ready() -> bool:
    from huggingface_hub import try_to_load_from_cache

    for repo, files in SPEECH_FILES.items():
        for f in files or ["config.json"]:
            if not isinstance(try_to_load_from_cache(repo, f), str):
                return False
        if files is None and not is_cached(repo):
            return False
    return True


def _diarization_ready() -> bool:
    from parola import diarize

    return not diarize.installed() or diarize.available()


def models_ready() -> bool:
    """Every model a call needs is on disk: nothing will be downloaded."""
    return _speech_ready() and _diarization_ready()


class ModelDownload:
    """The first download, run when the person agrees to it, with its progress for the UI.

    States: ``missing`` (nothing asked yet), ``downloading``, ``error`` (it can be retried; what
    was already downloaded stays), ``ready``."""

    def __init__(self) -> None:
        import threading

        self._lock = threading.Lock()
        self.state = "ready" if models_ready() else "missing"
        self.done = 0
        self.total = APPROX_BYTES
        self.message = ""

    def status(self) -> dict:
        with self._lock:
            if self.state == "missing" and models_ready():
                self.state = "ready"  # downloaded meanwhile, e.g. by `parola transcribe`
            return self._status()

    def _status(self) -> dict:
        return {"state": self.state, "done": self.done, "total": self.total,
                "message": self.message}  # fmt: skip

    def start(self) -> dict:
        import threading

        with self._lock:
            if self.state in ("downloading", "ready"):
                return self._status()
            self.state, self.done, self.message = "downloading", 0, ""
        threading.Thread(target=self._run, daemon=True).start()
        return self.status()

    def _add(self, n: int) -> None:
        with self._lock:
            self.done += int(n)

    def _run(self) -> None:
        try:
            self._download()
            with self._lock:
                self.state, self.done = "ready", self.total
        except Exception as e:  # shown in the UI, with a retry button
            with self._lock:
                self.state, self.message = "error", str(e) or e.__class__.__name__

    def _download(self) -> None:
        from huggingface_hub import hf_hub_download, snapshot_download

        from parola import diarize

        if os.environ.get("HF_HUB_OFFLINE") not in (None, "", "0", "false"):
            raise RuntimeError("HF_HUB_OFFLINE is set: the models cannot be downloaded")
        plan = []  # (repo, filename, size) still to download
        for repo, files in SPEECH_FILES.items():
            for info in snapshot_download(repo, dry_run=True):
                if (files is None or info.filename in files) and info.will_download:
                    plan.append((repo, info.filename, info.file_size or 0))
        voices = DIARIZATION_BYTES if not _diarization_ready() else 0
        with self._lock:
            self.total = sum(size for *_, size in plan) + voices
        progress = _progress_class(self._add)
        for repo, filename, _ in plan:
            hf_hub_download(repo, filename, tqdm_class=progress)
        if voices:
            diarize.ensure_models(self._add)


def _progress_class(add):
    """A stand-in for tqdm that hands each download's bytes to ``add``. It has
    ``update_transfer`` so that huggingface_hub's Xet downloads report one count (bytes written
    to disk), not two."""

    class Progress:
        def __init__(self, *args, total=None, initial=0, **kwargs):
            self.total, self.n = total, initial
            if initial:
                add(initial)

        def update(self, n=1):
            self.n += n or 0
            add(n or 0)

        def update_transfer(self, n=1):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *exc):
            return False

        def __getattr__(self, name):  # set_postfix_str, refresh, close...: nothing to draw
            return lambda *args, **kwargs: None

    return Progress
