"""Small, bounded output capture for local metadata utilities."""

import os
import selectors
import subprocess
import time


def bounded_output(command, *, timeout=2, limit=16 * 1024, pass_fds=()):
    deadline = time.monotonic() + timeout
    with subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
                          pass_fds=pass_fds) as process:
        try:
            output = bytearray()
            with selectors.DefaultSelector() as selector:
                selector.register(process.stdout, selectors.EVENT_READ)
                while True:
                    remaining = deadline - time.monotonic()
                    if remaining <= 0 or not selector.select(remaining):
                        raise subprocess.TimeoutExpired(command, timeout)
                    chunk = os.read(process.stdout.fileno(), min(4096, limit + 1 - len(output)))
                    if not chunk:
                        break
                    output.extend(chunk)
                    if len(output) > limit:
                        raise OSError("Metadata utility exceeded its output limit.")
            process.wait(timeout=max(0, deadline - time.monotonic()))
            return subprocess.CompletedProcess(command, process.returncode, output.decode("utf-8", errors="replace"))
        finally:
            if process.poll() is None:
                process.kill()
            process.wait()
