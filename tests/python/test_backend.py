import io
import json
import sys
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "backend"))

from memory_lane.database import connect
from memory_lane.library import mime_type, scan_root
from memory_lane.server import Server


def png(path):
    path.write_bytes(b"\x89PNG\r\n\x1a\n" + b"\0" * 24)


class MemoryLaneTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.base = Path(self.tmp.name)
        self.db = self.base / "data.sqlite3"
        self.photos = self.base / "photos"
        self.photos.mkdir()
        self.connections = []

    def tearDown(self):
        for connection in self.connections:
            connection.close()
        self.tmp.cleanup()

    def connection(self):
        connection = connect(self.db)
        self.connections.append(connection)
        return connection

    def server(self, incoming=None, outgoing=None):
        server = Server(self.db, incoming, outgoing)
        self.connections.append(server.db)
        return server

    def test_magic_header_and_scan(self):
        png(self.photos / "holiday.png")
        (self.photos / "fake.jpg").write_text("not a photo")
        (self.photos / "Screenshot_1.png").write_bytes(b"\x89PNG\r\n\x1a\n")
        self.assertEqual(mime_type(self.photos / "holiday.png"), "image/png")
        self.assertIsNone(mime_type(self.photos / "fake.jpg"))
        con = self.connection()
        con.execute("INSERT INTO library_roots(path,created_at) VALUES(?,datetime('now'))", (str(self.photos),))
        root_id = con.execute("SELECT id FROM library_roots").fetchone()[0]
        stats = scan_root(con, root_id, self.photos, 1)
        self.assertEqual(stats["eligible"], 1)
        self.assertEqual(con.execute("SELECT count(*) FROM photos").fetchone()[0], 1)

    def test_symlink_is_not_followed(self):
        external = self.base / "external"; external.mkdir(); png(external / "private.png")
        (self.photos / "link").symlink_to(external, target_is_directory=True)
        con = self.connection()
        con.execute("INSERT INTO library_roots(path,created_at) VALUES(?,datetime('now'))", (str(self.photos),))
        scan_root(con, 1, self.photos, 2)
        self.assertEqual(con.execute("SELECT count(*) FROM photos").fetchone()[0], 0)

    def test_protocol_unicode_reflection(self):
        png(self.photos / "memory.png")
        incoming = io.StringIO("\n".join([
            json.dumps({"id":1,"method":"library.rootAdd","params":{"path":str(self.photos)}}),
            json.dumps({"id":2,"method":"reflection.save","params":{"photoId":999,"promptId":"where","promptText":"Where?","note":"café"}})
        ]) + "\n")
        outgoing = io.StringIO()
        self.server(incoming, outgoing).run()
        frames = [json.loads(x) for x in outgoing.getvalue().splitlines()]
        self.assertEqual(frames[0]["event"], "ready")
        self.assertTrue(frames[1]["ok"])
        self.assertFalse(frames[2]["ok"])

    def test_private_database_mode(self):
        con = self.connection()
        con.close()
        self.connections.remove(con)
        self.assertEqual(self.db.stat().st_mode & 0o777, 0o600)

    def test_annotated_photos_are_occasionally_resurfaced(self):
        png(self.photos / "annotated.png")
        png(self.photos / "fresh.png")
        server = self.server()
        server.dispatch("library.rootAdd", {"path": str(self.photos)})
        con = server.db
        scan_root(con, 1, self.photos, 1)
        annotated_id = con.execute("SELECT id FROM photos WHERE path LIKE '%annotated.png'").fetchone()[0]
        old = (datetime.now(timezone.utc) - timedelta(days=8)).isoformat().replace("+00:00", "Z")
        con.execute("UPDATE photos SET last_shown_at=? WHERE id=?", (old, annotated_id))
        con.execute("INSERT INTO reflections(photo_id,prompt_id,prompt_text,note,created_at,updated_at) VALUES(?,?,?,?,?,?)",
                    (annotated_id, "where", "Where?", "A previous memory", old, old))
        con.commit()
        with patch("memory_lane.selection.random.random", return_value=0.0):
            result = server.dispatch("memory.next", {})
        self.assertEqual(result["memory"]["id"], annotated_id)
        self.assertEqual(result["memory"]["reflection"]["note"], "A previous memory")

    def test_recent_photo_is_reused_when_preferred_pools_are_exhausted(self):
        png(self.photos / "only-photo.png")
        server = self.server()
        server.dispatch("library.rootAdd", {"path": str(self.photos)})
        scan_root(server.db, 1, self.photos, 1)
        photo_id = server.db.execute("SELECT id FROM photos").fetchone()[0]
        server.dispatch("memory.shown", {"photoId": photo_id})
        result = server.dispatch("memory.next", {})
        self.assertEqual(result["memory"]["id"], photo_id)

    def test_skipped_photo_is_last_resort(self):
        png(self.photos / "only-photo.png")
        server = self.server()
        server.dispatch("library.rootAdd", {"path": str(self.photos)})
        scan_root(server.db, 1, self.photos, 1)
        photo_id = server.db.execute("SELECT id FROM photos").fetchone()[0]
        server.dispatch("memory.skip", {"photoId": photo_id})
        result = server.dispatch("memory.next", {})
        self.assertEqual(result["memory"]["id"], photo_id)

    def test_reveal_opens_file_manager_with_photo_selected(self):
        photo_path = self.photos / "selected.png"
        png(photo_path)
        server = self.server()
        server.dispatch("library.rootAdd", {"path": str(self.photos)})
        scan_root(server.db, 1, self.photos, 1)
        photo_id = server.db.execute("SELECT id FROM photos").fetchone()[0]
        with patch("memory_lane.server.subprocess.Popen") as popen:
            result = server.dispatch("original.reveal", {"photoId": photo_id})
        self.assertEqual(result, {"opened": True})
        command = popen.call_args.args[0]
        self.assertEqual(command[:4], ["uwsm-app", "--", "nautilus", "--select"])
        self.assertEqual(command[4], photo_path.as_uri())


if __name__ == "__main__":
    unittest.main()
