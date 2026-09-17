# vanilla-ultra-rag-mcp-server

Run UltraRAG's existing Vanilla RAG components through one stdio MCP server.

## Purpose

This gateway exposes the MCP tools and prompts already provided by UltraRAG. It
does not modify UltraRAG or add new retrieval behavior. The current release is
pinned to UltraRAG `0.3.0.2` at commit
`3a709a2aea3fbe46acca59c422621c94b6e86857`.

The baseline is UltraRAG's documented
[`vanilla_rag.yaml` workflow](https://ultrarag.openbmb.cn/pages/en/pipeline/rag):
load questions, retrieve passages, construct a RAG prompt, generate an answer,
extract the answer, and optionally evaluate it. An AI agent connected through
MCP takes the role that UltraRAG's YAML pipeline runner normally performs.

This repository is the compatibility foundation. Research-specific source
policy, metadata, provenance, citation locators, and project enforcement belong
in `research-ultra-rag-mcp-server`, not in this vanilla gateway.

What you get:

- one MCP server named `vanilla-ultra-rag-mcp`;
- 78 namespaced UltraRAG tools and 26 prompts;
- persistent component state during an MCP session;
- built-in instructions describing the official Vanilla RAG stage order;
- all upstream retrieval, prompt, generation, extraction, and evaluation
  components used by that workflow;
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

## Official Vanilla RAG workflow

UltraRAG's pipeline is client-orchestrated. The gateway exposes the same stages
with namespaced MCP names; it does not add a replacement pipeline tool.

| Order | Upstream stage | Gateway component | Output used next |
|---:|---|---|---|
| 1 | `benchmark.get_data` | tool `benchmark_get_data` | `q_ls`, `gt_ls` |
| 2 | `retriever.retriever_init` | tool `retriever_retriever_init` | initialized retriever |
| 3 | `retriever.retriever_search` | tool `retriever_retriever_search` | `ret_psg` |
| 4 | `generation.generation_init` | tool `generation_generation_init` | initialized generator |
| 5 | `prompt.qa_rag_boxed` | MCP prompt `prompt_qa_rag_boxed` | rendered prompt messages |
| 6 | `generation.generate` | tool `generation_generate` | `ans_ls` |
| 7 | `custom.output_extract_from_boxed` | tool `custom_output_extract_from_boxed` | `pred_ls` |
| 8 | `evaluation.evaluate` | tool `evaluation_evaluate` | metrics file and result |

The prompt stage is an MCP **prompt**, not an MCP tool. The client must support
MCP prompts and pass the returned message text to `generation_generate`.

For an ordinary interactive question, the agent can supply `q_ls` directly and
omit benchmark loading and evaluation. Retrieval → RAG prompt → generation is
still required. For the documented experiment, use all eight stages.

Before running the dense-retrieval workflow for the first time, prepare its
index with `retriever_retriever_init`, `retriever_retriever_embed`, and
`retriever_retriever_index`. The CPU-oriented alternative uses UltraRAG's BM25
index and `retriever_bm25_search`, followed by the same prompt and generation
stages.

Example agent request:

> Use the official UltraRAG Vanilla RAG workflow. Retrieve passages for my
> question from the configured index, render `prompt_qa_rag_boxed` with those
> passages, and generate a grounded answer. Show both the retrieved passages
> and the answer. Do not answer from model memory without retrieval.

## What the knowledge base contains

UltraRAG does not produce one special database file. A usable knowledge base is
the combination of extracted text, chunks, and an index. A project can look
like this after the terminal verifier runs:

```text
research-project/
├── sources/                         # original PDF and EPUB files
└── .ultrarag/
    ├── runtime/
    │   ├── logs/                    # MCP child-process diagnostics
    │   └── ui-storage/              # storage reserved for the UltraRAG UI
    └── verification-run-001/
        ├── corpus/documents.jsonl   # one extracted-text record per source
        ├── chunks/chunks.jsonl      # smaller searchable passages
        ├── indexes/bm25/            # vocabulary and numerical BM25 index
        ├── runtime/                 # runtime logs/storage for this run
        ├── logs/                    # verifier diagnostics
        └── verification-report.json # counts, query, and returned passages
```

`documents.jsonl` contains the extracted text of each source. In vanilla
UltraRAG, the source ID and title are derived from its filename stem.

`chunks.jsonl` divides each document into passages. Every record contains a
numeric chunk ID, its document ID, its title, and its text. It does not retain
the original file path or PDF page number.

`indexes/bm25/` contains search data such as the term vocabulary and sparse
score matrices. These files are not readable research notes and do not replace
the corpus or chunks. BM25 uses them to rank which chunks best match a query.

A search therefore does not reopen every PDF. It searches the index and returns
the highest-ranking chunk texts. In the complete Vanilla RAG flow, those texts
are inserted into `prompt_qa_rag_boxed` and sent to the configured generation
backend. Normal search results are returned through MCP and are not
automatically saved as separate files.

## Use it with documents

After the server appears in your MCP client, ask the agent to perform the
workflow explicitly. For example:

> Using vanilla-ultra-rag-mcp, ingest all supported documents under
> `/absolute/path/to/project/original-sources`, create corpus and chunk files under
> `/absolute/path/to/project/.ultrarag`, build a CPU BM25 index, retrieve passages
> for "your research question", render the upstream RAG prompt, and generate a
> grounded answer. Show the retrieved passages and their available source
> identifiers alongside the answer.

The input directory in that request must contain only PDF and EPUB source
documents. Do not point the MCP corpus tool at a mixed directory containing
Markdown notes, source maps, drafts, or generated research files.

The server supplies lifecycle instructions to compatible agents. The main BM25
sequence is:

1. `corpus_build_text_corpus`
2. `corpus_chunk_documents`
3. `retriever_retriever_init` with the BM25 backend
4. `retriever_bm25_index`
5. `retriever_retriever_init` again to load the saved index
6. `retriever_bm25_search`

This six-step list prepares and searches the CPU index. To complete RAG, follow
the search with `prompt_qa_rag_boxed` and `generation_generate` as described
above. Direct search results are not automatically written to a separate file.

The upstream vanilla corpus tool also accepts Markdown and several other file
types. The gateway exposes that tool unchanged, so PDF/EPUB-only ingestion is
currently an agent instruction rather than a hard security boundary. The
terminal verifier below enforces the intended research profile by presenting
only PDF and EPUB files to UltraRAG, even when its input directory also contains
Markdown files.

### Project separation

Use a different `--workspace-root` for each project. This keeps ordinary logs,
UI storage, indexes, corpora, and generated files project-owned.

This is organizational separation, not a security boundary: vanilla UltraRAG
tools still accept caller-supplied paths. Hard path enforcement belongs in a
separate, non-vanilla MCP server.

## Verify a document collection from the terminal

The included verifier selects only PDF and EPUB files, then performs real
ingestion, chunking, BM25 indexing, reload, and search through the stdio MCP
server:

```bash
uv run python scripts/verify_corpus.py \
  /absolute/path/to/project/sources \
  --workspace /absolute/path/to/project/.ultrarag/verification-001 \
  --query "your research question"
```

Use a new verification workspace for each run. The command creates inspectable
corpus JSONL, chunk JSONL, BM25 index, logs, and
`verification-report.json`. The report lists the selected source files and their
extensions, making it possible to confirm that no Markdown file was included. A
passing report confirms mechanical coverage and retrieval for that run; it does
not guarantee extraction fidelity, ranking quality, or citation accuracy.

Run the automated gateway tests with:

```bash
uv run pytest -q
```

The test suite locks the exact official Vanilla RAG tool/prompt surface and
executes a CPU BM25 variant end to end through retrieval, prompt rendering,
generation, boxed-answer extraction, and evaluation. Its generator is a local
deterministic OpenAI-compatible test endpoint, so this validates integration,
not real-model answer quality.

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
- direct MCP calls do not technically enforce PDF/EPUB-only ingestion;
- it does not preserve source paths, structured bibliographic metadata, or
  metadata filters;
- it does not add page-level citation locators;
- it does not combine BM25 and vector results into hybrid retrieval;
- it does not simplify or hide heavyweight, GPU, or network-backed tools; and
- it does not wrap UltraRAG's complete YAML pipeline runner as a new MCP tool.

The last point preserves the upstream architecture: the connected AI agent is
the MCP client orchestrator. Production generation still requires configuring
one of UltraRAG's existing generation backends.

See [AGENT_GUIDE.md](AGENT_GUIDE.md) for agent tool-use guidance and
[AGENTS.md](AGENTS.md) for the repository's engineering contract.
