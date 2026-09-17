"""Source-selection helpers for the PDF/EPUB corpus verifier."""

from __future__ import annotations

from pathlib import Path

ALLOWED_SOURCE_EXTENSIONS = frozenset({".epub", ".pdf"})


def input_files(source: Path) -> list[Path]:
    """Return only PDF and EPUB files from a file or directory input."""
    candidates = [source] if source.is_file() else list(source.rglob("*"))
    return sorted(
        path
        for path in candidates
        if path.is_file() and path.suffix.lower() in ALLOWED_SOURCE_EXTENSIONS
    )


def stage_input_files(
    source: Path,
    inputs: list[Path],
    staging_root: Path,
) -> Path:
    """Create a temporary PDF/EPUB-only view for the vanilla corpus tool."""
    if source.is_file():
        return source

    for input_path in inputs:
        relative_path = input_path.relative_to(source)
        staged_path = staging_root / relative_path
        staged_path.parent.mkdir(parents=True, exist_ok=True)
        staged_path.symlink_to(input_path)
    return staging_root
