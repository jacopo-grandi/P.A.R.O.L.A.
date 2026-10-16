import json
from datetime import UTC, datetime

import pytest
from fastapi.testclient import TestClient

from ilat.app.server import create_app
from ilat.schema import Metadata, Segment, Transcript, Word


@pytest.fixture
def folder(tmp_path):
    t = Transcript(
        metadata=Metadata(audio_file="call.*.wav", duration=12.0, backend="mlx-whisper",
                          model="turbo", created_at=datetime(2026, 10, 16, tzinfo=UTC),
                          ilat_version="0"),
        segments=[
            Segment(start=0, end=2, text="ciao a tutti", lang="it", channel="mic", words=[
                Word(text="ciao", start=0.1, end=0.4), Word(text="a", start=0.5, end=0.6),
                Word(text="tutti", start=0.7, end=1.2, doubtful=True)]),
            Segment(start=3, end=4, text="buongiorno", lang="it", channel="system",
                    words=[Word(text="buongiorno", start=3.1, end=3.8)]),
        ],
    )  # fmt: skip
    t.save(tmp_path / "call.json")
    (tmp_path / "call.mic.wav").write_bytes(b"RIFF" + b"\0" * 1000)
    (tmp_path / "call.system.wav").write_bytes(b"RIFF" + b"\0" * 1000)
    (tmp_path / "call.capture.json").write_text(json.dumps({"started_at": "2026-10-16T09:00:00Z"}))
    # Not a recording: a transcript without audio files.
    t.save(tmp_path / "other.json")
    return tmp_path


@pytest.fixture
def client(folder):
    return TestClient(create_app(folder))


def test_index_and_static(client):
    assert "ilat" in client.get("/").text
    assert client.get("/static/app.js").status_code == 200


def test_list_recordings(client):
    [rec] = client.get("/api/recordings").json()
    assert rec["name"] == "call" and rec["doubtful"] == 1 and rec["words"] == 4
    assert rec["channels"] == ["mic", "system"] and rec["started_at"] == "2026-10-16T09:00:00Z"


def test_get_recording(client):
    data = client.get("/api/recordings/call").json()
    assert data["audio"] == {"mic": "/audio/call/mic", "system": "/audio/call/system"}
    assert data["segments"][0]["words"][2]["doubtful"] is True


def test_audio_supports_ranges(client):
    r = client.get("/audio/call/mic", headers={"Range": "bytes=0-3"})
    assert r.status_code == 206 and r.content == b"RIFF"


def test_exports(client):
    txt = client.get("/export/call.txt")
    assert "Io: ciao a (tutti?)" in txt.text
    assert 'filename="call.txt"' in txt.headers["content-disposition"]
    assert "**Altri**" in client.get("/export/call.md").text
    assert client.get("/export/call.json").json()["metadata"]["model"] == "turbo"


@pytest.mark.parametrize(
    "url",
    [
        "/api/recordings/..%2Fsecret",
        "/api/recordings/missing",
        "/audio/call/other",
        "/audio/..%2Fx/mic",
        "/export/call.pdf",
    ],
)
def test_bad_paths_are_404(client, url):
    assert client.get(url).status_code == 404
