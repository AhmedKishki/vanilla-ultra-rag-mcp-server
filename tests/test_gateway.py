from __future__ import annotations

import asyncio
import json
import os
import sys
from pathlib import Path
from typing import Any

from conftest import ultrarag_root
from fastmcp import Client
from fastmcp.client.transports import StdioTransport

from vanilla_ultra_rag_mcp.config import resolve_config
from vanilla_ultra_rag_mcp.instructions import SERVER_INSTRUCTIONS
from vanilla_ultra_rag_mcp.manifest import SERVER_SPECS
from vanilla_ultra_rag_mcp.server import _child_environment, create_gateway


def _dump(component: Any) -> dict[str, Any]:
    return component.model_dump(mode="json", by_alias=True, exclude_none=False)


async def _assert_contract_parity(workspace: Path) -> None:
    config = resolve_config(
        ultrarag_root(),
        workspace,
        python_executable=sys.executable,
    )
    expected_tools: dict[str, dict[str, Any]] = {}
    expected_prompts: dict[str, dict[str, Any]] = {}
    expected_resources: list[dict[str, Any]] = []
    expected_templates: list[dict[str, Any]] = []

    for spec in SERVER_SPECS:
        transport = StdioTransport(
            command=str(config.python_executable),
            args=[str(config.ultrarag_root / spec.relative_entrypoint)],
            env=_child_environment(config, spec.namespace),
            cwd=str(config.workspace_root),
            log_file=config.workspace_root / "logs" / f"direct-{spec.namespace}.log",
        )
        async with Client(transport) as client:
            for tool in await client.list_tools():
                contract = _dump(tool)
                contract["name"] = f"{spec.namespace}_{contract['name']}"
                expected_tools[contract["name"]] = contract
            for prompt in await client.list_prompts():
                contract = _dump(prompt)
                contract["name"] = f"{spec.namespace}_{contract['name']}"
                expected_prompts[contract["name"]] = contract
            expected_resources.extend(
                _dump(item) for item in await client.list_resources()
            )
            expected_templates.extend(
                _dump(item) for item in await client.list_resource_templates()
            )

    async with Client(create_gateway(config)) as client:
        actual_tools = {item.name: _dump(item) for item in await client.list_tools()}
        actual_prompts = {
            item.name: _dump(item) for item in await client.list_prompts()
        }
        actual_resources = [_dump(item) for item in await client.list_resources()]
        actual_templates = [
            _dump(item) for item in await client.list_resource_templates()
        ]

    assert actual_tools == expected_tools
    assert actual_prompts == expected_prompts
    assert actual_resources == expected_resources == []
    assert actual_templates == expected_templates == []


def test_gateway_is_exact_namespaced_union(tmp_path: Path) -> None:
    asyncio.run(_assert_contract_parity(tmp_path / "parity-workspace"))


async def _assert_bm25_state_survives_calls(workspace: Path) -> None:
    corpus_path = workspace / "corpus.jsonl"
    workspace.mkdir(parents=True)
    documents = [
        {"contents": "The cobalt heron nests beside the amber marsh."},
        {"contents": "The quartz badger lives beneath the northern ridge."},
    ]
    corpus_path.write_text(
        "".join(json.dumps(document) + "\n" for document in documents),
        encoding="utf-8",
    )
    index_path = workspace / "indexes" / "bm25"
    config = resolve_config(
        ultrarag_root(),
        workspace / "runtime",
        python_executable=sys.executable,
    )
    init_arguments = {
        "model_name_or_path": "",
        "backend_configs": {
            "bm25": {
                "lang": "en",
                "tokenizer": "default",
                "save_path": str(index_path),
            }
        },
        "batch_size": 2,
        "corpus_path": str(corpus_path),
        "gpu_ids": None,
        "is_multimodal": False,
        "backend": "bm25",
        "index_backend": "faiss",
        "index_backend_configs": {},
        "is_demo": False,
        "collection_name": "",
    }

    async with Client(create_gateway(config)) as client:
        await client.call_tool("retriever_retriever_init", init_arguments)
        await client.call_tool("retriever_bm25_index", {"overwrite": False})
        # UltraRAG 0.3.0.2 returns numeric BM25 row IDs immediately after a new
        # build. Reinitialization reloads the saved index and attaches passages.
        await client.call_tool("retriever_retriever_init", init_arguments)
        assert len(await client.list_tools()) == 78
        result = await client.call_tool(
            "retriever_bm25_search",
            {"query_list": ["cobalt heron amber marsh"], "top_k": 1},
        )

    assert result.data == {
        "ret_psg": [["The cobalt heron nests beside the amber marsh."]]
    }


def test_bm25_child_state_survives_sequential_proxy_calls(tmp_path: Path) -> None:
    asyncio.run(_assert_bm25_state_survives_calls(tmp_path / "bm25-workspace"))


async def _assert_console_entrypoint(workspace: Path) -> None:
    executable = Path(sys.executable).parent / "vanilla-ultra-rag-mcp"
    environment = dict(os.environ)
    managed_cache = environment.get("VANILLA_ULTRARAG_CACHE_ROOT")
    if managed_cache:
        environment.pop("ULTRARAG_ROOT", None)
        arguments = [
            "--workspace-root",
            str(workspace),
            "--runtime-cache-root",
            managed_cache,
            "--offline",
        ]
    else:
        arguments = [
            "--ultrarag-root",
            str(ultrarag_root()),
            "--workspace-root",
            str(workspace),
        ]
    transport = StdioTransport(
        command=str(executable),
        args=arguments,
        env=environment,
        log_file=workspace / "gateway-stderr.log",
    )
    async with Client(transport) as client:
        assert client.initialize_result is not None
        assert client.initialize_result.instructions == SERVER_INSTRUCTIONS
        assert client.initialize_result.serverInfo.name == "vanilla-ultra-rag-mcp"
        assert len(await client.list_tools()) == 78
        assert len(await client.list_prompts()) == 26
        assert await client.list_resources() == []
        assert await client.list_resource_templates() == []


def test_installed_console_entrypoint_uses_stdio(tmp_path: Path) -> None:
    workspace = tmp_path / "stdio-workspace"
    workspace.mkdir()
    asyncio.run(_assert_console_entrypoint(workspace))
