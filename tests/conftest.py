from __future__ import annotations

import os
import subprocess
from pathlib import Path

import pytest


def ultrarag_root() -> Path:
    configured = os.environ.get("ULTRARAG_ROOT")
    if configured:
        return Path(configured).expanduser().resolve()
    return Path(__file__).resolve().parents[2] / "UltraRAG"


def _git_status(root: Path) -> str:
    return subprocess.run(
        ["git", "-C", str(root), "status", "--porcelain", "--untracked-files=all"],
        check=True,
        capture_output=True,
        text=True,
    ).stdout


@pytest.fixture(scope="session", autouse=True)
def upstream_checkout_is_unchanged() -> None:
    root = ultrarag_root()
    before = _git_status(root)
    yield
    assert _git_status(root) == before
