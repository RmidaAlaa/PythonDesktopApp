"""Application version and build metadata helpers."""

from __future__ import annotations

import os
import subprocess
from typing import Tuple


def _git_commit_short() -> str:
    try:
        # Prefer environment override if present
        env_commit = os.environ.get("APP_COMMIT")
        if env_commit:
            return env_commit
        # Fallback to Git if repository is available
        res = subprocess.run([
            "git", "rev-parse", "--short", "HEAD"
        ], capture_output=True, text=True)
        if res.returncode == 0:
            return res.stdout.strip()
    except Exception:
        pass
    return "unknown"


def get_version() -> Tuple[str, str]:
    """Return (version, commit) strings.

    Version is read from env `APP_VERSION` if present, otherwise defaults to `1.0.0`.
    Commit is short Git hash or `unknown`.
    """
    version = os.environ.get("APP_VERSION", "1.0.4")
    commit = _git_commit_short()
    return version, commit


def format_version_banner() -> str:
    v, c = get_version()
    return f"AWG Kumulus Device Manager v{v} (commit {c})"