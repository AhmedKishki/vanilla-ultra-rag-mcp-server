"""Generate the reviewed MCP contract for the pinned UltraRAG checkout."""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import sys
import tempfile
from importlib.metadata import version
from pathlib import Path
from typing import Any

from fastmcp import Client
from fastmcp.client.transports import StdioTransport

from vanilla_ultra_rag_mcp.config import resolve_config
from vanilla_ultra_rag_mcp.manifest import (
    BASELINE_COMMIT,
    BASELINE_VERSION,
    SERVER_SPECS,
    STATEFUL_NAMESPACES,
)
from vanilla_ultra_rag_mcp.server import _child_environment


def _canonical_hash(value: Any) -> str:
    encoded = json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _component(component: Any, namespace: str) -> dict[str, Any]:
    contract = component.model_dump(mode="json", by_alias=True, exclude_none=False)
    return {
        "upstream_name": contract["name"],
        "gateway_name": f"{namespace}_{contract['name']}",
        "contract_sha256": _canonical_hash(contract),
        "contract": contract,
    }


async def _generate(ultrarag_root: Path, python: Path) -> dict[str, Any]:
    with tempfile.TemporaryDirectory(prefix="vanilla-ultra-rag-manifest-") as temp:
        config = resolve_config(
            ultrarag_root=ultrarag_root,
            workspace_root=Path(temp),
            python_executable=python,
        )
        servers: list[dict[str, Any]] = []

        for spec in SERVER_SPECS:
            transport = StdioTransport(
                command=str(config.python_executable),
                args=[str(config.ultrarag_root / spec.relative_entrypoint)],
                env=_child_environment(config, spec.namespace),
                cwd=str(config.workspace_root),
                log_file=config.workspace_root
                / "logs"
                / f"manifest-{spec.namespace}.log",
            )
            async with Client(transport) as client:
                tools = await client.list_tools()
                prompts = await client.list_prompts()
                resources = await client.list_resources()
                templates = await client.list_resource_templates()

            server = {
                "namespace": spec.namespace,
                "entrypoint": spec.relative_entrypoint.as_posix(),
                "persistent_state": spec.namespace in STATEFUL_NAMESPACES,
                "tools": [_component(item, spec.namespace) for item in tools],
                "prompts": [_component(item, spec.namespace) for item in prompts],
                "resources": [
                    item.model_dump(mode="json", by_alias=True, exclude_none=False)
                    for item in resources
                ],
                "resource_templates": [
                    item.model_dump(mode="json", by_alias=True, exclude_none=False)
                    for item in templates
                ],
            }
            server["contract_sha256"] = _canonical_hash(server)
            servers.append(server)

    manifest = {
        "format_version": 1,
        "upstream": {
            "package": "ultrarag",
            "version": BASELINE_VERSION,
            "git_commit": BASELINE_COMMIT,
            "python": ">=3.11,<3.13",
            "fastmcp": ">=3.3.1,<3.4.5",
        },
        "gateway": {
            "name": "vanilla-ultra-rag-mcp",
            "fastmcp_version": version("fastmcp"),
            "name_rule": "{namespace}_{upstream_name}",
            "adds_mcp_components": False,
        },
        "servers": servers,
    }
    manifest["contract_sha256"] = _canonical_hash(manifest)
    return manifest


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--ultrarag-root", type=Path, required=True)
    parser.add_argument("--python", type=Path, default=Path(sys.executable))
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    manifest = asyncio.run(_generate(args.ultrarag_root, args.python))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(args.output)


if __name__ == "__main__":
    main()
