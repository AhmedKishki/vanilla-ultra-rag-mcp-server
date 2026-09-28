"""Regenerate the per-file digests that let validation name a differing path."""

from __future__ import annotations

import argparse
from pathlib import Path

from vanilla_ultra_rag_mcp.manifest import BASELINE_COMMIT
from vanilla_ultra_rag_mcp.runtime import (
    _tree_files,
    managed_runtime_path,
    validate_managed_runtime,
)

TARGET = (
    Path(__file__).resolve().parents[1]
    / "src"
    / "vanilla_ultra_rag_mcp"
    / "tree_manifest.py"
)

HEADER = '''"""Generated per-file digests for the pinned UltraRAG tree.

Regenerate with scripts/generate_tree_manifest.py. A tree whose aggregate hash
still matches TREE_SHA256 can no longer be described this way, so the manifest
and the aggregate hash must be regenerated together.
"""

from __future__ import annotations

TREE_FILES: dict[str, str] = {
'''


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Write tree_manifest.py from a runtime root that already passes "
            "validate_managed_runtime."
        ),
    )
    parser.add_argument(
        "--runtime-root",
        type=Path,
        default=managed_runtime_path(),
        help="A validated managed runtime (default: the managed cache).",
    )
    args = parser.parse_args()

    root = validate_managed_runtime(args.runtime_root)
    files = _tree_files(root)
    body = "".join(f'    "{path}": "{digest}",\n' for path, digest in files.items())
    TARGET.write_text(HEADER + body + "}\n", encoding="utf-8")
    print(f"{TARGET} records {len(files)} files for UltraRAG {BASELINE_COMMIT}")


if __name__ == "__main__":
    main()
