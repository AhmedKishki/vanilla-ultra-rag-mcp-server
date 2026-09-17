"""Exercise vanilla corpus ingestion, chunking, and BM25 through stdio MCP."""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
import tempfile
from collections import Counter
from pathlib import Path
from typing import Any

from fastmcp import Client
from fastmcp.client.transports import StdioTransport

from vanilla_ultra_rag_mcp.source_selection import input_files, stage_input_files


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Verify PDF and EPUB sources through vanilla UltraRAG's existing "
            "corpus, chunking, and BM25 MCP tools. Other file types are ignored."
        )
    )
    parser.add_argument("source", type=Path, help="Document file or directory")
    parser.add_argument(
        "--workspace",
        type=Path,
        required=True,
        help="New or empty directory for generated verification data",
    )
    parser.add_argument(
        "--ultrarag-root",
        type=Path,
        default=os.environ.get("ULTRARAG_ROOT"),
        help="Optional pinned checkout; managed runtime is used if omitted",
    )
    parser.add_argument(
        "--runtime-cache-root",
        type=Path,
        default=os.environ.get("VANILLA_ULTRARAG_CACHE_ROOT"),
        help="Override the managed runtime cache root",
    )
    parser.add_argument("--offline", action="store_true")
    parser.add_argument(
        "--query",
        default="artificial intelligence labour environment supply chains",
        help="BM25 query used for the retrieval check",
    )
    parser.add_argument("--top-k", type=int, default=5)
    parser.add_argument("--chunk-size", type=int, default=500)
    return parser


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    return [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def _require_fresh_targets(paths: list[Path]) -> None:
    existing = [path for path in paths if path.exists()]
    if existing:
        formatted = "\n".join(f"- {path}" for path in existing)
        raise RuntimeError(
            "Verification refuses to overwrite existing output. "
            f"Choose a new workspace or move these paths:\n{formatted}"
        )


async def _verify(args: argparse.Namespace) -> dict[str, Any]:
    source = args.source.expanduser().resolve()
    workspace = args.workspace.expanduser().resolve()

    if not source.exists():
        raise FileNotFoundError(f"Source does not exist: {source}")
    if args.top_k < 1 or args.chunk_size < 1:
        raise ValueError("--top-k and --chunk-size must be positive")

    inputs = input_files(source)
    if not inputs:
        raise RuntimeError(f"No PDF or EPUB source documents found beneath {source}")

    duplicate_stems = {
        stem: count
        for stem, count in Counter(path.stem for path in inputs).items()
        if count > 1
    }
    if duplicate_stems:
        raise RuntimeError(
            "Vanilla corpus IDs use file stems, so duplicate stems cannot be "
            f"verified unambiguously: {duplicate_stems}"
        )

    corpus_path = workspace / "corpus" / "documents.jsonl"
    chunks_path = workspace / "chunks" / "chunks.jsonl"
    index_path = workspace / "indexes" / "bm25"
    report_path = workspace / "verification-report.json"
    _require_fresh_targets([corpus_path, chunks_path, index_path, report_path])
    (workspace / "logs").mkdir(parents=True, exist_ok=True)

    executable = Path(sys.executable).parent / "vanilla-ultra-rag-mcp"
    if not executable.is_file():
        raise FileNotFoundError(
            f"Gateway executable not found beside this interpreter: {executable}"
        )

    gateway_arguments = [
        "--workspace-root",
        str(workspace / "runtime"),
    ]
    if args.ultrarag_root is not None:
        gateway_arguments.extend(
            ["--ultrarag-root", str(args.ultrarag_root.expanduser().resolve())]
        )
    if args.runtime_cache_root is not None:
        gateway_arguments.extend(
            [
                "--runtime-cache-root",
                str(args.runtime_cache_root.expanduser().resolve()),
            ]
        )
    if args.offline:
        gateway_arguments.append("--offline")

    transport = StdioTransport(
        command=str(executable),
        args=gateway_arguments,
        log_file=workspace / "logs" / "gateway-stderr.log",
    )

    print(f"[1/5] Found {len(inputs)} PDF/EPUB source files")
    async with Client(transport) as client:
        tools = {tool.name for tool in await client.list_tools()}
        required_tools = {
            "corpus_build_text_corpus",
            "corpus_chunk_documents",
            "retriever_retriever_init",
            "retriever_bm25_index",
            "retriever_bm25_search",
        }
        missing_tools = required_tools - tools
        if missing_tools:
            raise RuntimeError(f"Gateway is missing required tools: {missing_tools}")

        print("[2/5] Building the PDF/EPUB-only vanilla text corpus")
        with tempfile.TemporaryDirectory(
            prefix="vanilla-ultrarag-sources-"
        ) as temporary:
            filtered_source = stage_input_files(
                source,
                inputs,
                Path(temporary),
            )
            await client.call_tool(
                "corpus_build_text_corpus",
                {
                    "parse_file_path": str(filtered_source),
                    "text_corpus_save_path": str(corpus_path),
                },
            )
        corpus_rows = _read_jsonl(corpus_path)
        if len(corpus_rows) != len(inputs):
            raise RuntimeError(
                f"Expected {len(inputs)} corpus rows, got {len(corpus_rows)}"
            )
        if any(not str(row.get("contents", "")).strip() for row in corpus_rows):
            raise RuntimeError("At least one corpus record has empty contents")
        expected_document_ids = {path.stem for path in inputs}
        actual_document_ids = {str(row.get("id", "")) for row in corpus_rows}
        if actual_document_ids != expected_document_ids:
            raise RuntimeError(
                "Corpus/source ID mismatch: "
                f"missing={sorted(expected_document_ids - actual_document_ids)}, "
                f"unexpected={sorted(actual_document_ids - expected_document_ids)}"
            )

        print("[3/5] Chunking the extracted corpus")
        await client.call_tool(
            "corpus_chunk_documents",
            {
                "raw_chunk_path": str(corpus_path),
                "chunk_backend_configs": {"token": {"chunk_overlap": 64}},
                "chunk_backend": "token",
                "tokenizer_or_token_counter": "word",
                "chunk_size": args.chunk_size,
                "chunk_path": str(chunks_path),
                "use_title": True,
            },
        )
        chunk_rows = _read_jsonl(chunks_path)
        document_ids = actual_document_ids
        represented_ids = {str(row["doc_id"]) for row in chunk_rows}
        if represented_ids != document_ids:
            missing_ids = sorted(document_ids - represented_ids)
            raise RuntimeError(f"Documents missing from chunks: {missing_ids}")
        if any(not str(row.get("contents", "")).strip() for row in chunk_rows):
            raise RuntimeError("At least one chunk has empty contents")

        init_arguments = {
            "model_name_or_path": "",
            "backend_configs": {
                "bm25": {
                    "lang": "en",
                    "tokenizer": "default",
                    "save_path": str(index_path),
                }
            },
            "batch_size": 32,
            "corpus_path": str(chunks_path),
            "gpu_ids": None,
            "is_multimodal": False,
            "backend": "bm25",
            "index_backend": "faiss",
            "index_backend_configs": {},
            "is_demo": False,
            "collection_name": "",
        }
        print("[4/5] Building and reloading the vanilla BM25 index")
        await client.call_tool("retriever_retriever_init", init_arguments)
        await client.call_tool("retriever_bm25_index", {"overwrite": False})
        await client.call_tool("retriever_retriever_init", init_arguments)

        print(f"[5/5] Searching BM25 for: {args.query!r}")
        result = await client.call_tool(
            "retriever_bm25_search",
            {"query_list": [args.query], "top_k": args.top_k},
        )
        passages = result.data["ret_psg"][0]
        if not passages:
            raise RuntimeError("BM25 returned no passages")

    report = {
        "status": "passed",
        "source": str(source),
        "workspace": str(workspace),
        "supported_input_files": len(inputs),
        "source_files": [
            path.name if source.is_file() else path.relative_to(source).as_posix()
            for path in inputs
        ],
        "extensions": dict(
            sorted(Counter(path.suffix.lower() for path in inputs).items())
        ),
        "corpus_rows": len(corpus_rows),
        "chunks": len(chunk_rows),
        "documents_represented": len(represented_ids),
        "query": args.query,
        "retrieved_passages": passages,
        "limits": (
            "This verifies mechanical coverage and retrieval only; it does not "
            "prove extraction fidelity, ranking quality, or citation accuracy."
        ),
    }
    report_path.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return report


def main() -> None:
    args = _parser().parse_args()
    report = asyncio.run(_verify(args))
    print(
        "PASS: "
        f"{report['corpus_rows']} documents -> {report['chunks']} chunks -> "
        f"{len(report['retrieved_passages'])} passages"
    )
    print(f"Report: {Path(report['workspace']) / 'verification-report.json'}")
    print("Top results:")
    for index, passage in enumerate(report["retrieved_passages"], 1):
        preview = " ".join(str(passage).split())[:180]
        print(f"  {index}. {preview}")


if __name__ == "__main__":
    main()
