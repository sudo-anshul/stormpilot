#!/usr/bin/env python3
"""Run behavior, independent evidence and HTTP integration checks."""
import subprocess
import sys
from pathlib import Path

root = Path(__file__).resolve().parent.parent
commands = [
    ["-m", "unittest", "discover", "-s", "engine/tests", "-v"],
    ["-m", "unittest", "discover", "-s", "validation", "-t", ".", "-p", "test_*.py", "-v"],
    ["-m", "unittest", "discover", "-s", "service/tests", "-t", ".", "-p", "test_*.py", "-v"],
]
for args in commands:
    result = subprocess.run([sys.executable, *args], cwd=root)
    if result.returncode:
        raise SystemExit(result.returncode)
