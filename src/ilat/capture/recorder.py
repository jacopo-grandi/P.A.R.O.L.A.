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
from ilat.schema.vocab import split_punctuation

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


def marked_text(seg: Segment) -> str:
    """Segment text with runs of doubtful words as ``(word word?)``, like uncertain words in the
    annotation format (docs/annotation.md)."""
    if not seg.words:
        return seg.text
    out: list[str] = []
    run: list[str] = []
    for w in [*seg.words, None]:
        if w is not None and w.doubtful:
            run.append(w.text)
            continue
        if run:
            body, punct = split_punctuation(" ".join(run))
            out.append(f"({body}?){punct}")
            run = []
        if w is not None:
            out.append(w.text)
    return " ".join(out)


def to_dialogue(transcript: Transcript) -> str:
    """Readable text with the speaker side of each segment and the doubtful words marked."""
    lines = []
    for line, seg in zip(to_text(transcript).splitlines(), transcript.segments, strict=True):
        label = LABELS.get(seg.channel or "", "?")
        stamp, _, _ = line.partition("] ")
        lines.append(f"{stamp}] {label}: {marked_text(seg)}")
    return "\n".join(lines) + ("\n" if lines else "")


# A mic segment is echo of the other side (headphones leaking into the microphone) when at
# least this share of its words is said by the other side within ECHO_MARGIN_SECONDS.
ECHO_SHARE = 0.6
ECHO_MARGIN_SECONDS = 2.0


def drop_echo(mic: Transcript, system: Transcript) -> int:
    """Remove from ``mic`` the segments that repeat what ``system`` says at the same time."""
    from collections import Counter

    from ilat.eval.normalize import tokenize

    timed: list[tuple[str, float]] = []
    for seg in system.segments:
        for tok in tokenize(seg.words, seg.lang or "it", "fidelity", "hyp"):
            w = seg.words[tok.word_index]
            t = (w.start + w.end) / 2 if w.start is not None and w.end is not None else seg.start
            timed.append((tok.text, t))
    kept, dropped = [], 0
    for seg in mic.segments:
        tokens = [t.text for t in tokenize(seg.words, seg.lang or "it", "fidelity", "hyp")]
        if not tokens:
            kept.append(seg)
            continue
        lo, hi = seg.start - ECHO_MARGIN_SECONDS, seg.end + ECHO_MARGIN_SECONDS
        near = Counter(text for text, t in timed if lo <= t <= hi)
        mine = Counter(tokens)
        shared = sum(min(n, near[text]) for text, n in mine.items())
        if shared / len(tokens) >= ECHO_SHARE:
            dropped += 1
        else:
            kept.append(seg)
    mic.segments = kept
    return dropped


def mark_doubts(primary: Transcript, second: Transcript) -> int:
    """Flag the words of ``primary`` that ``second`` does not confirm; returns how many."""
    from ilat.doubt import doubtful_words

    flagged = doubtful_words(primary, second)
    k = 0
    for seg in primary.segments:
        for w in seg.words:
            w.doubtful = k in flagged
            k += 1
    return len(flagged)


def transcribe_recording(rec: Recording, backend: ASRBackend, language: str | None = None,
                         second: ASRBackend | None = None) -> tuple[Path, Path]:  # fmt: skip
    """Transcribe each channel and write <name>.json and <name>.txt next to the audio.

    With ``second``, each channel is also transcribed by a second system and the words of the
    primary transcript it does not confirm are marked as doubtful. On the test set Parakeet v3
    catches about two thirds of turbo's errors while flagging 12% of the words
    (results/2026-10-16-doubt-analisi.md).
    """
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
        if second is not None:
            other = transcribe_file(rec.path(channel), second, out_dir=work / "second",
                                    language=language).transcript  # fmt: skip
            n = mark_doubts(parts[channel], other)
            total = sum(len(seg.words) for seg in parts[channel].segments)
            print(f"{channel}: {n} doubtful words out of {total}", file=sys.stderr)
        shutil.rmtree(work, ignore_errors=True)
    if "mic" in parts and "system" in parts:
        n = drop_echo(parts["mic"], parts["system"])
        if n:
            print(f"mic: dropped {n} segments that echo the other side", file=sys.stderr)
    # Whisper cuts speech into very short segments: join those of the same side separated by
    # at most 1 s (up to 30 s), as for annotation drafts. Words and their flags do not change.
    from ilat.annotate import merge_segments

    parts = {c: merge_segments(t) for c, t in parts.items()}
    duration = max(rec.capture[c]["seconds"] for c in with_speech)
    merged = merge_channels(parts, f"{rec.name}.*.wav", duration)
    json_path = rec.out_dir / f"{rec.name}.json"
    txt_path = rec.out_dir / f"{rec.name}.txt"
    merged.save(json_path)
    txt_path.write_text(to_dialogue(merged), encoding="utf-8")
    return json_path, txt_path


def main_record(out_dir: Path, name: str | None, backend: ASRBackend, language: str | None,
                duration: float | None, mic: bool, system: bool,
                second: ASRBackend | None = None) -> int:  # fmt: skip
    name = name or datetime.now().strftime("call-%Y%m%d-%H%M%S")
    try:
        print(f"recording {out_dir / name}.*.wav — stop with Ctrl-C", file=sys.stderr)
        rec = record(out_dir, name, duration=duration, mic=mic, system=system)
        for c in rec.channels():
            print(f"{c}: {rec.capture[c]['seconds']:.1f} s", file=sys.stderr)
        json_path, txt_path = transcribe_recording(rec, backend, language, second=second)
    except CaptureError as e:
        print(f"error: {e}", file=sys.stderr)
        return 1
    print(f"wrote {json_path}")
    print(f"wrote {txt_path}")
    return 0
