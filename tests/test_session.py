"""Recording from the app, with a fake capture helper and fake ASR backends."""

import json
import stat
import sys
import time
from datetime import UTC, datetime
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from parola.app.server import create_app
from parola.asr import ASRResult
from parola.capture.session import RecordingSession, SessionError
from parola.schema import Segment, Transcript, Word
from tests.conftest import requires_ffmpeg

FAKE_HELPER = '''#!{python}
"""Mimics parola-capture: levels on stderr until SIGINT, then two tone files and the summary."""
import json, signal, subprocess, sys, time
args = dict(zip(sys.argv[1::2], sys.argv[2::2]))
out, name = args["--out-dir"], args["--name"]
stop = paused = False
def handler(*_):
    global stop
    stop = True
def pause(sig, _):
    global paused
    paused = sig == signal.SIGUSR1
signal.signal(signal.SIGINT, handler)
signal.signal(signal.SIGUSR1, pause)
signal.signal(signal.SIGUSR2, pause)
print("parola-capture: recording", file=sys.stderr, flush=True)
while not stop:
    if not paused:
        print('LEVELS {{"mic": -20.0, "system": -12.5}}', file=sys.stderr, flush=True)
    time.sleep(0.05)
for c in ("mic", "system"):
    subprocess.run(["ffmpeg", "-nostdin", "-loglevel", "error", "-y", "-f", "lavfi", "-i",
                    "sine=frequency=440:duration=1", f"{{out}}/{{name}}.{{c}}.wav"], check=True)
print(json.dumps({{"mic": {{"seconds": 1.0}}, "system": {{"seconds": 1.0}}}}))
'''


class Fake:
    name, model = "fake", "m"

    def __init__(self, text):
        self.text = text

    def transcribe(self, wav_path, language=None):
        words = [
            Word(text=t, start=0.1 * k, end=0.1 * k + 0.08) for k, t in enumerate(self.text.split())
        ]
        return ASRResult(segments=[Segment(start=0, end=1, text=self.text, lang="it", words=words)],
                         language="it")  # fmt: skip


@pytest.fixture
def helper(tmp_path):
    path = tmp_path / "fake-capture"
    path.write_text(FAKE_HELPER.format(python=sys.executable))
    path.chmod(path.stat().st_mode | stat.S_IEXEC)
    return path


def wait_for(session, state, timeout=20):
    deadline = time.time() + timeout
    while session.status()["state"] != state and time.time() < deadline:
        time.sleep(0.05)
    return session.status()


@requires_ffmpeg
def test_session_records_and_transcribes(tmp_path, helper):
    folder = tmp_path / "calls"
    backends = lambda: (Fake("ciao a tutti"), Fake("ciao a voi"))  # noqa: E731
    session = RecordingSession(folder, binary=helper, backends=backends)
    st = session.start(name="riunione")
    assert st["state"] == "recording" and st["name"] == "riunione"
    time.sleep(0.4)
    assert session.status()["levels"] == {"mic": -20.0, "system": -12.5}
    with pytest.raises(SessionError):
        session.start()
    with pytest.raises(SessionError):
        session.resume()
    st = session.pause()
    assert st["paused"] and st["levels"] == {}
    time.sleep(0.3)
    assert session.status()["elapsed"] == st["elapsed"]  # the clock stops while paused
    with pytest.raises(SessionError):
        session.pause()
    assert not session.resume()["paused"]
    assert session.stop()["state"] == "transcribing"
    st = wait_for(session, "done")
    assert st["state"] == "done", st
    t = Transcript.load(folder / "riunione.json")
    words = [w for s in t.segments for w in s.words]
    # Both fake channels say the same thing at the same time: the mic one is dropped as echo.
    assert {s.channel for s in t.segments} == {"system"}
    assert any(w.doubtful for w in words)  # "tutti" is not confirmed by the second opinion
    with pytest.raises(SessionError):
        session.stop()


def test_bad_names_are_refused(tmp_path, helper):
    (tmp_path / "taken.json").write_text("{}")
    session = RecordingSession(tmp_path, binary=helper, backends=lambda: (None, None))
    for name in ("../x", "taken"):
        with pytest.raises(SessionError):
            session.start(name=name)


