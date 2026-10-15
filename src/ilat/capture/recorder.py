"""Record a call (microphone + system audio) and transcribe it per channel.

Capture is done by the Swift helper ``ilat-capture`` (Core Audio process taps, decision 0013),
built on first use with ``swiftc``. Each channel is transcribed separately and the two are
merged into one transcript whose segments carry ``channel`` = ``mic`` (you) or ``system``
(the others): turns are separated by channel, not guessed.
"""

from __future__ import annotations

import json
import shutil
import signal
import subprocess
import sys
import tempfile
import wave
from array import array
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

from ilat import __version__
from ilat.asr import ASRBackend
from ilat.audio import extract_audio
from ilat.pipeline import transcribe_file
from ilat.schema import Metadata, Segment, Transcript, to_text

REPO_ROOT = Path(__file__).resolve().parents[3]
SWIFT_DIR = Path(__file__).resolve().parent / "swift"
BINARY = REPO_ROOT / "bin" / "ilat-capture"
CHANNELS = ("mic", "system")
# Peak below this (16-bit PCM) means digital silence: macOS returns zeros instead of an error
# when the permission to record system audio is missing.
SILENCE_PEAK = 8
PERMISSION_HINT = {
    "mic": "System Settings > Privacy & Security > Microphone",
    "system": "System Settings > Privacy & Security > Screen & System Audio Recording "
    "(System Audio Recording Only)",
}


class CaptureError(RuntimeError):
    pass


def build_helper(force: bool = False) -> Path:
    """Compile the Swift helper if it is missing or older than its sources."""
    sources = [SWIFT_DIR / "main.swift", SWIFT_DIR / "Info.plist"]
    newest = max(s.stat().st_mtime for s in sources)
    if BINARY.exists() and not force and BINARY.stat().st_mtime >= newest:
        return BINARY
    if shutil.which("swiftc") is None:
        raise CaptureError("swiftc not found: install the Xcode Command Line Tools")
    BINARY.parent.mkdir(parents=True, exist_ok=True)
    cmd = [
        "swiftc", "-O", "-swift-version", "5", str(sources[0]), "-o", str(BINARY),
        "-Xlinker", "-sectcreate", "-Xlinker", "__TEXT", "-Xlinker", "__info_plist",
        "-Xlinker", str(sources[1]),
    ]  # fmt: skip
    result = subprocess.run(cmd, capture_output=True, text=True, check=False)
    if result.returncode != 0:
        raise CaptureError(f"building ilat-capture failed:\n{result.stderr}")
    return BINARY


@dataclass
class Recording:
    name: str
    out_dir: Path
    capture: dict

    def path(self, channel: str) -> Path:
        return self.out_dir / f"{self.name}.{channel}.wav"

    def channels(self) -> list[str]:
        return [c for c in CHANNELS if c in self.capture and self.path(c).exists()]


def record(out_dir: Path, name: str, duration: float | None = None, mic: bool = True,
           system: bool = True) -> Recording:  # fmt: skip
    """Run the helper until ``duration`` elapses or the user presses Ctrl-C."""
    binary = build_helper()
    cmd = [str(binary), "--out-dir", str(out_dir), "--name", name]
    if duration:
        cmd += ["--duration", str(duration)]
    if not mic:
        cmd.append("--no-mic")
    if not system:
        cmd.append("--no-system")
    proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, text=True)
    try:
        out, _ = proc.communicate()
    except KeyboardInterrupt:
        # Ctrl-C reaches the helper too (same process group); wait for it to close the files.
        proc.send_signal(signal.SIGINT)
        out, _ = proc.communicate()
    if proc.returncode != 0:
        raise CaptureError(f"ilat-capture exited with {proc.returncode}")
    return Recording(name, out_dir, json.loads(out))


