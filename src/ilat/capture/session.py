"""A recording started and stopped from the app, transcribed in the background.

One session at a time: ``start`` launches the capture helper with live levels, ``stop`` ends it
and transcribes the call in a thread (same pipeline as ``ilat record``), ``status`` tells the UI
what is happening.
"""

from __future__ import annotations

import contextlib
import json
import re
import signal
import subprocess
import threading
import time
from collections.abc import Callable
from datetime import datetime
from pathlib import Path

from ilat.capture.recorder import Recording, build_helper, transcribe_recording

_NAME = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]*$")


def default_backends() -> tuple:
    from ilat.asr import DEFAULT_MODEL, MLXWhisperBackend
    from ilat.asr.parakeet_backend import PARAKEET_MODEL, ParakeetBackend
    from ilat.models import offline_if_cached

    offline_if_cached([DEFAULT_MODEL, PARAKEET_MODEL])
    return MLXWhisperBackend(vad=True), ParakeetBackend()


class SessionError(RuntimeError):
    pass


class RecordingSession:
    def __init__(self, folder: Path, binary: Path | None = None,
                 backends: Callable[[], tuple] = default_backends) -> None:  # fmt: skip
        self.folder = folder
        self._binary = binary
        self._backends = backends
        self._lock = threading.Lock()
        self._proc: subprocess.Popen | None = None
        self.state = "idle"  # idle | recording | transcribing | done | error
        self.name: str | None = None
        self.language: str | None = None
        self.started: float | None = None
        self.levels: dict[str, float] = {}
        self.message = ""
        self.step = (0, 0)

    # ---------------------------------------------------------------- recording

    def start(self, name: str | None = None, language: str | None = None, mic: bool = True,
              system: bool = True) -> dict:  # fmt: skip
        with self._lock:
            if self.state in ("recording", "transcribing"):
                raise SessionError(f"already {self.state}")
            name = name or datetime.now().strftime("call-%Y%m%d-%H%M%S")
            if not _NAME.match(name) or (self.folder / f"{name}.json").exists():
                raise SessionError(f"invalid or existing name: {name!r}")
            binary = self._binary or build_helper()
            cmd = [str(binary), "--out-dir", str(self.folder), "--name", name, "--levels"]
            if not mic:
                cmd.append("--no-mic")
            if not system:
                cmd.append("--no-system")
            self.folder.mkdir(parents=True, exist_ok=True)
            self._proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                          text=True)  # fmt: skip
            self.state, self.name, self.language = "recording", name, language
            self.started, self.levels, self.message, self.step = time.time(), {}, "", (0, 0)
            threading.Thread(target=self._read_levels, args=(self._proc,), daemon=True).start()
        return self.status()

    def _read_levels(self, proc: subprocess.Popen) -> None:
        tail: list[str] = []
        for line in proc.stderr:
            if line.startswith("LEVELS "):
                with contextlib.suppress(json.JSONDecodeError):
                    self.levels = json.loads(line[7:])
            else:
                tail = [*tail, line.strip()][-5:]
        returncode = proc.wait()
        # The helper ended on its own (not through stop): permission or device problem.
        if self.state == "recording" and proc is self._proc and returncode != 0:
            self.state, self.message = "error", " ".join(tail) or "the capture stopped"

    def stop(self) -> dict:
        with self._lock:
            if self.state != "recording" or self._proc is None:
                raise SessionError("not recording")
            proc = self._proc
            proc.send_signal(signal.SIGINT)
            # stderr is read by the levels thread: read only stdout here.
            out = proc.stdout.read()
            proc.wait(timeout=60)
            self._proc = None
            if proc.returncode != 0:
                self.state, self.message = "error", f"capture exited with {proc.returncode}"
                return self.status()
            capture = json.loads(out)
            self.state, self.levels = "transcribing", {}
            rec = Recording(self.name, self.folder, capture)
            threading.Thread(target=self._transcribe, args=(rec,), daemon=True).start()
        return self.status()

    def _transcribe(self, rec: Recording) -> None:
        def progress(message: str, done: int, total: int) -> None:
            self.message, self.step = message, (done, total)

        try:
            backend, second = self._backends()
            transcribe_recording(rec, backend, self.language, second=second, progress=progress)
            self.state, self.message = "done", ""
        except Exception as e:  # shown in the UI; the audio files stay on disk
            self.state, self.message = "error", f"transcription failed: {e}"

    def abort(self) -> None:
        """Stop the helper without transcribing (server shutdown)."""
        if self._proc is not None and self._proc.poll() is None:
            self._proc.send_signal(signal.SIGINT)
            try:
                self._proc.wait(timeout=10)
            except subprocess.TimeoutExpired:
                self._proc.kill()

    # ---------------------------------------------------------------- status

    def status(self) -> dict:
        elapsed = time.time() - self.started if self.state == "recording" and self.started else 0
        return {
            "state": self.state,
            "name": self.name,
            "elapsed": round(elapsed, 1),
            "levels": self.levels,
            "message": self.message,
            "step": list(self.step),
        }
