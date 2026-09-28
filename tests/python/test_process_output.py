import subprocess
import sys
import unittest

import test_backend  # Makes the local backend package importable.
from memory_lane.process_output import bounded_output


class ProcessOutputTest(unittest.TestCase):
    def test_exact_limit_and_exit_code(self):
        result = bounded_output([sys.executable, "-c", "import sys; sys.stdout.write('x'*16); sys.exit(3)"], limit=16)
        self.assertEqual(result.stdout, "x" * 16)
        self.assertEqual(result.returncode, 3)

    def test_output_overflow(self):
        with self.assertRaisesRegex(OSError, "output limit"):
            bounded_output([sys.executable, "-c", "print('x'*100000)"], limit=16)

    def test_timeout(self):
        with self.assertRaises(subprocess.TimeoutExpired):
            bounded_output([sys.executable, "-c", "import time; time.sleep(2)"], timeout=.1)
