from __future__ import annotations

import subprocess


def git_diff() -> str:
    proc = subprocess.run(["git", "diff"], check=False, capture_output=True, text=True)
    return proc.stdout
