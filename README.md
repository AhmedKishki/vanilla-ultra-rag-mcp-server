# vanilla-ultra-rag-mcp-server

Use UltraRAG from an AI agent through one local stdio MCP server.

This gateway exposes the MCP tools and prompts already provided by UltraRAG. It
does not modify UltraRAG or add new retrieval behavior. The current release is
pinned to UltraRAG `0.3.0.2` at commit
`3a709a2aea3fbe46acca59c422621c94b6e86857`.

What you get:

- one MCP server named `vanilla-ultra-rag-mcp`;
- 78 namespaced UltraRAG tools and 26 prompts;
- persistent component state during an MCP session;
- built-in instructions that explain tool ordering to the agent;
- a CPU-tested path for document ingestion, chunking, BM25 indexing, and search;
- project-owned workspaces; and
- no separate UltraRAG clone.

## Requirements

- Python 3.11 or 3.12
- [`uv`](https://docs.astral.sh/uv/getting-started/installation/)
- Internet access during the first installation and first server launch

The commands below use POSIX paths and have been tested on Linux.

## Install

```bash
git clone https://github.com/AhmedKishki/vanilla-ultra-rag-mcp-server.git
cd vanilla-ultra-rag-mcp-server
uv sync --frozen
```

The first launch downloads a pinned UltraRAG source snapshot to the operating
system's user cache. Both the downloaded archive and extracted files are
verified before use.

You can install the runtime in advance and then confirm it works offline:

```bash
uv run vanilla-ultra-rag-runtime
uv run vanilla-ultra-rag-runtime --offline
```

## Add it to an MCP client

Create a separate workspace for each research project. Replace both placeholder
paths below with absolute paths:

```json
{
  "mcpServers": {
    "vanilla-ultra-rag-mcp": {
      "command": "/ABSOLUTE/PATH/TO/vanilla-ultra-rag-mcp-server/.venv/bin/vanilla-ultra-rag-mcp",
      "args": [
        "--workspace-root",
        "/ABSOLUTE/PATH/TO/YOUR/PROJECT/.ultrarag/runtime"
      ],
      "env": {},
      "disabled": false,
      "autoApprove": [],
      "timeout": 1800
    }
  }
}
```

A copyable template is provided in
[`mcp_settings.example.json`](mcp_settings.example.json).

For Cline, open **MCP Servers → Configure → Configure MCP Servers**, paste the
entry under `mcpServers`, save, and reload the VS Code window. Other local MCP
clients use the same `command` and `args` values, although their configuration
filename and optional fields may differ.

Keep `autoApprove` empty initially. The vanilla UltraRAG surface includes tools
that write files, build indexes, contact network services, or load heavyweight
models.

Running `vanilla-ultra-rag-mcp` directly in a terminal produces no interactive
prompt; a stdio MCP server waits for JSON-RPC messages from an MCP client.

## Use it with documents

After the server appears in your MCP client, ask the agent to perform the
workflow explicitly. For example:

> Using vanilla-ultra-rag-mcp, ingest all supported documents under
> `/absolute/path/to/project/sources`, create corpus and chunk files under
> `/absolute/path/to/project/.ultrarag`, build a CPU BM25 index, and search it
> for "your research question". Show the retrieved passages and their available
> source identifiers.

The server supplies lifecycle instructions to compatible agents. The main BM25
sequence is:

1. `corpus_build_text_corpus`
2. `corpus_chunk_documents`
3. `retriever_retriever_init` with the BM25 backend
4. `retriever_bm25_index`
5. `retriever_retriever_init` again to load the saved index
6. `retriever_bm25_search`

Direct search results are returned to the agent. They are not automatically
written to a separate results file.

The upstream corpus tool accepts TXT, Markdown, PDF, XPS/OXPS, EPUB, MOBI, FB2,
and DOCX files. Legacy DOC and WPS conversion requires LibreOffice.

### Project separation

Use a different `--workspace-root` for each project. This keeps ordinary logs,
UI storage, indexes, corpora, and generated files project-owned.

This is organizational separation, not a security boundary: vanilla UltraRAG
tools still accept caller-supplied paths. Hard path enforcement belongs in a
separate, non-vanilla MCP server.

## Verify a document collection from the terminal

The included verifier performs real ingestion, chunking, BM25 indexing, reload,
and search through the stdio MCP server:

```bash
uv run python scripts/verify_corpus.py \
  /absolute/path/to/project/sources \
  --workspace /absolute/path/to/project/.ultrarag/verification-001 \
  --query "your research question"
```

Use a new verification workspace for each run. The command creates inspectable
corpus JSONL, chunk JSONL, BM25 index, logs, and
`verification-report.json`. A passing report confirms mechanical coverage and
retrieval for that run; it does not guarantee extraction fidelity, ranking
quality, or citation accuracy.

Run the automated gateway tests with:

```bash
uv run pytest -q
```

## Optional UltraRAG UI

The pinned upstream UI can be launched without an UltraRAG clone:

```bash
uv run vanilla-ultra-rag-ui \
  --workspace-root /absolute/path/to/project/.ultrarag/runtime \
  --host 127.0.0.1 \
  --port 5050
```

Open `http://127.0.0.1:5050`.

The UI launches its own UltraRAG pipeline processes; it is not a frontend for
the already-running aggregate MCP gateway. Its knowledge-base indexing screens
currently target Milvus or Qdrant rather than the verifier's local BM25 index.

## Vanilla limitations

This server intentionally preserves the upstream UltraRAG interface:

- it does not enforce a project root;
- it does not add metadata filters or automatic project selection;
- it does not add page-level citation locators;
- it does not simplify or hide heavyweight, GPU, or network-backed tools; and
- it does not wrap UltraRAG's complete YAML pipeline runner as a new MCP tool.

See [AGENT_GUIDE.md](AGENT_GUIDE.md) for agent tool-use guidance and
[AGENTS.md](AGENTS.md) for the repository's engineering contract.
