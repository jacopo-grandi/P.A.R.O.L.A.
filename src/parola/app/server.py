"""Local web UI for recorded calls: list, transcript with doubtful words, click to listen.

Everything is served from this machine (no CDN, no external requests) and bound to 127.0.0.1.
A recording is the set of files written by ``parola record`` in one folder:
``<name>.json`` (merged transcript), ``<name>.mic.wav``, ``<name>.system.wav`` and
``<name>.capture.json``.
"""

from __future__ import annotations

import json
import re
import shutil
from datetime import UTC, datetime
from pathlib import Path
from urllib.parse import quote

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse, HTMLResponse, PlainTextResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from parola import editing
from parola.capture.recorder import CHANNELS, LABELS, marked_text, to_dialogue
from parola.capture.session import RecordingSession, SessionError
from parola.schema import Transcript, format_timestamp

STATIC = Path(__file__).resolve().parent / "static"
_NAME = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]*$")
# Deleted calls are moved here, one folder per deletion, never removed by the app (decision 0017).
TRASH = ".trash"
_TRASHED = re.compile(r"^([A-Za-z0-9][A-Za-z0-9._-]*)--\d{8}-\d{6}-\d{6}$")
# Every file a recording owns. Listed, not globbed: "prova.*" would also catch "prova.2.json".
OWNED = (".json", ".asr.json", ".capture.json", ".txt", ".mic.wav", ".system.wav", ".mixed.wav")


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
        # No title yet: an imported file shows its own name ("Intervista Marco"), not the slug.
        "title": t.metadata.title
        or (Path(capture["source"]).stem if capture.get("source") else name),
        "source": capture.get("source"),  # name of the imported file, if it was one
        "started_at": capture.get("started_at") or t.metadata.created_at.isoformat(),
        "duration": t.metadata.duration,
        "channels": sorted({s.channel for s in t.segments if s.channel}),
        "segments": len(t.segments),
        "words": len(words),
        "doubtful": sum(w.doubtful for w in words),
        "to_review": len(editing.doubt_runs(t)),  # runs of doubtful words, as the UI counts them
        "checked": sum(w.checked for w in words),
        "edits": len(t.edits),
        "model": t.metadata.model,
    }


class RecordRequest(BaseModel):
    name: str | None = None
    lang: str | None = None
    mic: bool = True
    system: bool = True


class Rename(BaseModel):
    title: str


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


# Audio and video that ffmpeg reads; anything else is refused before it is uploaded.
IMPORT_EXTENSIONS = frozenset([
    ".m4a", ".mp3", ".wav", ".aac", ".flac", ".ogg", ".opus", ".oga", ".webm", ".aiff", ".aif",
    ".caf", ".wma", ".amr", ".mp4", ".mov", ".m4v", ".mkv", ".avi",
])  # fmt: skip


def owned_files(folder: Path, name: str) -> list[Path]:
    return [folder / f"{name}{s}" for s in OWNED if (folder / f"{name}{s}").exists()]


def to_markdown(t: Transcript, name: str) -> str:
    lines = [f"# {name}", ""]
    for s in t.segments:
        label = LABELS.get(s.channel or "", "?")
        who = f"**{label}** · " if label else ""
        lines.append(f"{who}{format_timestamp(s.start)[:8]} — {marked_text(s)}")
        lines.append("")
    return "\n".join(lines)


