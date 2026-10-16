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
