"""Launch the existing UltraRAG UI with external project storage."""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

from .config import ConfigurationError, resolve_config
from .runtime import RUNTIME_CACHE_ENV, RuntimeErrorBase, install_managed_runtime


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="vanilla-ultra-rag-ui",
        description="Launch the pinned, unmodified UltraRAG UI.",
    )
    parser.add_argument(
        "--workspace-root",
        type=Path,
        default=os.environ.get("ULTRARAG_WORKSPACE_ROOT"),
        required=os.environ.get("ULTRARAG_WORKSPACE_ROOT") is None,
        help="Project-owned directory for UI storage, logs, and output.",
    )
    parser.add_argument(
        "--ultrarag-root",
        type=Path,
        default=os.environ.get("ULTRARAG_ROOT"),
        help="Optional development checkout; managed runtime is used if omitted.",
    )
    parser.add_argument(
        "--runtime-cache-root",
        type=Path,
        default=os.environ.get(RUNTIME_CACHE_ENV),
        help="Override the managed runtime cache root.",
    )
    parser.add_argument("--offline", action="store_true")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=5050)
    return parser


def main() -> None:
    args = _parser().parse_args()
    try:
        ultrarag_root = (
            args.ultrarag_root.expanduser().resolve()
            if args.ultrarag_root is not None
            else install_managed_runtime(
                cache_root=args.runtime_cache_root,
                allow_download=not args.offline,
            )
        )
        workspace = args.workspace_root.expanduser().resolve()
        config = resolve_config(
            ultrarag_root=ultrarag_root,
            workspace_root=workspace,
            python_executable=sys.executable,
        )
    except (ConfigurationError, RuntimeErrorBase) as exc:
        raise SystemExit(str(exc)) from exc

    os.environ["ULTRARAG_UI_STORAGE_ROOT"] = str(workspace / "ui-storage")
    os.chdir(workspace)
    # Imports come from a content-verified cache and must not add .pyc files to
    # that otherwise immutable tree.
    sys.dont_write_bytecode = True

    source_root = str(config.ultrarag_root / "src")
    repository_root = str(config.ultrarag_root)
    sys.path.insert(0, source_root)
    sys.path.insert(1, repository_root)

    from ultrarag.client import launch_ui

    launch_ui(host=args.host, port=args.port)


if __name__ == "__main__":
    main()