def create_app(folder: Path, session: RecordingSession | None = None) -> FastAPI:
    from contextlib import asynccontextmanager

    session = session or RecordingSession(folder)

    @asynccontextmanager
    async def lifespan(app):
        yield
        session.abort()  # never leave the capture helper running

    app = FastAPI(
        title="parola", docs_url=None, redoc_url=None, openapi_url=None, lifespan=lifespan
    )

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

    @app.post("/api/record/{action}")
    def record_control(action: str) -> dict:
        controls = {"stop": session.stop, "pause": session.pause, "resume": session.resume}
        if action not in controls:
            raise HTTPException(status_code=404, detail="no such action")
        try:
            return controls[action]()
        except SessionError as e:
            raise HTTPException(status_code=409, detail=str(e)) from e

    @app.post("/api/import")
    async def import_file(request: Request, filename: str, lang: str | None = None,
                          modified: int | None = None) -> dict:  # fmt: skip
        """Body = the raw file. ``modified`` (ms) is the file's date, used as the call's date."""
        ext = Path(filename).suffix.lower()
        if ext not in IMPORT_EXTENSIONS:
            raise HTTPException(status_code=415, detail=f"not an audio or video file: {filename}")
        if session.status()["state"] in ("recording", "transcribing"):
            raise HTTPException(status_code=409, detail=f"already {session.status()['state']}")
        uploads = folder / ".uploads"
        uploads.mkdir(parents=True, exist_ok=True)
        tmp = uploads / f"{datetime.now():%Y%m%d-%H%M%S-%f}{ext}"
        with tmp.open("wb") as f:
            async for chunk in request.stream():
                f.write(chunk)
        started = datetime.fromtimestamp(modified / 1000, UTC) if modified else None
        language = lang if lang in ("it", "en") else None
        try:
            return session.import_file(tmp, Path(filename).name, language, started)
        except SessionError as e:
            tmp.unlink(missing_ok=True)
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

    @app.post("/api/recordings/{name}/rename")
    def rename(name: str, req: Rename) -> dict:
        t, path = _load(name)
        title = " ".join(req.title.split())[:120]
        t.metadata.title = title or None
        t.save(path)  # a display change: not an edit of the transcript, no .asr.json needed
        return get_recording(name)

    @app.delete("/api/recordings/{name}")
    def delete(name: str) -> dict:
        """Move the call's files to the trash folder: the app never deletes audio for real."""
        _load(name)
        st = session.status()
        if st["name"] == name and st["state"] in ("recording", "transcribing"):
            raise HTTPException(status_code=409, detail="the call is still being recorded")
        entry = f"{name}--{datetime.now():%Y%m%d-%H%M%S-%f}"
        dest = folder / TRASH / entry
        dest.mkdir(parents=True)
        for f in owned_files(folder, name):
            shutil.move(f, dest / f.name)
        return {"name": name, "trashed": entry}

    @app.post("/api/trash/{entry}/restore")
    def restore(entry: str) -> dict:
        m = _TRASHED.match(entry)
        src = folder / TRASH / entry
        if not m or not src.is_dir():
            raise HTTPException(status_code=404, detail="not in the trash")
        name = m.group(1)
        if (folder / f"{name}.json").exists():
            raise HTTPException(status_code=409, detail=f"a call named {name} exists")
        for f in src.iterdir():
            shutil.move(f, folder / f.name)
        src.rmdir()
        return summary(folder, name)

    @app.get("/api/recordings/{name}/title-suggestion")
    def title_suggestion(name: str) -> dict:
        """A title from the call's key phrases; nothing is saved (decision 0020)."""
        from parola.keywords import key_phrases, suggest_title

        t, _ = _load(name)
        return {"title": suggest_title(t), "phrases": [p.text for p in key_phrases(t, 8)]}

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
        title = t.metadata.title or name
        # The file is named after the title the user gave; plain name as the ASCII fallback.
        stem = re.sub(r'[\\/:*?"<>|\x00-\x1f]', "", title).strip() or name
        disposition = f"attachment; filename=\"{name}.{fmt}\"; filename*=UTF-8''{quote(stem)}.{fmt}"
        headers = {"Content-Disposition": disposition}
        if fmt == "json":
            return PlainTextResponse(t.to_json(), media_type="application/json", headers=headers)
        if fmt == "docx":
            from fastapi.responses import Response

            from parola.app.export import to_docx

            return Response(
                to_docx(t, title),
                headers=headers,
                media_type=(
                    "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
                ),
            )
        text = to_dialogue(t) if fmt == "txt" else to_markdown(t, title)
        return PlainTextResponse(text, media_type="text/plain; charset=utf-8", headers=headers)

    app.mount("/static", StaticFiles(directory=STATIC), name="static")
    return app
