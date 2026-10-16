"""Recording from the app, with a fake capture helper and fake ASR backends."""

import stat
import sys
import time
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from ilat.app.server import create_app
from ilat.asr import ASRResult
from ilat.capture.session import RecordingSession, SessionError
from ilat.schema import Segment, Transcript, Word
from tests.conftest import requires_ffmpeg

FAKE_HELPER = '''#!{python}
"""Mimics ilat-capture: levels on stderr until SIGINT, then two tone files and the summary."""
import json, signal, subprocess, sys, time
args = dict(zip(sys.argv[1::2], sys.argv[2::2]))
out, name = args["--out-dir"], args["--name"]
stop = False
def handler(*_):
    global stop
    stop = True
signal.signal(signal.SIGINT, handler)
print("ilat-capture: recording", file=sys.stderr, flush=True)
while not stop:
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
