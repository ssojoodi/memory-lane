import hashlib
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest
from unittest.mock import patch

import test_backend
from memory_lane.library import mime_type
from memory_lane.photo_files import photo_file
from memory_lane.previews import ensure_preview
from memory_lane.location import map_url


class PhotoSecurityTest(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.base = Path(temporary.name)
        self.photo = self.base / "photo.png"
        test_backend.png(self.photo)
        self.cache = self.base / "cache"
        self.env = patch.dict(os.environ, {"XDG_CACHE_HOME": str(self.cache)})
        self.env.start()
        self.addCleanup(self.env.stop)

    def test_fifo_and_links_rejected_before_io(self):
        fifo = self.base / "fifo.png"
        os.mkfifo(fifo)
        link = self.base / "link.png"
        link.symlink_to(self.photo)
        alias = self.base / "alias"
        alias.symlink_to(self.base, target_is_directory=True)
        for path in (fifo, link, alias / "photo.png"):
            with self.subTest(path=path):
                self.assertIsNone(mime_type(path))
                with self.assertRaises(OSError):
                    with photo_file(path):
                        self.fail("Unsafe file opened")
                with patch("memory_lane.location.bounded_output") as run:
                    with self.assertRaises(OSError):
                        map_url(path)
                    run.assert_not_called()

    def test_open_descriptor_survives_replacement(self):
        with photo_file(self.photo) as stream:
            self.photo.rename(self.base / "original.png")
            self.photo.symlink_to(self.base / "missing")
            self.assertEqual(stream.read(8), b"\x89PNG\r\n\x1a\n")

    def test_cache_directory_link_never_chmods_target(self):
        target = self.base / "unrelated"
        target.mkdir(mode=0o755)
        target.chmod(0o755)
        (self.cache / "memory-lane").mkdir(parents=True)
        (self.cache / "memory-lane/previews").symlink_to(target)
        with self.assertRaises(OSError):
            ensure_preview({"path": str(self.photo)})
        self.assertEqual(target.stat().st_mode & 0o777, 0o755)
        self.assertEqual(list(target.iterdir()), [])

    def test_cache_file_links_and_permissions_rejected(self):
        directory = self.cache / "memory-lane/previews"
        directory.mkdir(parents=True, mode=0o700)
        info = self.photo.stat()
        key = hashlib.blake2b(
            f"{self.photo}\0{info.st_dev}\0{info.st_ino}\0{info.st_size}\0{info.st_mtime_ns}".encode(),
            digest_size=20).hexdigest()
        cached = directory / f"{key}.jpg"
        for kind in ("symlink", "hardlink", "fifo", "public"):
            if kind == "symlink":
                cached.symlink_to(self.photo)
            elif kind == "hardlink":
                os.link(self.photo, cached)
            elif kind == "fifo":
                os.mkfifo(cached)
            else:
                cached.touch()
                cached.chmod(0o644)
            with self.subTest(kind=kind), self.assertRaises(OSError):
                ensure_preview({"path": str(self.photo)})
            cached.unlink()

    @unittest.skipUnless(shutil.which("vips") and shutil.which("vipsthumbnail"), "libvips required")
    def test_real_private_preview_and_reuse(self):
        subprocess.run(["vips", "black", str(self.photo), "2", "2"], check=True,
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=5)
        before = self.photo.read_bytes()
        preview = Path(ensure_preview({"path": str(self.photo)}))
        self.assertEqual(preview.stat().st_mode & 0o777, 0o600)
        self.assertEqual(preview.parent.stat().st_mode & 0o777, 0o700)
        self.assertTrue(preview.read_bytes().startswith(b"\xff\xd8\xff"))
        self.assertEqual(self.photo.read_bytes(), before)
        with patch("memory_lane.previews.subprocess.run") as run:
            self.assertEqual(ensure_preview({"path": str(self.photo)}), str(preview))
            run.assert_not_called()
