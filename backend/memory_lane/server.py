import json
import subprocess
import sys
import threading
from datetime import datetime, timezone
from pathlib import Path

from .database import connect, utcnow
from .library import canonical_root, scan_root
from .paths import suggested_pictures
from .previews import ensure_preview
from .selection import select_next_photo

MAX_FRAME_BYTES = 16 * 1024
MAX_NOTE_BYTES = 8 * 1024


class ApiError(Exception):
    def __init__(self, code, message):
        self.code, self.message = code, message


class Server:
    def __init__(self, db_path=None, inp=None, out=None):
        self.db_path = db_path
        self.db = connect(db_path)
        self.inp = inp or sys.stdin
        self.out = out or sys.stdout
        self.write_lock = threading.Lock()
        self.scan_running = False

    def emit(self, value):
        frame = json.dumps(value, ensure_ascii=False, separators=(",", ":"))
        if len(frame.encode("utf-8")) + 1 > MAX_FRAME_BYTES:
            raise ApiError("FRAME_TOO_LARGE", "The local service response is too large.")
        with self.write_lock:
            self.out.write(frame + "\n")
            self.out.flush()

    def status(self):
        onboarded = self.db.execute(
            "SELECT EXISTS(SELECT 1 FROM library_roots LIMIT 1)"
        ).fetchone()[0]
        count = self.db.execute(
            "SELECT count(*) FROM photos p "
            "JOIN library_roots r ON r.id=p.root_id "
            "WHERE r.enabled=1 AND p.available=1 AND p.hidden_at IS NULL"
        ).fetchone()[0]
        return {
            "onboarded": bool(onboarded),
            "eligibleCount": count,
            "scanRunning": self.scan_running,
        }

    def photo(self, row):
        if not row:
            return None
        result = dict(row)
        result["fileName"] = Path(result["path"]).name
        draft = self.db.execute(
            "SELECT note,prompt_id FROM drafts WHERE photo_id=?", (row["id"],)
        ).fetchone()
        reflection = self.db.execute(
            "SELECT id,note,prompt_id,prompt_text,created_at,updated_at "
            "FROM reflections WHERE photo_id=?",
            (row["id"],),
        ).fetchone()
        result["draft"] = dict(draft) if draft else None
        result["reflection"] = dict(reflection) if reflection else None
        return result

    def dispatch(self, method, p):
        if method in ("app.initialize", "app.status"):
            return self.status()
        if method == "library.suggestedRoot":
            return {"path": suggested_pictures()}
        if method == "library.rootAdd":
            path = str(canonical_root(p.get("path", "")))
            now = utcnow()
            self.db.execute(
                "INSERT INTO library_roots(path,enabled,created_at) VALUES(?,1,?) "
                "ON CONFLICT(path) DO UPDATE SET enabled=1",
                (path, now),
            )
            self.db.commit()
            return self.status()
        if method == "library.scanStart":
            if self.scan_running:
                raise ApiError("SCAN_RUNNING", "A scan is already running.")
            self.scan_running = True
            threading.Thread(target=self._scan, daemon=True).start()
            return {"started": True}
        if method == "memory.next":
            photo = select_next_photo(self.db)
            if not photo:
                return {
                    "memory": None,
                    "reason": "No photographs are available. Try rescanning or adjusting your folders.",
                }
            return {"memory": self.photo(photo)}
        if method == "preview.ensure":
            row = self.db.execute(
                "SELECT * FROM photos WHERE id=?", (int(p["photoId"]),)
            ).fetchone()
            if not row or not Path(row["path"]).is_file():
                raise ApiError("PHOTO_MISSING", "The original photograph is no longer available.")
            try:
                preview = ensure_preview(row)
            except (OSError, subprocess.SubprocessError):
                preview = row["path"]
            return {"path": preview, "sourcePath": row["path"]}
        if method in ("memory.shown", "memory.skip"):
            photo_id = int(p["photoId"])
            kind = "shown" if method.endswith("shown") else "skipped"
            now = utcnow()
            self.db.execute(
                "INSERT INTO events(photo_id,kind,occurred_at) VALUES(?,?,?)",
                (photo_id, kind, now),
            )
            if kind == "shown":
                self.db.execute(
                    "UPDATE photos SET last_shown_at=? WHERE id=?", (now, photo_id)
                )
            self.db.commit()
            return {"saved": True}
        if method == "draft.save":
            note = str(p.get("note", ""))
            if len(note.encode("utf-8")) > MAX_NOTE_BYTES:
                raise ApiError("NOTE_TOO_LONG", "Keep memories under 8 KiB.")
            now = utcnow()
            self.db.execute(
                "INSERT INTO drafts VALUES(?,?,?,?) "
                "ON CONFLICT(photo_id) DO UPDATE SET "
                "prompt_id=excluded.prompt_id,note=excluded.note,"
                "updated_at=excluded.updated_at",
                (int(p["photoId"]), str(p["promptId"]), note, now),
            )
            self.db.commit()
            return {"savedAt": now}
        if method == "reflection.save":
            note = str(p.get("note", "")).strip()
            if not note:
                raise ApiError("NOTE_EMPTY", "Write something before saving.")
            if len(note.encode("utf-8")) > MAX_NOTE_BYTES:
                raise ApiError("NOTE_TOO_LONG", "Keep memories under 8 KiB.")
            photo_id = int(p["photoId"])
            now = utcnow()
            self.db.execute(
                """INSERT INTO reflections(
                    photo_id,prompt_id,prompt_text,note,created_at,updated_at
                ) VALUES(?,?,?,?,?,?)
                ON CONFLICT(photo_id) DO UPDATE SET
                    prompt_id=excluded.prompt_id,
                    prompt_text=excluded.prompt_text,
                    note=excluded.note,
                    updated_at=excluded.updated_at""",
                (photo_id, str(p["promptId"]), str(p["promptText"]), note, now, now),
            )
            self.db.execute("DELETE FROM drafts WHERE photo_id=?", (photo_id,))
            self.db.execute(
                "INSERT INTO events(photo_id,kind,occurred_at) VALUES(?,?,?)",
                (photo_id, "saved", now),
            )
            self.db.execute(
                "UPDATE photos SET last_shown_at=? WHERE id=?", (now, photo_id)
            )
            self.db.commit()
            return {"savedAt": now}
        if method == "original.reveal":
            row = self.db.execute(
                "SELECT path FROM photos WHERE id=?", (int(p["photoId"]),)
            ).fetchone()
            if not row:
                raise ApiError(
                    "PHOTO_MISSING", "The original photograph is no longer available."
                )
            subprocess.Popen(
                ["uwsm-app", "--", "nautilus", "--select", Path(row["path"]).as_uri()],
                start_new_session=True,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            return {"opened": True}
        raise ApiError("UNKNOWN_METHOD", "This version does not support that action.")

    def _scan(self):
        connection = None
        try:
            connection = connect(self.db_path)
            roots = connection.execute(
                "SELECT id,path FROM library_roots WHERE enabled=1"
            ).fetchall()
            generation = int(datetime.now(timezone.utc).timestamp() * 1000)
            totals = {"seen": 0, "eligible": 0, "errors": 0}
            for library_root in roots:
                stats = scan_root(
                    connection,
                    library_root["id"],
                    library_root["path"],
                    generation,
                    lambda seen, eligible, errors: self.emit(
                        {
                            "event": "scan.progress",
                            "data": {
                                "seen": totals["seen"] + seen,
                                "eligible": totals["eligible"] + eligible,
                                "errors": totals["errors"] + errors,
                            },
                        }
                    ),
                )
                for key in totals:
                    totals[key] += stats[key]
            self.emit({"event": "scan.complete", "data": totals})
        except Exception as exc:
            self.emit(
                {"event": "scan.error", "data": {"message": str(exc)[:240]}}
            )
        finally:
            if connection:
                connection.close()
            self.scan_running = False

    def run(self):
        self.emit({"event": "ready", "data": {"protocolVersion": 1}})
        for raw in self.inp:
            request_id = None
            try:
                if len(raw.encode("utf-8")) > MAX_FRAME_BYTES:
                    raise ApiError("FRAME_TOO_LARGE", "Request is too large.")
                request = json.loads(raw)
                request_id = request.get("id")
                if (
                    not isinstance(request_id, int)
                    or request_id < 1
                    or not isinstance(request.get("method"), str)
                    or not isinstance(request.get("params", {}), dict)
                ):
                    raise ApiError("INVALID_REQUEST", "Malformed request.")
                self.emit(
                    {
                        "id": request_id,
                        "ok": True,
                        "result": self.dispatch(
                            request["method"], request.get("params", {})
                        ),
                    }
                )
            except ApiError as exc:
                self.emit(
                    {
                        "id": request_id,
                        "ok": False,
                        "error": {"code": exc.code, "message": exc.message},
                    }
                )
            except (KeyError, ValueError, TypeError, json.JSONDecodeError) as exc:
                self.emit(
                    {
                        "id": request_id,
                        "ok": False,
                        "error": {
                            "code": "INVALID_REQUEST",
                            "message": str(exc)[:240],
                        },
                    }
                )
            except Exception:
                self.emit(
                    {
                        "id": request_id,
                        "ok": False,
                        "error": {
                            "code": "INTERNAL_ERROR",
                            "message": "The local backend could not complete that action.",
                        },
                    }
                )


def main():
    Server().run()