@requires_ffmpeg
def test_api_start_status_stop(tmp_path, helper):
    backends = lambda: (Fake("buongiorno"), Fake("buongiorno"))  # noqa: E731
    session = RecordingSession(tmp_path, binary=helper, backends=backends)
    client = TestClient(create_app(tmp_path, session=session))
    assert client.get("/api/record/status").json()["state"] == "idle"
    assert (
        client.post("/api/record/start", json={"name": "c1", "lang": "it"}).json()["state"]
        == "recording"
    )
    assert client.post("/api/record/start", json={}).status_code == 409
    time.sleep(0.3)
    assert client.post("/api/record/pause").json()["paused"]
    assert client.post("/api/record/pause").status_code == 409
    assert not client.post("/api/record/resume").json()["paused"]
    assert client.post("/api/record/rewind").status_code == 404
    assert client.post("/api/record/stop").json()["state"] == "transcribing"
    assert wait_for(session, "done")["state"] == "done"
    assert [r["name"] for r in client.get("/api/recordings").json()] == ["c1"]
    assert client.post("/api/record/stop").status_code == 409


def test_helper_failure_is_reported(tmp_path):
    failing = tmp_path / "fail"
    failing.write_text(
        f"#!{sys.executable}\nimport sys\nprint('no permission', file=sys.stderr)\nsys.exit(1)\n"
    )
    failing.chmod(failing.stat().st_mode | stat.S_IEXEC)
    session = RecordingSession(tmp_path, binary=Path(failing), backends=lambda: (None, None))
    session.start(name="x")
    st = wait_for(session, "error", timeout=5)
    assert st["state"] == "error" and "no permission" in st["message"]


def tone(path: Path, seconds: int = 1) -> Path:
    import subprocess

    subprocess.run(["ffmpeg", "-nostdin", "-loglevel", "error", "-y", "-f", "lavfi", "-i",
                    f"sine=frequency=440:duration={seconds}", str(path)], check=True)  # fmt: skip
    return path


@requires_ffmpeg
def test_import_a_file_like_a_recording(tmp_path, helper):
    folder = tmp_path / "calls"
    folder.mkdir()
    backends = lambda: (Fake("ciao a tutti"), Fake("ciao a voi"))  # noqa: E731
    session = RecordingSession(folder, binary=helper, backends=backends)
    upload = tone(tmp_path / "upload.m4a")
    started = datetime(2026, 10, 1, 9, 30, tzinfo=UTC)
    st = session.import_file(upload, "Intervista Marco (1).m4a", "it", started)
    assert st["state"] == "transcribing" and st["name"] == "Intervista-Marco-1"
    with pytest.raises(SessionError):
        session.start()
    assert wait_for(session, "done")["state"] == "done"
    t = Transcript.load(folder / "Intervista-Marco-1.json")
    assert {s.channel for s in t.segments} == {"mixed"}
    assert any(w.doubtful for s in t.segments for w in s.words)
    capture = json.loads((folder / "Intervista-Marco-1.capture.json").read_text())
    assert capture["source"] == "Intervista Marco (1).m4a"
    assert capture["started_at"].startswith("2026-10-01T09:30")
    assert (folder / "Intervista-Marco-1.mixed.wav").exists() and not upload.exists()
    assert "] ciao a (tutti?)" in (folder / "Intervista-Marco-1.txt").read_text()  # no side label
    assert session.free_name("Intervista Marco (1).m4a") == "Intervista-Marco-1-2"


@requires_ffmpeg
def test_a_file_without_audio_is_reported(tmp_path, helper):
    session = RecordingSession(tmp_path, binary=helper, backends=lambda: (None, None))
    bad = tmp_path / "notes.m4a"
    bad.write_text("not audio")
    session.import_file(bad, "notes.m4a")
    st = wait_for(session, "error", timeout=10)
    assert st["state"] == "error" and st["message"].startswith("import failed")
    assert not list(tmp_path.glob("*.mixed.wav")) and not bad.exists()


@requires_ffmpeg
def test_api_import(tmp_path, helper):
    backends = lambda: (Fake("buongiorno a tutti"), Fake("buongiorno a tutti"))  # noqa: E731
    session = RecordingSession(tmp_path, binary=helper, backends=backends)
    client = TestClient(create_app(tmp_path, session=session))
    assert client.post("/api/import?filename=notes.txt", content=b"x").status_code == 415
    audio = tone(tmp_path / "src.mp3").read_bytes()
    r = client.post("/api/import?filename=riunione.mp3&modified=1790000000000&lang=it",
                    content=audio)  # fmt: skip
    assert r.json()["state"] == "transcribing" and r.json()["name"] == "riunione"
    assert client.post("/api/import?filename=altra.mp3", content=audio).status_code == 409
    assert wait_for(session, "done")["state"] == "done"
    rec = client.get("/api/recordings/riunione").json()
    assert rec["summary"]["source"] == "riunione.mp3"
    assert list(rec["audio"]) == ["mixed"]
    assert client.get("/audio/riunione/mixed").status_code == 200
    assert not list((tmp_path / ".uploads").iterdir())
    md = client.get("/export/riunione.md").text
    assert "**" not in md.split("\n", 2)[2]  # no side label on a single-track file
