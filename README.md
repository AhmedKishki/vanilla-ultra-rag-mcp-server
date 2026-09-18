# vanilla-ultra-rag-mcp-server

Use UltraRAG's existing MCP tools and prompts through one local stdio MCP
server.

This gateway preserves the pinned upstream interface. It combines UltraRAG's
independent MCP components behind one endpoint, adds deterministic namespace
prefixes to avoid name collisions, and keeps component processes alive so
initialization state survives between calls. It does not add a new retrieval
algorithm or change upstream tool behavior.

## Built on UltraRAG

This project directly exposes
[`OpenBMB/UltraRAG`](https://github.com/OpenBMB/UltraRAG), pinned to version
`0.3.0.2` at commit
[`3a709a2`](https://github.com/OpenBMB/UltraRAG/tree/3a709a2aea3fbe46acca59c422621c94b6e86857).
UltraRAG is a joint project of THUNLP, NEUIR, OpenBMB, AI9stars, and its
contributors, and is licensed under Apache-2.0.

This is an independent compatibility project and is not an official UltraRAG
release. See [`NOTICE`](NOTICE) for complete attribution and citation details.

## What the server offers

- one stdio MCP server named `vanilla-ultra-rag-mcp`;
- 78 namespaced UltraRAG tools and 26 namespaced prompts;
- upstream corpus, retrieval, reranking, prompt, generation, routing, memory,
  benchmark, and evaluation components;
- persistent component state for the duration of an MCP session;
- FAISS, Qdrant, Milvus, BM25, and web-search capabilities exposed wherever the
  pinned UltraRAG release provides them;
- a managed, integrity-checked UltraRAG runtime with no Git clone required;
- a CPU-tested BM25 workflow; and
- an optional launcher for the existing UltraRAG web interface.

Names follow `<component>_<upstream-name>`. Examples include
`corpus_chunk_documents`, `retriever_retriever_search`, and
`generation_generate`.

## How it works

```text
AI agent / MCP client
          │ stdio
          ▼
vanilla-ultra-rag-mcp
          │
          ├─ persistent corpus MCP process
          ├─ persistent retriever MCP process
          ├─ persistent prompt MCP process
          ├─ persistent generation MCP process
          └─ other pinned UltraRAG MCP processes
                         │
                         ▼
             verified UltraRAG snapshot
```

The first launch downloads the official pinned source archive, verifies the
archive and extracted file tree, and caches it in the operating-system user
cache. Every later launch validates the snapshot before starting UltraRAG's
component servers.

The connected agent is the orchestrator. It calls initialization, retrieval,
prompt, and generation components in order and passes each stage's output to
the next stage. There is intentionally no additional one-call pipeline tool.

## Requirements

- Python 3.11 or 3.12
- [`uv`](https://docs.astral.sh/uv/getting-started/installation/)
- Linux for the currently tested setup
- Internet access during installation and first runtime download

Individual UltraRAG tools may require extra model files, credentials, services,
or GPU resources. The CPU BM25 path does not require a GPU.

## Install

```bash
git clone https://github.com/AhmedKishki/vanilla-ultra-rag-mcp-server.git
cd vanilla-ultra-rag-mcp-server
uv sync --frozen
```

Install and validate the managed runtime in advance:

```bash
uv run vanilla-ultra-rag-runtime
uv run vanilla-ultra-rag-runtime --offline
```

The second command proves that the cached runtime can be validated without a
network connection.

## Configure your MCP client

Create a workspace for runtime logs and generated state, then replace both
placeholder paths with absolute paths:

```json
{
  "mcpServers": {
    "vanilla-ultra-rag-mcp": {
      "command": "/ABSOLUTE/PATH/TO/vanilla-ultra-rag-mcp-server/.venv/bin/vanilla-ultra-rag-mcp",
      "args": [
        "--workspace-root",
        "/ABSOLUTE/PATH/TO/your-project/.ultrarag/runtime"
      ],
      "env": {},
      "disabled": false,
      "autoApprove": [],
      "timeout": 1800
    }
  }
}
```

A copyable configuration is provided in
[`mcp_settings.example.json`](mcp_settings.example.json). For Cline, place the
entry under `mcpServers`, save the configuration, and reload VS Code.

Keep `autoApprove` empty initially. The upstream surface contains tools that
write files, download models, call network services, or start heavyweight
processes.

The executable is a stdio server. Running it directly shows no interactive
prompt because it waits for an MCP client.

By default the gateway starts the complete upstream surface. Integrators that
need only particular UltraRAG components can repeat `--namespace`; for example,
`--namespace corpus --namespace retriever` exposes only those two namespaced
components and avoids starting unrelated child servers.

## Use it

Ask the connected agent to perform a specific UltraRAG workflow. For example:

> Use UltraRAG to initialize the configured retriever, retrieve passages for my
> question, render the `prompt_qa_rag_boxed` MCP prompt with those passages, and
> generate a grounded answer. Show the retrieved passages and the answer.

The official Vanilla RAG experiment uses these namespaced stages:

| Order | MCP call | Result |
|---:|---|---|
| 1 | tool `benchmark_get_data` | questions and ground truth |
| 2 | tool `retriever_retriever_init` | initialized retriever |
| 3 | tool `retriever_retriever_search` | retrieved passages |
| 4 | tool `generation_generation_init` | initialized generator |
| 5 | prompt `prompt_qa_rag_boxed` | rendered prompt messages |
| 6 | tool `generation_generate` | generated answers |
| 7 | tool `custom_output_extract_from_boxed` | extracted predictions |
| 8 | tool `evaluation_evaluate` | evaluation result |

For an interactive question, the agent can provide the question directly and
omit benchmark loading and evaluation. Retrieval, prompt construction, and
generation remain the essential RAG stages.

`prompt_qa_rag_boxed` is an MCP prompt, not a tool. The MCP client must support
prompts and pass its rendered message text to `generation_generate`.

### Prepare retrieval

Dense index creation:

1. `retriever_retriever_init`
2. `retriever_retriever_embed`
3. `retriever_retriever_index`
4. `retriever_retriever_search`

CPU BM25 index creation:

1. `corpus_build_text_corpus`
2. `corpus_chunk_documents`
3. `retriever_retriever_init` with `backend="bm25"`
4. `retriever_bm25_index`
5. `retriever_retriever_init` again to load the saved index
6. `retriever_bm25_search`

Always follow the schemas advertised by the MCP server. Initialize generation
and reranking components before using their dependent tools.

## Expected retrieval result

UltraRAG's BM25 search returns ranked passage strings grouped by query. A
representative MCP result is:

```json
{
  "ret_psg": [
    [
      "The highest-ranking passage for the first query...",
      "The second-highest-ranking passage..."
    ]
  ]
}
```

Dense retrieval returns the same passage-oriented shape. Exact content depends
on the corpus, index, model, and requested `top_k`.

Direct searches return their results to the MCP client; they do not
automatically create a search-results file. Any corpus, chunk, embedding, index,
evaluation, or memory files are written to the paths supplied to the upstream
tools.

## Verify document ingestion from the terminal

The repository includes a CPU smoke test for PDF and EPUB collections. The
verifier filters its own input to those two formats, then exercises real corpus
building, chunking, BM25 indexing, reload, and search through stdio MCP:

```bash
uv run python scripts/verify_corpus.py \
  /absolute/path/to/project/sources \
  --workspace /absolute/path/to/project/.ultrarag/verification-001 \
  --query "your search terms"
```

Use a new or empty workspace. Expected terminal output has this form:

```text
[1/5] Found 12 PDF/EPUB source files
[2/5] Building the PDF/EPUB-only vanilla text corpus
[3/5] Chunking the extracted corpus
[4/5] Building and reloading the vanilla BM25 index
[5/5] Searching BM25 for: 'your search terms'
PASS: 12 documents -> 146 chunks -> 5 passages
Report: /absolute/path/to/project/.ultrarag/verification-001/verification-report.json
```

The workspace contains inspectable corpus JSONL, chunk JSONL, the BM25 index,
logs, and `verification-report.json`. A passing report verifies mechanical
coverage and retrieval, not extraction fidelity or ranking quality.

The verifier's PDF/EPUB filter is a test convenience. The MCP gateway itself
preserves the file-format behavior of the pinned UltraRAG corpus tools.

## Workspace and storage

`--workspace-root` sets the working directory for component processes and keeps
ordinary logs and UI storage outside the verified runtime snapshot. Use a
different workspace for each project.

This is organizational separation, not a security boundary. Upstream tools can
accept caller-selected input and output paths, so confirm every path before a
write operation.

The managed UltraRAG snapshot is cached separately as a read-only runtime
dependency. It does not contain your corpus or indexes.

## Optional UltraRAG interface

Launch the pinned upstream web interface with:

```bash
uv run vanilla-ultra-rag-ui \
  --workspace-root /absolute/path/to/your-project/.ultrarag/runtime \
  --host 127.0.0.1 \
  --port 5050
```

Open `http://127.0.0.1:5050`. The interface starts its own pipeline processes;
it is not a frontend for an already-running stdio session.

## Current limitations

- The server intentionally exposes low-level upstream tools rather than a
  simplified ingestion or query API.
- It does not enforce a project root or a read-only policy.
- It does not add source metadata, metadata filters, or page-level locators.
- Optional dense, generation, reranking, web, and GPU paths may require
  additional services, credentials, downloads, or hardware.
- Only the CPU BM25 path and pinned interface contract are covered by the
  default end-to-end tests.
- Production answer generation requires configuring one of UltraRAG's existing
  generation backends.
