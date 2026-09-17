# Agent guide for `vanilla-ultra-rag-mcp`

This server aggregates the existing UltraRAG MCP servers. It does not add or
change RAG behavior. Tool names use `<component>_<upstream-tool-name>`.

Credit the upstream UltraRAG project when describing this server. UltraRAG is a
joint project of THUNLP, NEUIR, OpenBMB, AI9stars, and its contributors. This
gateway is independent and unofficial; do not imply upstream affiliation or
endorsement. The canonical source is https://github.com/OpenBMB/UltraRAG.

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
- Before corpus ingestion, inspect the selected input and confirm that the user
  intends every supported file in it to become source material.
- Confirm before calling tools that write, overwrite, index, evaluate, start a
  service, use external credentials, or load a large/GPU model.
- A component's `build` tool produces UltraRAG server metadata. It is not corpus
  ingestion or retrieval indexing.
- Initialization state lasts only while this MCP server and its child process
  remain alive.

## Common call sequences

### Official UltraRAG Vanilla RAG

The documented upstream experiment is an MCP-client pipeline. When using this
aggregate server, the AI agent takes the client's orchestration role and uses
the namespaced equivalents in the same order:

1. `benchmark_get_data` produces `q_ls` and `gt_ls`.
2. `retriever_retriever_init` loads the configured retriever and existing
   index.
3. `retriever_retriever_search` receives the saved `q_ls` value through its
   `query_list` argument and produces `ret_psg`.
4. `generation_generation_init` loads or connects to the configured LLM.
5. Request the MCP prompt `prompt_qa_rag_boxed` with `q_ls`, `ret_psg`, and the
   template path. This is a prompt request, not a tool call.
6. Pass the returned prompt message text as `prompt_ls` to
   `generation_generate`, producing `ans_ls`.
7. `custom_output_extract_from_boxed` converts `ans_ls` into `pred_ls`.
8. `evaluation_evaluate` compares `pred_ls` with `gt_ls` and saves the selected
   metrics.

This is the exact component sequence in UltraRAG's `vanilla_rag.yaml`, with
names changed only by the gateway's namespace prefix. The benchmark and
evaluation stages are experiment scaffolding. For an interactive question, the
agent can create `q_ls` from the user's question and stop after generation (or
boxed extraction), but it must not omit retrieval or the RAG prompt.

The official example uses dense retrieval. Its index is prepared separately:

1. `retriever_retriever_init`
2. `retriever_retriever_embed`
3. `retriever_retriever_index`

An MCP client that exposes tools but not MCP prompts cannot reproduce the exact
upstream pipeline through this gateway. Enable prompt support in that client or
use an UltraRAG YAML pipeline runner.

### Corpus and retrieval preparation

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
The default tested local retrieval profile is CPU BM25. Dense embedding and
generation backends may require optional dependencies, network credentials, a
model service, or GPU resources; follow the upstream schemas and configured
environment.

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
- The gateway does not add project scoping, read-only search, provenance
  enrichment, or simplified knowledge-base workflows.
