from __future__ import annotations

import asyncio
import json
import sys
from collections.abc import Iterator
from contextlib import contextmanager
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from threading import Thread
from typing import Any

from conftest import ultrarag_root
from fastmcp import Client

from vanilla_ultra_rag_mcp.config import resolve_config
from vanilla_ultra_rag_mcp.server import create_gateway

OFFICIAL_RAG_TOOLS = {
    "benchmark_get_data",
    "retriever_retriever_init",
    "retriever_retriever_search",
    "generation_generation_init",
    "generation_generate",
    "custom_output_extract_from_boxed",
    "evaluation_evaluate",
}
OFFICIAL_RAG_PROMPT = "prompt_qa_rag_boxed"


@contextmanager
def _mock_openai() -> Iterator[tuple[str, list[dict[str, Any]]]]:
    requests: list[dict[str, Any]] = []

    class Handler(BaseHTTPRequestHandler):
        def do_POST(self) -> None:
            length = int(self.headers.get("Content-Length", "0"))
            requests.append(json.loads(self.rfile.read(length)))
            payload = {
                "id": "chatcmpl-vanilla-rag-test",
                "object": "chat.completion",
                "created": 0,
                "model": "deterministic-test-model",
                "choices": [
                    {
                        "index": 0,
                        "message": {
                            "role": "assistant",
                            "content": (
                                "The retrieved document identifies the amber marsh. "
                                r"\boxed{amber marsh}"
                            ),
                        },
                        "finish_reason": "stop",
                    }
                ],
                "usage": {
                    "prompt_tokens": 1,
                    "completion_tokens": 1,
                    "total_tokens": 2,
                },
            }
            body = json.dumps(payload).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, _format: str, *args: object) -> None:
            return

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        host, port = server.server_address
        yield f"http://{host}:{port}/v1", requests
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)


def _prompt_text(prompt_result: Any) -> list[str]:
    texts: list[str] = []
    for message in prompt_result.messages:
        content = message.content
        text = getattr(content, "text", None)
        if not isinstance(text, str):
            raise TypeError("The RAG prompt returned non-text content")
        texts.append(text)
    return texts


async def _assert_cpu_rag_flow(workspace: Path, base_url: str) -> None:
    workspace.mkdir(parents=True)
    corpus_path = workspace / "corpus.jsonl"
    corpus_path.write_text(
        json.dumps(
            {
                "id": "source-1",
                "contents": "The cobalt heron nests beside the amber marsh.",
            }
        )
        + "\n",
        encoding="utf-8",
    )
    benchmark_path = workspace / "benchmark.jsonl"
    benchmark_path.write_text(
        json.dumps(
            {
                "question": "Where does the cobalt heron nest?",
                "golden_answers": ["amber marsh"],
            }
        )
        + "\n",
        encoding="utf-8",
    )
    template_path = workspace / "qa_rag_boxed.jinja"
    template_path.write_text(
        "Documents:\n{{documents}}\n\nQuestion: {{question}}\n"
        r"Answer as \boxed{YOUR_ANSWER}."
        "\n",
        encoding="utf-8",
    )
    evaluation_path = workspace / "evaluation.json"
    index_path = workspace / "index" / "bm25"
    config = resolve_config(
        ultrarag_root(),
        workspace / "runtime",
        python_executable=sys.executable,
    )

    async with Client(create_gateway(config)) as client:
        tools = {tool.name for tool in await client.list_tools()}
        prompts = {prompt.name for prompt in await client.list_prompts()}
        assert OFFICIAL_RAG_TOOLS <= tools
        assert OFFICIAL_RAG_PROMPT in prompts

        benchmark = await client.call_tool(
            "benchmark_get_data",
            {
                "benchmark": {
                    "path": str(benchmark_path),
                    "key_map": {
                        "q_ls": "question",
                        "gt_ls": "golden_answers",
                    },
                    "shuffle": False,
                    "seed": 42,
                    "limit": -1,
                    "name": "vanilla-rag-contract",
                }
            },
        )
        q_ls = benchmark.data["q_ls"]
        gt_ls = benchmark.data["gt_ls"]

        retriever_config = {
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
        await client.call_tool("retriever_retriever_init", retriever_config)
        await client.call_tool("retriever_bm25_index", {"overwrite": False})
        await client.call_tool("retriever_retriever_init", retriever_config)
        retrieved = await client.call_tool(
            "retriever_bm25_search",
            {"query_list": q_ls, "top_k": 1},
        )
        ret_psg = retrieved.data["ret_psg"]

        await client.call_tool(
            "generation_generation_init",
            {
                "backend_configs": {
                    "openai": {
                        "api_key": "test-key",
                        "base_url": base_url,
                        "model_name": "deterministic-test-model",
                        "concurrency": 1,
                        "retries": 1,
                        "base_delay": 0,
                    }
                },
                "sampling_params": {"max_tokens": 32, "temperature": 0},
                "extra_params": None,
                "backend": "openai",
            },
        )
        rendered = await client.get_prompt(
            OFFICIAL_RAG_PROMPT,
            {
                "q_ls": json.dumps(q_ls),
                "ret_psg": json.dumps(ret_psg),
                "template": json.dumps(str(template_path)),
            },
        )
        prompt_ls = _prompt_text(rendered)
        assert "amber marsh" in prompt_ls[0]
        assert q_ls[0] in prompt_ls[0]

        generated = await client.call_tool(
            "generation_generate",
            {"prompt_ls": prompt_ls, "system_prompt": ""},
        )
        extracted = await client.call_tool(
            "custom_output_extract_from_boxed",
            {"ans_ls": generated.data["ans_ls"]},
        )
        assert extracted.data["pred_ls"] == ["amber marsh"]

        evaluated = await client.call_tool(
            "evaluation_evaluate",
            {
                "pred_ls": extracted.data["pred_ls"],
                "gt_ls": gt_ls,
                "metrics": ["em"],
                "save_path": str(evaluation_path),
            },
        )
        assert evaluated.data["eval_res"]["avg_em"] == 1.0

    evaluation_files = list(workspace.glob("evaluation_*.json"))
    assert len(evaluation_files) == 1
    assert json.loads(evaluation_files[0].read_text(encoding="utf-8"))["avg_em"] == 1.0


def test_official_vanilla_rag_surface_and_cpu_flow(tmp_path: Path) -> None:
    with _mock_openai() as (base_url, requests):
        asyncio.run(_assert_cpu_rag_flow(tmp_path / "vanilla-rag", base_url))

    assert len(requests) == 1
    messages = requests[0]["messages"]
    assert "amber marsh" in messages[-1]["content"]
    assert "Where does the cobalt heron nest?" in messages[-1]["content"]
