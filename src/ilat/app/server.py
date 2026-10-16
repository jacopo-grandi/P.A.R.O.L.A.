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
from pydantic import BaseModel

from ilat import editing
from ilat.capture.recorder import CHANNELS, LABELS, marked_text, to_dialogue
from ilat.capture.session import RecordingSession, SessionError
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
        "checked": sum(w.checked for w in words),
        "edits": len(t.edits),
        "model": t.metadata.model,
    }


class RecordRequest(BaseModel):
    name: str | None = None
    lang: str | None = None
    mic: bool = True
    system: bool = True


class Span(BaseModel):
    segment: int
    start: int
    end: int
    text: str | None = None


def recordings(folder: Path) -> list[str]:
    """Names of the recordings in ``folder``: transcripts with at least one channel file."""
    names = []
    for p in sorted(folder.glob("*.json")):
        name = p.stem
        if name.endswith((".capture", ".asr")) or not _NAME.match(name):
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


def create_app(folder: Path, session: RecordingSession | None = None) -> FastAPI:
    from contextlib import asynccontextmanager

    session = session or RecordingSession(folder)

    @asynccontextmanager
    async def lifespan(app):
        yield
        session.abort()  # never leave the capture helper running

    app = FastAPI(title="ilat", docs_url=None, redoc_url=None, openapi_url=None, lifespan=lifespan)

    @app.get("/api/record/status")
    def record_status() -> dict:
        return session.status()

    @app.post("/api/record/start")
    def record_start(req: RecordRequest) -> dict:
        lang = req.lang if req.lang in ("it", "en") else None
        try:
            return session.start(req.name or None, lang, req.mic, req.system)
        except SessionError as e:
            raise HTTPException(status_code=409, detail=str(e)) from e

    @app.post("/api/record/stop")
    def record_stop() -> dict:
        try:
            return session.stop()
        except SessionError as e:
            raise HTTPException(status_code=409, detail=str(e)) from e

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

    def _load(name: str) -> tuple[Transcript, Path]:
        name = _check(name)
        path = folder / f"{name}.json"
        if not path.exists():
            raise HTTPException(status_code=404, detail="no such recording")
        return Transcript.load(path), path

    def _store(t: Transcript, path: Path, name: str) -> dict:
        editing.save(t, path)
        (folder / f"{name}.txt").write_text(to_dialogue(t), encoding="utf-8")
        return get_recording(name)

    @app.post("/api/recordings/{name}/correct")
    def correct(name: str, span: Span) -> dict:
        t, path = _load(name)
        try:
            editing.correct(t, span.segment, span.start, span.end, span.text or "")
        except editing.EditError as e:
            raise HTTPException(status_code=400, detail=str(e)) from e
        return _store(t, path, name)

    @app.post("/api/recordings/{name}/confirm")
    def confirm(name: str, span: Span) -> dict:
        t, path = _load(name)
        try:
            editing.confirm(t, span.segment, span.start, span.end)
        except editing.EditError as e:
            raise HTTPException(status_code=400, detail=str(e)) from e
        return _store(t, path, name)

    @app.post("/api/recordings/{name}/undo")
    def undo(name: str) -> dict:
        t, path = _load(name)
        if editing.undo(t) is None:
            raise HTTPException(status_code=400, detail="nothing to undo")
        return _store(t, path, name)

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
        if not path.exists() or fmt not in ("txt", "md", "json", "docx"):
            raise HTTPException(status_code=404, detail="no such export")
        t = Transcript.load(path)
        headers = {"Content-Disposition": f'attachment; filename="{name}.{fmt}"'}
        if fmt == "json":
            return PlainTextResponse(t.to_json(), media_type="application/json", headers=headers)
        if fmt == "docx":
            from fastapi.responses import Response

            from ilat.app.export import to_docx

            return Response(
                to_docx(t, name),
                headers=headers,
                media_type=(
                    "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
                ),
            )
        text = to_dialogue(t) if fmt == "txt" else to_markdown(t, name)
        return PlainTextResponse(text, media_type="text/plain; charset=utf-8", headers=headers)

    app.mount("/static", StaticFiles(directory=STATIC), name="static")
    return app
