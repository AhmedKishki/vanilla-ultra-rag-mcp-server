from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from vanilla_ultra_rag_mcp.manifest import BASELINE_COMMIT, BASELINE_VERSION


def _canonical_hash(value: Any) -> str:
    encoded = json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def test_manifest_is_self_consistent() -> None:
    path = (
        Path(__file__).resolve().parents[1]
        / "compatibility"
        / "ultrarag-0.3.0.2-3a709a2.json"
    )
    manifest = json.loads(path.read_text(encoding="utf-8"))

    root_hash = manifest.pop("contract_sha256")
    assert _canonical_hash(manifest) == root_hash
    assert manifest["upstream"]["version"] == BASELINE_VERSION
    assert manifest["upstream"]["git_commit"] == BASELINE_COMMIT
    assert manifest["gateway"]["adds_mcp_components"] is False

    gateway_names: set[str] = set()
    tool_count = 0
    prompt_count = 0
    for server in manifest["servers"]:
        server_hash = server.pop("contract_sha256")
        assert _canonical_hash(server) == server_hash
        namespace = server["namespace"]

        for kind in ("tools", "prompts"):
            for component in server[kind]:
                assert component["contract_sha256"] == _canonical_hash(
                    component["contract"]
                )
                assert component["gateway_name"] == (
                    f"{namespace}_{component['upstream_name']}"
                )
                assert component["gateway_name"] not in gateway_names
                gateway_names.add(component["gateway_name"])

        tool_count += len(server["tools"])
        prompt_count += len(server["prompts"])
        assert server["resources"] == []
        assert server["resource_templates"] == []

    assert len(manifest["servers"]) == 11
    assert tool_count == 78
    assert prompt_count == 26