def peak(path: Path) -> int:
    """Peak absolute sample (16-bit scale) of an audio file."""
    with tempfile.TemporaryDirectory(prefix="ilat-peak-") as tmp:
        wav = extract_audio(path, Path(tmp) / "a.wav")
        with wave.open(str(wav), "rb") as f:
            samples = array("h", f.readframes(f.getnframes()))
    return max((abs(x) for x in samples), default=0)


def merge_channels(parts: dict[str, Transcript], audio_file: str, duration: float) -> Transcript:
    """One transcript with the segments of every channel, sorted by time."""
    segments: list[Segment] = []
    for channel, t in parts.items():
        for s in t.segments:
            segments.append(s.model_copy(update={"channel": channel}))
    segments.sort(key=lambda s: (s.start, CHANNELS.index(s.channel or "mic")))
    first = next(iter(parts.values()))
    return Transcript(
        metadata=Metadata(
            kind="asr",
            audio_file=audio_file,
            duration=duration,
            backend=first.metadata.backend,
            model=first.metadata.model,
            language_requested=first.metadata.language_requested,
            language_detected=first.metadata.language_detected,
            created_at=datetime.now(UTC),
            ilat_version=__version__,
        ),
        segments=segments,
    )


LABELS = {"mic": "Io", "system": "Altri"}


def to_dialogue(transcript: Transcript) -> str:
    """Readable text with the speaker side of each segment."""
    lines = []
    for line, seg in zip(to_text(transcript).splitlines(), transcript.segments, strict=True):
        label = LABELS.get(seg.channel or "", "?")
        stamp, _, text = line.partition("] ")
        lines.append(f"{stamp}] {label}: {text}")
    return "\n".join(lines) + ("\n" if lines else "")


def transcribe_recording(rec: Recording, backend: ASRBackend, language: str | None = None
                         ) -> tuple[Path, Path]:  # fmt: skip
    """Transcribe each channel and write <name>.json and <name>.txt next to the audio."""
    parts: dict[str, Transcript] = {}
    with_speech = []
    for c in rec.channels():
        if rec.capture[c].get("seconds", 0) <= 0:
            continue
        if peak(rec.path(c)) < SILENCE_PEAK:
            # Transcribing silence makes Whisper invent text ("Thank you."): skip it.
            print(f"warning: the {c} channel is silent; if that is unexpected, check "
                  f"{PERMISSION_HINT[c]}", file=sys.stderr)  # fmt: skip
            continue
        with_speech.append(c)
    if not with_speech:
        raise CaptureError("every channel is silent: nothing to transcribe")
    for channel in with_speech:
        work = rec.out_dir / f".{rec.name}.{channel}"
        out = transcribe_file(rec.path(channel), backend, out_dir=work, language=language)
        parts[channel] = out.transcript
        shutil.rmtree(work, ignore_errors=True)
    duration = max(rec.capture[c]["seconds"] for c in with_speech)
    merged = merge_channels(parts, f"{rec.name}.*.wav", duration)
    json_path = rec.out_dir / f"{rec.name}.json"
    txt_path = rec.out_dir / f"{rec.name}.txt"
    merged.save(json_path)
    txt_path.write_text(to_dialogue(merged), encoding="utf-8")
    return json_path, txt_path


def main_record(out_dir: Path, name: str | None, backend: ASRBackend, language: str | None,
                duration: float | None, mic: bool, system: bool) -> int:  # fmt: skip
    name = name or datetime.now().strftime("call-%Y%m%d-%H%M%S")
    try:
        print(f"recording {out_dir / name}.*.wav — stop with Ctrl-C", file=sys.stderr)
        rec = record(out_dir, name, duration=duration, mic=mic, system=system)
        for c in rec.channels():
            print(f"{c}: {rec.capture[c]['seconds']:.1f} s", file=sys.stderr)
        json_path, txt_path = transcribe_recording(rec, backend, language)
    except CaptureError as e:
        print(f"error: {e}", file=sys.stderr)
        return 1
    print(f"wrote {json_path}")
    print(f"wrote {txt_path}")
    return 0
