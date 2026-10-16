"""Give the memory of the speech models back once they are not needed (decision 0027).

``parola serve`` is a long-running process: mlx-whisper keeps the last model in
``mlx_whisper.transcribe.ModelHolder`` and Parakeet stays in ``parakeet_backend._load``'s cache,
about 2.9 GB together, and MLX keeps freed buffers in its own cache for reuse (about 5 GB after
one transcription). Between calls none of that is useful, and on an 8 GB Mac it pushes the
rest of the system into swap. Loading a model again from the disk cache takes a second or two.
"""

from __future__ import annotations

import gc
import sys


def release_models() -> None:
    """Drop the loaded speech models and MLX's buffer cache. Safe to call at any time: the next
    transcription loads what it needs again."""
    holder = getattr(sys.modules.get("mlx_whisper.transcribe"), "ModelHolder", None)
    if holder is not None:
        holder.model = None
        holder.model_path = None
    parakeet = sys.modules.get("parola.asr.parakeet_backend")
    if parakeet is not None:
        parakeet._load.cache_clear()
    gc.collect()
    release_buffers()


def release_buffers() -> None:
    """Free MLX's cache of buffers no longer in use; the models stay loaded."""
    mx = sys.modules.get("mlx.core")
    if mx is not None:
        mx.clear_cache()
