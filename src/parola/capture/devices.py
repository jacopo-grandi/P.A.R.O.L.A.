"""The Mac's audio output devices, through the capture helper (CoreAudio).

The app's playback is plain ``<audio>`` in the WebView, which follows the system default
output; WebKit has no ``setSinkId``, so choosing where to listen means switching the Mac's
default output, exactly what Control Center's switcher does.
"""

from __future__ import annotations

import json
import subprocess

from parola.capture.recorder import CaptureError, build_helper


def outputs() -> list[dict]:
    """Every output device, as ``{uid, name, kind, current}`` rows."""
    out = _run("--outputs")
    return json.loads(out)


def set_output(uid: str) -> None:
    """Make ``uid`` the Mac's default output (all audio moves there, not just the app's)."""
    _run("--set-output", uid)


def _run(*args: str) -> str:
    result = subprocess.run([str(build_helper()), *args], capture_output=True, text=True,
                            check=False)  # fmt: skip
    if result.returncode != 0:
        raise CaptureError(result.stderr.strip() or f"parola-capture {args[0]} failed")
    return result.stdout
