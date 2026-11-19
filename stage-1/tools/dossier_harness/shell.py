"""Run external commands with a timeout; image builds hold the shared heavy lock."""
from __future__ import annotations

import subprocess
from collections.abc import Sequence

from .config import HEAVY_LOCK


class CommandFailed(RuntimeError):
    pass


def run(command: Sequence[str], timeout: float, check: bool = True) -> subprocess.CompletedProcess[str]:
    result = subprocess.run(command, capture_output=True, text=True, timeout=timeout)
    if check and result.returncode != 0:
        raise CommandFailed(f"{' '.join(command[:4])} failed: {result.stderr.strip()[-600:]}")
    return result


def run_heavy(command: Sequence[str], timeout: float) -> subprocess.CompletedProcess[str]:
    return run(["flock", HEAVY_LOCK, *command], timeout)
