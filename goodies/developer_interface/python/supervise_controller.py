#!/usr/bin/env python3
"""Keep the local Web Sweeper controller alive in a user session."""

from __future__ import annotations

import subprocess
import sys
import time
from pathlib import Path


RESTART_DELAY_SECONDS = 2


def controller_command(arguments: list[str]) -> list[str]:
    server = Path(__file__).resolve().with_name("server.py")
    return [sys.executable, "-u", str(server), *arguments]


def main(arguments: list[str] | None = None) -> int:
    forwarded = list(sys.argv[1:] if arguments is None else arguments)
    while True:
        child = subprocess.Popen(controller_command(forwarded))
        try:
            return_code = child.wait()
        except KeyboardInterrupt:
            child.terminate()
            try:
                child.wait(timeout=5)
            except subprocess.TimeoutExpired:
                child.kill()
                child.wait()
            return 130
        if return_code == 0:
            return 0
        time.sleep(RESTART_DELAY_SECONDS)


if __name__ == "__main__":
    raise SystemExit(main())
