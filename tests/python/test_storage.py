import os
import sqlite3
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "backend"))

from memory_lane.database import connect
from memory_lane.storage import UnsafeStorageError, _database_location, open_private_database


class StorageTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.base = Path(self.tmp.name)
        self.state = self.base / "memory-lane"
        self.state.mkdir(mode=0o700)
        self.db = self.state / "memory-lane.sqlite3"
        self.victim = self.base / "unrelated.txt"
        self.victim.write_bytes(b"Must not be changed")
        self.victim.chmod(0o600)

    def assert_rejected(self):
        before = self.victim.stat()
        with patch("memory_lane.database.migrate") as migrate:
            with self.assertRaises(OSError):
                connect(self.db)
            migrate.assert_not_called()
        after = self.victim.stat()
        self.assertEqual(self.victim.read_bytes(), b"Must not be changed")
        self.assertEqual(before.st_mode, after.st_mode)
        self.assertEqual(before.st_mtime_ns, after.st_mtime_ns)

    def test_database_symlink(self):
        self.db.symlink_to(self.victim)
        self.assert_rejected()

    def test_dangling_database_symlink(self):
        missing = self.base / "missing"
        self.db.symlink_to(missing)
        self.assert_rejected()
        self.assertFalse(missing.exists())

    def test_database_hardlink(self):
        os.link(self.victim, self.db)
        self.assert_rejected()

    def test_nonregular_database(self):
        os.mkfifo(self.db, mode=0o600)
        self.assert_rejected()

    def test_sidecar_symlinks(self):
        for suffix in ("-journal", "-wal", "-shm"):
            with self.subTest(suffix=suffix):
                sidecar = Path(str(self.db) + suffix)
                sidecar.symlink_to(self.victim)
                self.assert_rejected()
                self.assertFalse(self.db.exists())
                sidecar.unlink()

    def test_sidecar_hardlink(self):
        os.link(self.victim, str(self.db) + "-wal")
        self.assert_rejected()

    def test_directory_symlink(self):
        external = self.base / "external"
        external.mkdir(mode=0o700)
        self.state.rmdir()
        self.state.symlink_to(external, target_is_directory=True)
        self.assert_rejected()
        self.assertEqual(list(external.iterdir()), [])

    def test_ancestor_symlink(self):
        alias = self.base / "alias"
        alias.symlink_to(self.state, target_is_directory=True)
        self.db = alias / "nested" / self.db.name
        self.assert_rejected()
        self.assertFalse((self.state / "nested").exists())

    def test_unsafe_permissions_are_rejected_without_chmod(self):
        self.state.chmod(0o777)
        self.assert_rejected()
        self.assertEqual(self.state.stat().st_mode & 0o777, 0o777)
        self.state.chmod(0o700)
        self.db.touch(mode=0o666)
        self.db.chmod(0o666)
        self.assert_rejected()
        self.assertEqual(self.db.stat().st_mode & 0o777, 0o666)

    def test_foreign_owned_database_and_directory(self):
        self.db.touch(mode=0o600)
        real_fstat = os.fstat
        for target in (self.db, self.state):
            identity = target.stat().st_ino

            def foreign_owner(fd):
                info = real_fstat(fd)
                if info.st_ino == identity:
                    fields = list(info)
                    fields[4] = os.geteuid() + 1
                    return os.stat_result(fields)
                return info

            with self.subTest(target=target.name), patch(
                "memory_lane.storage.os.fstat", side_effect=foreign_owner
            ):
                self.assert_rejected()

    def test_default_xdg_path_does_not_follow_or_chmod_symlink(self):
        self.state.rmdir()
        self.state.symlink_to(self.base, target_is_directory=True)
        before = self.base.stat().st_mode
        with patch.dict(os.environ, {"XDG_DATA_HOME": str(self.base)}):
            with self.assertRaises(OSError):
                connect()
        self.assertEqual(self.base.stat().st_mode, before)
        self.assertFalse((self.base / "memory-lane.sqlite3").exists())

    def test_descriptor_path_survives_parent_rename(self):
        with _database_location(self.db) as (location, identity):
            moved = self.base / "moved"
            self.state.rename(moved)
            self.state.symlink_to(self.base, target_is_directory=True)
            con = sqlite3.connect(location)
            try:
                con.execute("CREATE TABLE test(value)")
                con.commit()
            finally:
                con.close()
            info = (moved / self.db.name).stat()
            self.assertEqual((info.st_dev, info.st_ino), identity)
        self.assertFalse((self.base / self.db.name).exists())

    def test_creation_reopen_migration_and_concurrent_connections(self):
        self.db = self.state / "new" / "nested" / self.db.name
        first = connect(self.db)
        self.addCleanup(first.close)
        first.execute("INSERT INTO settings VALUES ('memory-test', 'remember me', 'today')")
        first.commit()
        second = connect(self.db)
        self.addCleanup(second.close)
        self.assertEqual(second.execute(
            "SELECT value_json FROM settings WHERE key='memory-test'"
        ).fetchone()[0], "remember me")
        self.assertEqual(second.execute("PRAGMA journal_mode").fetchone()[0], "wal")
        self.assertEqual(second.execute("PRAGMA busy_timeout").fetchone()[0], 3000)
        self.assertEqual(self.db.stat().st_mode & 0o777, 0o600)
        self.assertEqual(self.db.parent.stat().st_mode & 0o777, 0o700)
        first.execute("BEGIN IMMEDIATE")
        # Storage checks must not release the first connection's write lock.
        with _database_location(self.db):
            pass
        contender = subprocess.run(
            [sys.executable, "-c",
             "import sqlite3, sys; c=sqlite3.connect(sys.argv[1], timeout=0); "
             "c.execute('BEGIN IMMEDIATE')", str(self.db)],
            capture_output=True, text=True, timeout=5,
        )
        self.assertNotEqual(contender.returncode, 0)
        self.assertIn("database is locked", contender.stderr)
        first.rollback()
        second.execute("BEGIN IMMEDIATE")
        second.rollback()

    def test_private_open_does_not_configure_or_migrate(self):
        con = open_private_database(self.db)
        self.addCleanup(con.close)
        self.assertEqual(con.execute("PRAGMA journal_mode").fetchone()[0], "delete")
        self.assertEqual(con.execute("SELECT count(*) FROM sqlite_master").fetchone()[0], 0)

    def test_identity_mismatch_closes_connection_before_migration(self):
        with patch("memory_lane.storage.sqlite3.connect") as opening, patch(
            "memory_lane.storage.os.stat"
        ) as file_stat, patch("memory_lane.database.migrate") as migrate:
            file_stat.return_value.st_dev = -1
            file_stat.return_value.st_ino = -1
            with self.assertRaises(UnsafeStorageError):
                connect(self.db)
            opening.return_value.close.assert_called_once()
            migrate.assert_not_called()

    def test_setup_failure_closes_connection(self):
        for step in ("configure", "migrate"):
            with self.subTest(step=step), patch(
                "memory_lane.database.open_private_database"
            ) as opening, patch(
                "memory_lane.database." + step, side_effect=RuntimeError("setup failed")
            ):
                with self.assertRaisesRegex(RuntimeError, "setup failed"):
                    connect(self.db)
                opening.return_value.close.assert_called_once()
