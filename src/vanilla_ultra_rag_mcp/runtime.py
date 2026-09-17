"""Install and validate an immutable, non-Git UltraRAG runtime snapshot."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
import tarfile
import tempfile
import tomllib
import urllib.request
from pathlib import Path, PurePosixPath
from typing import Any

from platformdirs import user_cache_path

from .manifest import BASELINE_COMMIT, BASELINE_VERSION, SERVER_SPECS

ARCHIVE_URL = f"https://codeload.github.com/OpenBMB/UltraRAG/tar.gz/{BASELINE_COMMIT}"
ARCHIVE_SHA256 = "cb7b7b10dd8eacecd43d7e6705baea4cd431710e7016a0b66673c56821accece"
TREE_SHA256 = "054ec995256de591bf8b1f17bfbb4788bee4694e6f73dc971580c1676ee8c025"
MARKER_FILENAME = ".vanilla-ultra-rag-runtime.json"
RUNTIME_CACHE_ENV = "VANILLA_ULTRARAG_CACHE_ROOT"


class RuntimeErrorBase(RuntimeError):
    """Base class for managed-runtime failures."""


class RuntimeInstallError(RuntimeErrorBase):
    """Raised when the pinned runtime cannot be installed safely."""


class RuntimeValidationError(RuntimeErrorBase):
    """Raised when an existing managed runtime does not match the baseline."""


def default_cache_root() -> Path:
    configured = os.environ.get(RUNTIME_CACHE_ENV)
    if configured:
        return Path(configured).expanduser().resolve()
    return user_cache_path("vanilla-ultra-rag-mcp", appauthor=False).resolve()


def managed_runtime_path(cache_root: str | Path | None = None) -> Path:
    base = (
        Path(cache_root).expanduser().resolve()
        if cache_root is not None
        else default_cache_root()
    )
    return base / "runtime" / f"UltraRAG-{BASELINE_COMMIT}"


def _tree_hash(root: Path) -> str:
    digest = hashlib.sha256()
    files = sorted(
        path
        for path in root.rglob("*")
        if path.is_file() and path.name != MARKER_FILENAME
    )
    for path in files:
        relative = path.relative_to(root).as_posix().encode("utf-8")
        content = path.read_bytes()
        digest.update(len(relative).to_bytes(8, "big"))
        digest.update(relative)
        digest.update(len(content).to_bytes(8, "big"))
        digest.update(content)
    return digest.hexdigest()


def _read_version(root: Path) -> str:
    try:
        with (root / "pyproject.toml").open("rb") as handle:
            return str(tomllib.load(handle)["project"]["version"])
    except (OSError, KeyError, tomllib.TOMLDecodeError) as exc:
        raise RuntimeValidationError(
            f"Cannot read managed UltraRAG version beneath {root}"
        ) from exc


def _expected_marker() -> dict[str, Any]:
    return {
        "format_version": 1,
        "upstream_version": BASELINE_VERSION,
        "upstream_commit": BASELINE_COMMIT,
        "archive_url": ARCHIVE_URL,
        "archive_sha256": ARCHIVE_SHA256,
        "tree_sha256": TREE_SHA256,
    }


def validate_managed_runtime(root: str | Path) -> Path:
    runtime_root = Path(root).expanduser().resolve()
    marker_path = runtime_root / MARKER_FILENAME
    if not marker_path.is_file():
        raise RuntimeValidationError(
            f"Managed runtime marker is missing: {marker_path}"
        )
    try:
        marker = json.loads(marker_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise RuntimeValidationError(
            f"Cannot read managed runtime marker: {marker_path}"
        ) from exc
    if marker != _expected_marker():
        raise RuntimeValidationError(
            f"Managed runtime marker does not match this release: {marker_path}"
        )
    if _read_version(runtime_root) != BASELINE_VERSION:
        raise RuntimeValidationError(
            f"Managed runtime has the wrong UltraRAG version: {runtime_root}"
        )

    missing = [
        spec.relative_entrypoint.as_posix()
        for spec in SERVER_SPECS
        if not (runtime_root / spec.relative_entrypoint).is_file()
    ]
    if missing:
        raise RuntimeValidationError(
            f"Managed runtime is missing MCP entrypoints: {', '.join(missing)}"
        )

    actual_hash = _tree_hash(runtime_root)
    if actual_hash != TREE_SHA256:
        raise RuntimeValidationError(
            "Managed runtime content hash mismatch: "
            f"got {actual_hash}, expected {TREE_SHA256}. "
            "Use a fresh cache location rather than modifying the snapshot."
        )
    return runtime_root


def _download_archive(destination: Path) -> None:
    digest = hashlib.sha256()
    request = urllib.request.Request(
        ARCHIVE_URL,
        headers={"User-Agent": "vanilla-ultra-rag-mcp/0.1.1"},
    )
    try:
        with (
            urllib.request.urlopen(request, timeout=60) as response,
            destination.open("wb") as output,
        ):
            while chunk := response.read(1024 * 1024):
                digest.update(chunk)
                output.write(chunk)
    except OSError as exc:
        raise RuntimeInstallError(
            f"Failed to download the pinned UltraRAG runtime from {ARCHIVE_URL}"
        ) from exc

    actual_hash = digest.hexdigest()
    if actual_hash != ARCHIVE_SHA256:
        raise RuntimeInstallError(
            "Downloaded UltraRAG archive hash mismatch: "
            f"got {actual_hash}, expected {ARCHIVE_SHA256}"
        )


def _safe_extract(archive_path: Path, destination: Path) -> Path:
    expected_directory = f"UltraRAG-{BASELINE_COMMIT}"
    try:
        with tarfile.open(archive_path, mode="r:gz") as archive:
            members = archive.getmembers()
            for member in members:
                relative = PurePosixPath(member.name)
                if (
                    relative.is_absolute()
                    or ".." in relative.parts
                    or not relative.parts
                    or relative.parts[0] != expected_directory
                    or member.issym()
                    or member.islnk()
                    or member.isdev()
                ):
                    raise RuntimeInstallError(
                        f"Unsafe member in UltraRAG archive: {member.name}"
                    )
            archive.extractall(destination)
    except (OSError, tarfile.TarError) as exc:
        raise RuntimeInstallError("Failed to extract the UltraRAG archive") from exc

    extracted = destination / expected_directory
    if not extracted.is_dir():
        raise RuntimeInstallError(
            f"UltraRAG archive did not contain {expected_directory}"
        )
    return extracted


def install_managed_runtime(
    cache_root: str | Path | None = None,
    *,
    allow_download: bool = True,
) -> Path:
    target = managed_runtime_path(cache_root)
    if target.exists():
        return validate_managed_runtime(target)
    if not allow_download:
        raise RuntimeInstallError(
            f"Managed UltraRAG runtime is not installed at {target}"
        )

    target.parent.mkdir(parents=True, exist_ok=True)
    print(
        f"Installing verified UltraRAG {BASELINE_VERSION} runtime in {target}",
        file=sys.stderr,
    )
    with tempfile.TemporaryDirectory(
        prefix=".ultrarag-install-",
        dir=target.parent,
    ) as temporary:
        temporary_root = Path(temporary)
        archive_path = temporary_root / "ultrarag.tar.gz"
        extraction_root = temporary_root / "extracted"
        extraction_root.mkdir()
        _download_archive(archive_path)
        extracted = _safe_extract(archive_path, extraction_root)

        if _read_version(extracted) != BASELINE_VERSION:
            raise RuntimeInstallError(
                f"Downloaded UltraRAG version is not {BASELINE_VERSION}"
            )
        actual_tree_hash = _tree_hash(extracted)
        if actual_tree_hash != TREE_SHA256:
            raise RuntimeInstallError(
                "Extracted UltraRAG tree hash mismatch: "
                f"got {actual_tree_hash}, expected {TREE_SHA256}"
            )
        (extracted / MARKER_FILENAME).write_text(
            json.dumps(_expected_marker(), indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )

        try:
            extracted.rename(target)
        except OSError as exc:
            # Another process may have completed the same immutable install.
            if target.exists():
                return validate_managed_runtime(target)
            raise RuntimeInstallError(
                f"Failed to install the managed runtime at {target}"
            ) from exc

    return validate_managed_runtime(target)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="vanilla-ultra-rag-runtime",
        description="Install or validate the pinned clone-free UltraRAG runtime.",
    )
    parser.add_argument(
        "--cache-root",
        type=Path,
        default=os.environ.get(RUNTIME_CACHE_ENV),
        help=f"Cache root (default: ${RUNTIME_CACHE_ENV} or the user cache)",
    )
    parser.add_argument(
        "--offline",
        action="store_true",
        help="Validate an existing runtime without downloading it.",
    )
    return parser


def main() -> None:
    args = _parser().parse_args()
    try:
        path = install_managed_runtime(
            cache_root=args.cache_root,
            allow_download=not args.offline,
        )
    except RuntimeErrorBase as exc:
        raise SystemExit(str(exc)) from exc
    print(path)


if __name__ == "__main__":
    main()
