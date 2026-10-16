"""`parola doctor`: what a bug report needs, in one block to paste into a GitHub issue.

The Mac, macOS, memory and disk, the tools and packages, whether the models and the capture
helper are there, the audio devices in use, and the last errors of the app's engine. Nothing
personal: audio device names are left out (they often hold the owner's name, "AirPods di
Mario"), only their kind and sample rate are shown, and the log lines are only warnings and
errors, to be read before pasting. Every probe is independent: one that fails says so and the
others still run.
"""

from __future__ import annotations

import json
import platform
import re
import shutil
import subprocess
import sys
from collections.abc import Callable
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path

LOG = Path.home() / "Library" / "Logs" / "P.A.R.O.L.A." / "engine.log"
PACKAGES = ("mlx", "mlx-whisper", "parakeet-mlx", "sherpa-onnx", "huggingface-hub", "fastapi")
LOG_LINES = 30
_PROBLEM = re.compile(r"error|warning|traceback|failed|exception", re.IGNORECASE)


def _run(*cmd: str) -> str:
    result = subprocess.run(cmd, capture_output=True, text=True, check=False, timeout=30)
    return result.stdout.strip()


def _sysctl(name: str) -> str:
    return _run("sysctl", "-n", name)


def mac() -> str:
    chip = _sysctl("machdep.cpu.brand_string") or platform.machine()
    memory = int(_sysctl("hw.memsize") or 0) / 2**30
    free = shutil.disk_usage(Path.home()).free / 1e9
    return (f"macOS {platform.mac_ver()[0]} ({_run('sw_vers', '-buildVersion')}), {chip}, "
            f"{memory:.0f} GB memory, {free:.0f} GB free on disk")  # fmt: skip


def software() -> str:
    from parola import __version__

    repo = Path(__file__).resolve().parents[2]
    commit = _run("git", "-C", str(repo), "rev-parse", "--short", "HEAD") or "unknown"
    found = []
    for name in PACKAGES:
        try:
            found.append(f"{name} {version(name)}")
        except PackageNotFoundError:
            found.append(f"{name} missing")
    return (f"P.A.R.O.L.A. {__version__} (commit {commit}), Python {platform.python_version()}; "
            + ", ".join(found))  # fmt: skip


def tools() -> str:
    ffmpeg = shutil.which("ffmpeg")
    ffmpeg_v = _run("ffmpeg", "-version").split("\n")[0].split(" ")[2] if ffmpeg else "missing"
    swift = re.search(r"version (\S+)", _run("swift", "--version") if shutil.which("swift") else "")
    clt = _run("xcode-select", "-p") or "missing"
    return (
        f"ffmpeg {ffmpeg_v}; Swift {swift.group(1) if swift else 'missing'} "
        f"(developer tools: {clt}); uv {'found' if shutil.which('uv') else 'missing'}"
    )


def models() -> str:
    from parola import diarize
    from parola.models import _diarization_ready, _speech_ready

    voices = (
        "voices ready"
        if diarize.available()
        else ("voices missing" if diarize.installed() else "voices: sherpa-onnx missing")
    )
    speech = "speech models ready" if _speech_ready() else "speech models missing"
    return f"{speech}; {voices}" + ("" if _diarization_ready() else " (downloaded on first use)")


def app() -> str:
    """The capture helper, and every copy of the app Spotlight knows (paths with ~ for home)."""
    from parola.capture.recorder import BINARY

    found = _run("mdfind", "kMDItemCFBundleIdentifier == 'dev.parola.app'").splitlines()
    home = str(Path.home())
    copies = ", ".join(sorted(f.replace(home, "~", 1) for f in found if f)) or "none found"
    return f"capture helper {'built' if BINARY.exists() else 'not built yet'}; app: {copies}"


def device_kind(device: dict) -> str:
    """What kind of device, without its name: "Bluetooth (AirPods)", "Built-in", "USB"."""
    transport = str(device.get("coreaudio_device_transport", ""))
    transport = transport.replace("coreaudio_device_type_", "")
    kind = {"builtin": "Built-in", "bluetooth": "Bluetooth", "usb": "USB", "hdmi": "HDMI",
            "displayport": "DisplayPort", "virtual": "Virtual", "aggregate": "Aggregate",
            "airplay": "AirPlay"}.get(transport.lower(), transport or "unknown")  # fmt: skip
    names = " ".join(
        str(device.get(k, ""))
        for k in ("_name", "coreaudio_input_source", "coreaudio_output_source")
    )
    if "airpods" in names.lower():
        kind += " (AirPods)"
    rate = device.get("coreaudio_device_srate")
    return f"{kind}, {int(float(rate))} Hz" if rate else kind


def audio() -> str:
    data = json.loads(_run("system_profiler", "-json", "SPAudioDataType") or "{}")
    devices = [d for group in data.get("SPAudioDataType", []) for d in group.get("_items", [])]
    default_in = next((d for d in devices if d.get("coreaudio_default_audio_input_device")), None)
    default_out = next((d for d in devices if d.get("coreaudio_default_audio_output_device")), None)
    return (
        f"input: {device_kind(default_in) if default_in else 'none'}; "
        f"output: {device_kind(default_out) if default_out else 'none'}"
    )


def log_tail(path: Path = LOG, lines: int = LOG_LINES) -> list[str]:
    """The last warnings and errors of the app's engine."""
    if not path.exists():
        return ["(no engine log yet: the app writes it from its first start)"]
    problems = [ln for ln in path.read_text(errors="replace").splitlines() if _PROBLEM.search(ln)]
    return problems[-lines:] or ["(no warnings or errors)"]


PROBES: list[tuple[str, Callable[[], str]]] = [
    ("Mac", mac), ("Software", software), ("Tools", tools), ("Models", models), ("App", app),
    ("Audio now", audio),
]  # fmt: skip


def report() -> str:
    out = ["### P.A.R.O.L.A. diagnostics", ""]
    for label, probe in PROBES:
        try:
            out.append(f"- **{label}:** {probe()}")
        except Exception as e:  # one probe failing must not hide the others
            out.append(f"- **{label}:** could not check ({e.__class__.__name__}: {e})")
    out += ["", f"Last warnings and errors of the engine ({LOG}):", "", "```"]
    out += log_tail()
    out += ["```", "", "Read the lines above before pasting: they can hold names of your calls."]
    return "\n".join(out)


def main() -> int:
    print(report())
    return 0


if __name__ == "__main__":
    sys.exit(main())
