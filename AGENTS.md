# AGENTS.md

This file is the engineering guide for AI coding agents working in
`vanilla-ultra-rag-mcp-server`.

## Project objective

Provide one local stdio MCP server, `vanilla-ultra-rag-mcp`, that exposes the
existing MCP surface of one pinned, unmodified UltraRAG release to general MCP
clients and AI agents.

This repository is an external compatibility and presentation layer. It is not
an UltraRAG fork and must not become a place for new RAG behavior. Other MCP
servers or extensions belong in separate repositories.

Current baseline:

- UltraRAG version: `0.3.0.2`
- UltraRAG commit: `3a709a2aea3fbe46acca59c422621c94b6e86857`
- Python: `>=3.11,<3.13`
- FastMCP: `3.4.0`
- Captured surface: 78 tools, 26 prompts, no resources or resource templates

## Non-negotiable vanilla contract

- Retain the prominent UltraRAG acknowledgement in `README.md`, the root
  `NOTICE`, upstream project links, license information, and the independent
  project disclaimer.
- Credit THUNLP, NEUIR, OpenBMB, AI9stars, and the upstream contributors using
  the wording supported by UltraRAG's own README. Do not imply endorsement.
- Do not edit or patch UltraRAG source code.
- Do not reimplement an upstream tool or prompt.
- Do not change upstream input schemas, output schemas, return values, errors,
  or state semantics.
- Do not add custom MCP tools, prompts, resources, retrieval algorithms,
  metadata, filters, citation behavior, or project enforcement.
- Namespacing is the only intentional component-name adaptation.
- Keep the selected upstream version and commit explicit and fail closed on
  drift.
- Keep MCP stdout free of logs, progress text, and banners.
- Keep generated data outside the managed UltraRAG runtime.
If a requested change violates this contract, it belongs in a separately named
repository rather than this one.

## Documentation responsibilities

- `README.md` is a standalone user manual: capability summary, installation,
  MCP configuration, concrete usage, expected results, storage, and user-visible
  limitations. It must not compare or link to sibling MCP-server projects.
- `AGENT_GUIDE.md` is operational policy for an AI agent calling MCP tools. Do
  not put installation or contributor workflows there.
- `AGENTS.md` is this engineering contract. Do not turn it into user-facing
  setup documentation.
- `NOTICE` contains attribution and legal notices.
- Compatibility JSON records the machine-reviewed upstream interface.

## Architecture

```text
MCP client
   │ stdio
   ▼
vanilla-ultra-rag-mcp
   │ persistent FastMCP proxy providers
   ├── benchmark
   ├── corpus
   ├── custom
   ├── evaluation
   ├── generation
   ├── memory
   ├── prompt
   ├── reranker
   ├── retriever
   ├── router
   └── sayhello
          │
          ▼
verified UltraRAG runtime snapshot
```

The aggregate gateway keeps one child process per upstream component alive for
the outer MCP session. This is required because initialization state must
survive between calls such as `retriever_init` and `retriever_search`.

## Repository map

- `src/vanilla_ultra_rag_mcp/server.py`: aggregate stdio server and child
  lifecycle.
- `src/vanilla_ultra_rag_mcp/config.py`: runtime, revision, interpreter, and
  workspace validation.
- `src/vanilla_ultra_rag_mcp/runtime.py`: download, extraction, archive hash,
  tree hash, cache, and offline validation.
- `src/vanilla_ultra_rag_mcp/instructions.py`: concise instructions returned in
  the MCP initialization response.
- `src/vanilla_ultra_rag_mcp/manifest.py`: pinned upstream server inventory.
- `src/vanilla_ultra_rag_mcp/ui.py`: launcher for the existing upstream UI.
- `compatibility/*.json`: reviewed discovery contract for the pinned release.
- `scripts/verify_corpus.py`: end-to-end document ingestion and CPU BM25
  verifier through real stdio MCP.
- `scripts/generate_compatibility_manifest.py`: deliberate contract-regeneration
  utility.
- `tests/`: contract parity, real stdio, and persistent BM25 state tests.
- `AGENT_GUIDE.md`: operational instructions for agents using the MCP tools;
  this file instead governs agents modifying the repository.

## Runtime and storage model

Normal startup does not require an UltraRAG Git clone. It downloads the official
commit archive, verifies `ARCHIVE_SHA256`, safely extracts it, verifies
`TREE_SHA256`, and stores it under the platform user cache. The gateway validates
the snapshot on every start.

An explicit `--ultrarag-root` checkout is a development-only override. It must
be at the baseline commit with no tracked modifications.

`--workspace-root` controls the child working directory, logs, and UI storage.
Upstream tools may still accept arbitrary caller-provided paths; the vanilla
gateway documents project separation but does not enforce it.

Prevent Python bytecode from being written into the verified runtime. Any new
runtime output must go to the external workspace or an explicit user-selected
path.

## Dependency and packaging rules

- Use `uv` and keep `uv.lock` current.
- Keep the UltraRAG dependency pinned to the reviewed commit archive and hash.
- Do not replace the managed snapshot with an unbounded branch or `main` URL.
- Avoid adding GPU dependencies to the default CPU-tested installation.
- Treat optional upstream backends honestly: expose them when upstream exposes
  them, but do not claim they are installed or tested when they are not.
- The Python distribution and console command remain
  `vanilla-ultra-rag-mcp`; the Git repository is
  `vanilla-ultra-rag-mcp-server`.

## Safe change workflow

Before editing:

1. Read the affected source, tests, compatibility manifest, and upstream entrypoint.
2. Decide whether the change is adapter behavior or new RAG behavior.
3. Reject or relocate changes that violate the vanilla contract.

After editing, run:

```bash
uv lock --check
uv run ruff format --check .
uv run ruff check .
uv run pytest -q
uv run python -m compileall -q src scripts tests
```

For runtime changes, also test a fresh managed cache and then validate it with
`vanilla-ultra-rag-runtime --offline`. For MCP transport changes, launch the
installed console command with a real FastMCP client and verify discovery,
instructions, and one tool call.

For document-path changes, run `scripts/verify_corpus.py` against a representative
PDF/EPUB collection, including unrelated Markdown files to verify exclusion,
using a fresh external workspace.

## Updating UltraRAG deliberately

Never accept upstream drift automatically. To support a new UltraRAG revision:

1. inspect the new official commit;
2. update the pinned version, commit, archive SHA-256, and tree SHA-256;
3. regenerate and review the compatibility manifest;
4. inspect every added, removed, or changed MCP component;
5. run parity, stdio, managed-runtime, CPU retrieval, and real-corpus tests; and
6. release a new version of this package.

Do not regenerate a manifest merely to make a failing compatibility test pass.

## Known limitations

- CPU BM25 is tested; dense FAISS, generation, reranking, and GPU/vLLM paths are
  not all validated by the default test suite.
- The upstream UI uses its own pipeline processes and targets Milvus or Qdrant
  for its knowledge-base indexing views.
- Vanilla UltraRAG does not provide hard project isolation, metadata filtering,
  or page-level citation locators.
- Direct recursive corpus ingestion includes every upstream-supported file
  beneath the supplied path; there is no vanilla include/exclude filter. The
  repository verifier works around this with a temporary PDF/EPUB-only view.
