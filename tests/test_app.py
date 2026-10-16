import json
from datetime import UTC, datetime

import pytest
from fastapi.testclient import TestClient

from parola.app.server import create_app
from parola.schema import Metadata, Segment, Transcript, Word


@pytest.fixture
def folder(tmp_path):
    t = Transcript(
        metadata=Metadata(audio_file="call.*.wav", duration=12.0, backend="mlx-whisper",
                          model="turbo", created_at=datetime(2026, 10, 16, tzinfo=UTC),
                          parola_version="0"),
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
    assert "P.A.R.O.L.A." in client.get("/").text
    assert client.get("/static/app.js").status_code == 200


def test_list_recordings(client):
    [rec] = client.get("/api/recordings").json()
    assert rec["name"] == "call" and rec["doubtful"] == 1 and rec["words"] == 4
    assert rec["to_review"] == 1
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


def test_correct_confirm_undo_endpoints(client, folder):
    r = client.post("/api/recordings/call/correct",
                    json={"segment": 0, "start": 2, "end": 3, "text": "tutto"})  # fmt: skip
    assert r.status_code == 200
    data = r.json()
    assert data["segments"][0]["text"] == "ciao a tutto"
    assert data["summary"]["doubtful"] == 0 and data["summary"]["edits"] == 1
    assert (folder / "call.asr.json").exists()
    assert "Io: ciao a tutto" in (folder / "call.txt").read_text()
    r = client.post("/api/recordings/call/confirm", json={"segment": 1, "start": 0, "end": 1})
    assert r.json()["summary"]["checked"] == 2
    assert client.post("/api/recordings/call/undo").json()["summary"]["edits"] == 1
    assert client.post("/api/recordings/call/undo").json()["segments"][0]["text"] == "ciao a tutti"
    assert client.post("/api/recordings/call/undo").status_code == 400
    assert (
        client.post(
            "/api/recordings/call/correct", json={"segment": 5, "start": 0, "end": 1, "text": "x"}
        ).status_code
        == 400
    )
    # The kept model output is not listed as a recording.
    assert [r["name"] for r in client.get("/api/recordings").json()] == ["call"]


def test_docx_export(client):
    r = client.get("/export/call.docx")
    assert r.status_code == 200 and r.content[:2] == b"PK"
    from io import BytesIO

    from docx import Document

    doc = Document(BytesIO(r.content))
    text = "\n".join(p.text for p in doc.paragraphs)
    assert "ciao a tutti" in text and "buongiorno" in text


def test_rename(client):
    r = client.post("/api/recordings/call/rename", json={"title": "  Riunione   LED Q4 "})
    assert r.json()["summary"]["title"] == "Riunione LED Q4"
    assert client.get("/api/recordings").json()[0]["title"] == "Riunione LED Q4"
    assert (
        client.post("/api/recordings/call/rename", json={"title": ""}).json()["summary"]["title"]
        == "call"
    )


def test_exports_are_named_after_the_title(client):
    client.post("/api/recordings/call/rename", json={"title": "Riunione: LED/Q4"})
    r = client.get("/export/call.md")
    disposition = r.headers["content-disposition"]
    assert 'filename="call.md"' in disposition
    assert "filename*=UTF-8''Riunione%20LEDQ4.md" in disposition
    assert r.text.startswith("# Riunione: LED/Q4")


def test_delete_moves_the_call_to_the_trash_and_restore_brings_it_back(client, folder):
    (folder / "call.txt").write_text("x")
    (folder / "call.2.json").write_text("{}")  # another recording's file: must not move
    r = client.delete("/api/recordings/call")
    entry = r.json()["trashed"]
    assert client.get("/api/recordings").json() == []
    moved = sorted(p.name for p in (folder / ".trash" / entry).iterdir())
    assert moved == [
        "call.capture.json",
        "call.json",
        "call.mic.wav",
        "call.system.wav",
        "call.txt",
    ]
    assert (folder / "call.2.json").exists() and (folder / "other.json").exists()
    assert client.delete("/api/recordings/call").status_code == 404
    assert client.post(f"/api/trash/{entry}/restore").json()["name"] == "call"
    assert [r["name"] for r in client.get("/api/recordings").json()] == ["call"]
    assert not (folder / ".trash" / entry).exists()
    assert client.post(f"/api/trash/{entry}/restore").status_code == 404
    assert client.post("/api/trash/..--x/restore").status_code == 404


def test_title_suggestion_saves_nothing(client, folder):
    before = (folder / "call.json").read_text()
    r = client.get("/api/recordings/call/title-suggestion").json()
    assert r["title"] is None  # four words: too short for a title
    assert r["phrases"] == []  # "ciao", "buongiorno": greetings, not topics
    assert (folder / "call.json").read_text() == before


def test_search_across_calls(client):
    r = client.get("/api/search", params={"q": "TUTTI"}).json()
    assert [c["name"] for c in r] == ["call"] and r[0]["count"] == 1
    hit = r[0]["hits"][0]
    assert (hit["segment"], hit["word"], hit["match"], hit["before"]) == (0, 2, "tutti", "ciao a")
    assert client.get("/api/search", params={"q": "assente"}).json() == []
    assert client.get("/api/search", params={"q": " "}).json() == []
    client.post("/api/recordings/call/rename", json={"title": "Cena di sabato"})
    r = client.get("/api/search", params={"q": "sabato"}).json()
    assert r[0]["count"] == 0 and r[0]["title"] == "Cena di sabato"  # found by its title


def test_a_compressed_call_is_listed_and_played(client, folder):
    for c in ("mic", "system"):
        (folder / f"call.{c}.wav").rename(folder / f"call.{c}.flac")
    assert [r["name"] for r in client.get("/api/recordings").json()] == ["call"]
    assert set(client.get("/api/recordings/call").json()["audio"]) == {"mic", "system"}
    r = client.get("/audio/call/mic")
    assert r.status_code == 200 and r.headers["content-type"] == "audio/flac"
    assert client.get("/audio/call/nope").status_code == 404


def test_suggestions_come_only_from_your_own_corrections(client):
    assert client.get("/api/suggestions", params={"text": "tutti"}).json() == []  # starts empty
    client.post("/api/recordings/call/correct", json={"segment": 0, "start": 2, "end": 3,
                                                      "text": "Orto-Lab"})  # fmt: skip
    assert client.get("/api/suggestions", params={"text": "tutti"}).json() == []  # once: not yet
    client.post("/api/recordings/call/correct", json={"segment": 0, "start": 0, "end": 1,
                                                      "text": "Orto-Lab"})  # fmt: skip
    (s,) = client.get("/api/suggestions", params={"text": "tutti"}).json()
    assert (s["term"], s["count"], s["exact"]) == ("Orto-Lab", 2, True)
    rec = client.get("/api/recordings/call").json()
    assert rec["segments"][0]["text"] == "Orto-Lab a Orto-Lab"  # nothing changed by itself
