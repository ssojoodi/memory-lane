import subprocess
import shutil
import struct
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import test_backend
from memory_lane.location import coordinate, map_url, _map_url
from memory_lane.server import ApiError


class LocationTest(unittest.TestCase):
    def test_coordinates_and_hemispheres(self):
        self.assertEqual(coordinate("40/1 30/1 0/1 (details)", "N (North)", "N", "S", 90), 40.5)
        self.assertEqual(coordinate("40/1 30/1 0/1", "S", "N", "S", 90), -40.5)
        self.assertEqual(coordinate("0/1 0/1 0/1", "E", "E", "W", 180), 0)
        self.assertEqual(coordinate("180/1 0/1 0/1", "W", "E", "W", 180), -180)

    def test_invalid_coordinates(self):
        for value, ref in [("91/1 0/1 0/1", "N"), ("1 60 0", "N"),
                           ("1 0 60", "N"), ("1 0 0", "W"),
                           ("-1 0 0", "N"), ("1/0 0 0", "N"),
                           ("nan 0 0", "N"), ("1 2", "N")]:
            with self.subTest(value=value, ref=ref), self.assertRaises((ValueError, ZeroDivisionError)):
                coordinate(value, ref, "N", "S", 90)

    @patch("memory_lane.location.bounded_output")
    def test_marker_and_read_only_commands(self, run):
        run.side_effect = [subprocess.CompletedProcess([], 0, value)
                           for value in ("35 30 0", "N", "139 45 0", "E")]
        with tempfile.TemporaryFile() as stream:
            descriptor = stream.fileno()
            url = _map_url(stream)
        self.assertEqual(url, "https://www.openstreetmap.org/?mlat=35.500000&mlon=139.750000#map=16/35.500000/139.750000")
        self.assertEqual(run.call_count, 4)
        for call in run.call_args_list:
            self.assertEqual(call.args[0][0:2], ["vipsheader", "-f"])
            self.assertEqual(call.args[0][-1], f"/proc/self/fd/{descriptor}")
            self.assertEqual(call.kwargs["pass_fds"], (descriptor,))
            self.assertEqual(call.kwargs["timeout"], 2)

    @patch("memory_lane.location.bounded_output")
    def test_no_metadata(self, run):
        run.return_value = subprocess.CompletedProcess([], 1, "")
        with tempfile.TemporaryFile() as stream:
            self.assertIsNone(_map_url(stream))

    @unittest.skipUnless(shutil.which("vips") and shutil.which("vipsheader"), "libvips is required")
    def test_real_jpeg_metadata(self):
        with tempfile.TemporaryDirectory() as folder:
            photo = Path(folder) / "GPS photo.jpg"
            subprocess.run(["vips", "black", str(photo), "1", "1"], check=True,
                           stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=5)
            self.assertIsNone(map_url(photo))
            # Minimal little-endian TIFF: root IFD points to four GPS tags.
            tiff = b"II" + struct.pack("<HI", 42, 8)
            tiff += struct.pack("<HHHIII", 1, 0x8825, 4, 1, 26, 0)
            tiff += struct.pack("<H", 4)
            tiff += struct.pack("<HHI4s", 1, 2, 2, b"N\0\0\0")
            tiff += struct.pack("<HHII", 2, 5, 3, 80)
            tiff += struct.pack("<HHI4s", 3, 2, 2, b"W\0\0\0")
            tiff += struct.pack("<HHII", 4, 5, 3, 104) + struct.pack("<I", 0)
            tiff += struct.pack("<12I", 35, 1, 30, 1, 0, 1, 139, 1, 45, 1, 0, 1)
            exif = b"Exif\0\0" + tiff
            original = photo.read_bytes()
            photo.write_bytes(original[:2] + b"\xff\xe1" + struct.pack(">H", len(exif) + 2) + exif + original[2:])
            before = photo.read_bytes()
            self.assertEqual(map_url(photo), "https://www.openstreetmap.org/?mlat=35.500000&mlon=-139.750000#map=16/35.500000/-139.750000")
            self.assertEqual(photo.read_bytes(), before)


class LocationApiTest(unittest.TestCase):
    setUp = test_backend.MemoryLaneTest.setUp
    tearDown = test_backend.MemoryLaneTest.tearDown
    server = test_backend.MemoryLaneTest.server

    def test_location_api(self):
        server = self.server()
        photo = self.photos / "photo.png"
        test_backend.png(photo)
        server.dispatch("library.rootAdd", {"path": str(self.photos)})
        from memory_lane.library import scan_root
        scan_root(server.db, 1, str(self.photos), 1)
        with patch("memory_lane.server.map_url", return_value=None):
            with self.assertRaises(ApiError) as error:
                server.dispatch("photo.location", {"photoId": 1})
            self.assertEqual(error.exception.code, "NO_LOCATION")
        with patch("memory_lane.server.map_url", return_value="https://www.openstreetmap.org/"):
            self.assertIn("url", server.dispatch("photo.location", {"photoId": 1}))
        with patch("memory_lane.server.map_url", side_effect=subprocess.TimeoutExpired("vipsheader", 2)):
            with self.assertRaises(ApiError) as error:
                server.dispatch("photo.location", {"photoId": 1})
            self.assertEqual(error.exception.code, "LOCATION_UNAVAILABLE")
        photo.unlink()
        with self.assertRaises(ApiError) as error:
            server.dispatch("photo.location", {"photoId": 1})
        self.assertEqual(error.exception.code, "PHOTO_MISSING")
