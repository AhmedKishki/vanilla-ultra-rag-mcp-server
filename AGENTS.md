# AGENTS.md

The engineering contract for `vanilla-ultra-rag-mcp-server`: the rules a change has to be argued against, and the boundaries that keep it a compatibility layer rather than a fork.

This repository is an external compatibility and presentation layer. It is not an UltraRAG fork and must not become a place for new RAG behavior. Other MCP servers or extensions belong in separate repositories.

## Project objective

Provide one local stdio MCP server, `vanilla-ultra-rag-mcp`, that exposes the existing MCP surface of one pinned, unmodified UltraRAG release to general MCP clients and AI agents.

| Baseline | Value |
|---|---|
| UltraRAG version | `0.3.0.2` |
| UltraRAG commit | `3a709a2aea3fbe46acca59c422621c94b6e86857` |
| Python | `>=3.11,<3.13` |
| FastMCP | `3.4.0` |
| Captured surface | 78 tools, 26 prompts, no resources or resource templates |

## Non-negotiable vanilla contract

- Retain the prominent UltraRAG acknowledgement in `README.md`, the root `NOTICE`, upstream project links, license information, and the independent project disclaimer.
  - Credit THUNLP, NEUIR, OpenBMB, AI9stars, and the upstream contributors using the wording supported by UltraRAG's own README.
  - Do not imply endorsement.
- Do not edit or patch UltraRAG source code.
- Do not reimplement an upstream tool or prompt.
- Do not change upstream input schemas, output schemas, return values, errors, or state semantics.
- Do not add custom MCP tools, prompts, resources, retrieval algorithms, metadata, filters, citation behavior, or project enforcement.
- Namespacing is the only intentional component-name adaptation.
  - Optional `--namespace` filtering may expose a subset of the same unmodified components.
  - Omitting it must always preserve the complete captured surface.
- Keep the selected upstream version and commit explicit and fail closed on drift.
- Keep MCP stdout free of logs, progress text, and banners.
- Keep generated data outside the managed UltraRAG runtime.
  - A requested change that violates this contract belongs in a separately named repository rather than this one.

## Documentation responsibilities

- `README.md` is a standalone user manual: capability summary, installation, MCP configuration, concrete usage, expected results, storage, and user-visible limitations.
  - It must not compare or link to sibling MCP-server projects.
- `AGENT_GUIDE.md` is operational policy for an AI agent calling MCP tools.
  - Do not put installation or contributor workflows there.
- `AGENTS.md` is this engineering contract.
  - Do not turn it into user-facing setup documentation.
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

- The aggregate gateway keeps one child process per upstream component alive for the outer MCP session.
  - This is required because initialization state must survive between calls such as `retriever_init` and `retriever_search`.

## Repository map

| Path | Holds |
|---|---|
| `src/vanilla_ultra_rag_mcp/server.py` | aggregate stdio server and child lifecycle |
| `src/vanilla_ultra_rag_mcp/config.py` | runtime, revision, interpreter, and workspace validation |
| `src/vanilla_ultra_rag_mcp/runtime.py` | download, extraction, archive hash, tree hash, cache, and offline validation |
| `src/vanilla_ultra_rag_mcp/tree_manifest.py` | generated per-file digests for the pinned tree, used to name a differing path |
| `src/vanilla_ultra_rag_mcp/instructions.py` | concise instructions returned in the MCP initialization response |
| `src/vanilla_ultra_rag_mcp/manifest.py` | pinned upstream server inventory |
| `src/vanilla_ultra_rag_mcp/ui.py` | launcher for the existing upstream UI |
| `compatibility/*.json` | reviewed discovery contract for the pinned release |
| `scripts/verify_corpus.py` | end-to-end document ingestion and CPU BM25 verifier through real stdio MCP |
| `scripts/generate_compatibility_manifest.py` | deliberate contract-regeneration utility |
| `scripts/generate_tree_manifest.py` | deliberate pinned-tree digest regeneration utility |
| `tests/` | contract parity, real stdio, and persistent BM25 state tests |
| `AGENT_GUIDE.md` | operational instructions for agents using the MCP tools; this file instead governs agents modifying the repository |

## Runtime and storage model

- Normal startup does not require an UltraRAG Git clone.
  - It downloads the official commit archive, verifies `ARCHIVE_SHA256`, safely extracts it, verifies `TREE_SHA256`, and stores it under the platform user cache.
  - The gateway validates the snapshot on every start.
- `src/vanilla_ultra_rag_mcp/tree_manifest.py` records the SHA-256 of every file in the pinned tree, so a validation failure can name the differing path.
  - Regenerate it with `scripts/generate_tree_manifest.py` whenever `TREE_SHA256` changes, and change them in the same commit.
- An explicit `--ultrarag-root` checkout is a development-only override.
  - It must be at the baseline commit with no tracked modifications.
- `--workspace-root` controls the child working directory, logs, and UI storage.
  - Upstream tools may still accept arbitrary caller-provided paths.
  - The vanilla gateway documents project separation but does not enforce it.
- Prevent Python bytecode from being written into the verified runtime.
  - Any new runtime output must go to the external workspace or an explicit user-selected path.
- `install_managed_runtime` leaves the verified tree read-only — `0444` files, `0555` directories — and prints the command that undoes it.
  - An installed tree must therefore never be edited in place to make it usable: validation is read-only and a repaired tree is a different tree.

## Dependency and packaging rules

- Use `uv` and keep `uv.lock` current.
- Keep the UltraRAG dependency pinned to the reviewed commit archive and hash.
- Do not replace the managed snapshot with an unbounded branch or `main` URL.
- Avoid adding GPU dependencies to the default CPU-tested installation.
- Treat optional upstream backends honestly.
  - Expose them when upstream exposes them.
  - Do not claim they are installed or tested when they are not.
- The Python distribution and console command remain `vanilla-ultra-rag-mcp`; the Git repository is `vanilla-ultra-rag-mcp-server`.

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

Then run the check that matches the kind of change:

- A runtime change needs a fresh managed cache tested, then validated with `vanilla-ultra-rag-runtime --offline`.
- An MCP transport change needs the installed console command launched with a real FastMCP client, with discovery, instructions, and one tool call verified.
- A document-path change needs `scripts/verify_corpus.py` run against a representative PDF/EPUB collection, including unrelated Markdown files to verify exclusion, using a fresh external workspace.

## Updating UltraRAG deliberately

Never accept upstream drift automatically. To support a new UltraRAG revision:

1. Inspect the new official commit.
2. Update the pinned version, commit, archive SHA-256, and tree SHA-256, and regenerate `tree_manifest.py` from the validated new tree.
3. Regenerate and review the compatibility manifest.
4. Inspect every added, removed, or changed MCP component.
5. Run parity, stdio, managed-runtime, CPU retrieval, and real-corpus tests.
6. Release a new version of this package.

Do not regenerate a manifest merely to make a failing compatibility test pass.

## Known limitations

- CPU BM25 is tested; dense FAISS, generation, reranking, and GPU/vLLM paths are not all validated by the default test suite.
- The upstream UI uses its own pipeline processes and targets Milvus or Qdrant for its knowledge-base indexing views.
- Vanilla UltraRAG does not provide hard project isolation, metadata filtering, or page-level citation locators.
- Direct recursive corpus ingestion includes every upstream-supported file beneath the supplied path; there is no vanilla include/exclude filter.
  - The repository verifier works around this with a temporary PDF/EPUB-only view.
