# Agent guide for `vanilla-ultra-rag-mcp`

This server aggregates the existing UltraRAG MCP servers. It does not add or
change RAG behavior. Tool names use `<component>_<upstream-tool-name>`.

Its intended research workflow uses original PDF and EPUB sources. Do not ingest
Markdown notes, source maps, drafts, or other generated research files as source
documents. The upstream corpus tool accepts those formats, and the vanilla
gateway does not technically block them. When a directory is mixed, require a
PDF/EPUB-only input directory or use the repository's filtered terminal
verifier.

## Client instruction snippet

For clients that do not surface MCP server instructions, add this to the
agent's project instructions:

> Use `vanilla-ultra-rag-mcp` as an unmodified, stateful UltraRAG interface.
> Follow each MCP schema exactly, initialize a component before dependent
> calls, keep every input/output path inside this project's workspace, and ask
> before writes, overwrites, network/API use, or GPU/heavy operations. Do not
> assume project enforcement, metadata filters, or citation locators exist.

## General rules

- Inspect and follow each tool's MCP schema; do not invent parameter names.
- Use absolute paths beneath the workspace supplied by the user.
- Confirm before calling tools that write, overwrite, index, evaluate, start a
  service, use external credentials, or load a large/GPU model.
- A component's `build` tool produces UltraRAG server metadata. It is not corpus
  ingestion or retrieval indexing.
- Initialization state lasts only while this MCP server and its child process
  remain alive.

## Common call sequences

Text corpus:

1. `corpus_build_text_corpus`
2. `corpus_chunk_documents`

Dense retrieval when creating an index:

1. `retriever_retriever_init`
2. `retriever_retriever_embed`
3. `retriever_retriever_index`
4. `retriever_retriever_search`

Dense retrieval with an existing index:

1. `retriever_retriever_init`
2. `retriever_retriever_search`

BM25:

1. `retriever_retriever_init` with `backend` set to `bm25`
2. `retriever_bm25_index` when the index must be created
3. After creating an index, call `retriever_retriever_init` again to load the
   saved index (an upstream `0.3.0.2` lifecycle requirement)
4. `retriever_bm25_search`

Reranking and generation require their respective initialization tools first.
Some backends require network credentials, optional dependencies, or GPU
resources; follow the upstream tool description and configured environment.

## Important vanilla limitations

- Tool paths and collection names are caller-controlled; the gateway is not a
  project sandbox.
- PDF/EPUB-only ingestion is an agent policy, not an enforced gateway boundary.
- Search results have the same structure as upstream UltraRAG and may lack
  structured metadata, scores, and citation locators.
- Direct searches return data to the MCP client but do not create a separate
  results file.
- Pipeline memory snapshots are produced by UltraRAG's pipeline runner, which
  this vanilla MCP gateway does not wrap.
- Project scoping, read-only search, provenance enrichment, and research-library
  conveniences belong in separately named extension servers.
