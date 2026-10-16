"""Local web UI for recorded calls: list, transcript with doubtful words, click to listen.

Everything is served from this machine (no CDN, no external requests) and bound to 127.0.0.1.
A recording is the set of files written by ``ilat record`` in one folder:
``<name>.json`` (merged transcript), ``<name>.mic.wav``, ``<name>.system.wav`` and
``<name>.capture.json``.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse, HTMLResponse, PlainTextResponse
from fastapi.staticfiles import StaticFiles

from ilat.capture.recorder import CHANNELS, LABELS, marked_text, to_dialogue
from ilat.schema import Transcript, format_timestamp

STATIC = Path(__file__).resolve().parent / "static"
_NAME = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]*$")


def _check(name: str) -> str:
    if not _NAME.match(name) or ".." in name:
        raise HTTPException(status_code=404, detail="no such recording")
    return name


def summary(folder: Path, name: str) -> dict:
    t = Transcript.load(folder / f"{name}.json")
    words = [w for s in t.segments for w in s.words]
    capture_path = folder / f"{name}.capture.json"
    capture = json.loads(capture_path.read_text()) if capture_path.exists() else {}
    return {
        "name": name,
        "started_at": capture.get("started_at") or t.metadata.created_at.isoformat(),
        "duration": t.metadata.duration,
        "channels": sorted({s.channel for s in t.segments if s.channel}),
        "segments": len(t.segments),
        "words": len(words),
        "doubtful": sum(w.doubtful for w in words),
        "model": t.metadata.model,
    }


def recordings(folder: Path) -> list[str]:
    """Names of the recordings in ``folder``: transcripts with at least one channel file."""
    names = []
    for p in sorted(folder.glob("*.json")):
        name = p.stem
        if name.endswith(".capture") or not _NAME.match(name):
            continue
        if any((folder / f"{name}.{c}.wav").exists() for c in CHANNELS):
            names.append(name)
    return names


def to_markdown(t: Transcript, name: str) -> str:
    lines = [f"# {name}", ""]
    for s in t.segments:
        label = LABELS.get(s.channel or "", "?")
        lines.append(f"**{label}** · {format_timestamp(s.start)[:8]} — {marked_text(s)}")
        lines.append("")
    return "\n".join(lines)


def create_app(folder: Path) -> FastAPI:
    app = FastAPI(title="ilat", docs_url=None, redoc_url=None, openapi_url=None)

    @app.get("/", response_class=HTMLResponse)
    def index() -> str:
        return (STATIC / "index.html").read_text(encoding="utf-8")

    @app.get("/api/recordings")
    def list_recordings() -> list[dict]:
        out = [summary(folder, n) for n in recordings(folder)]
        return sorted(out, key=lambda r: r["started_at"], reverse=True)

    @app.get("/api/recordings/{name}")
    def get_recording(name: str) -> dict:
        name = _check(name)
        path = folder / f"{name}.json"
        if not path.exists():
            raise HTTPException(status_code=404, detail="no such recording")
        data = json.loads(path.read_text(encoding="utf-8"))
        data["summary"] = summary(folder, name)
        data["audio"] = {c: f"/audio/{name}/{c}" for c in CHANNELS
                         if (folder / f"{name}.{c}.wav").exists()}  # fmt: skip
        return data

    @app.get("/audio/{name}/{channel}")
    def audio(name: str, channel: str) -> FileResponse:
        name = _check(name)
        path = folder / f"{name}.{channel}.wav"
        if channel not in CHANNELS or not path.exists():
            raise HTTPException(status_code=404, detail="no such audio")
        return FileResponse(path, media_type="audio/wav")

    @app.get("/export/{name}.{fmt}")
    def export(name: str, fmt: str):
        name = _check(name)
        path = folder / f"{name}.json"
        if not path.exists() or fmt not in ("txt", "md", "json"):
            raise HTTPException(status_code=404, detail="no such export")
        t = Transcript.load(path)
        headers = {"Content-Disposition": f'attachment; filename="{name}.{fmt}"'}
        if fmt == "json":
            return PlainTextResponse(t.to_json(), media_type="application/json", headers=headers)
        text = to_dialogue(t) if fmt == "txt" else to_markdown(t, name)
        return PlainTextResponse(text, media_type="text/plain; charset=utf-8", headers=headers)

    app.mount("/static", StaticFiles(directory=STATIC), name="static")
    return app
