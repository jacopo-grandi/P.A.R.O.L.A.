"""Repair WAV headers whose sizes were never written.

AVAudioFile writes a WAV's sizes (the RIFF size and the size of the "data" chunk) when the file
is closed. The capture helper used to exit without closing, so its recordings say their audio is
0 bytes long while the samples are all there. ffmpeg and Chrome read to the end of the file
anyway; WebKit, which draws the native app's window, believes the header and plays nothing
(duration 0). The fix writes the two sizes from the file's real length: 8 bytes, the samples are
never touched.
"""

from __future__ import annotations

import os
import struct
from pathlib import Path

MAX_RIFF = 2**32 - 1  # beyond this a WAV needs RF64, which is not handled here


def _data_chunk(head: bytes) -> int | None:
    """Offset of the "data" chunk header in the first bytes of a RIFF/WAVE file."""
    if head[:4] != b"RIFF" or head[8:12] != b"WAVE":
        return None
    pos = 12
    while pos + 8 <= len(head):
        chunk, size = head[pos : pos + 4], struct.unpack("<I", head[pos + 4 : pos + 8])[0]
        if chunk == b"data":
            return pos
        pos += 8 + size + (size & 1)
    return None


def needs_repair(path: Path) -> bool:
    with path.open("rb") as f:
        head = f.read(65536)
    offset = _data_chunk(head)
    if offset is None:
        return False
    size = os.path.getsize(path)
    stated = struct.unpack("<I", head[offset + 4 : offset + 8])[0]
    return stated != size - offset - 8 and size - 8 <= MAX_RIFF


def repair(path: Path) -> bool:
    """Write the real sizes into ``path``'s header. True if it was changed."""
    if not needs_repair(path):
        return False
    with path.open("r+b") as f:
        head = f.read(65536)
        offset = _data_chunk(head)
        size = os.path.getsize(path)
        f.seek(4)
        f.write(struct.pack("<I", size - 8))
        f.seek(offset + 4)
        f.write(struct.pack("<I", size - offset - 8))
    return True
