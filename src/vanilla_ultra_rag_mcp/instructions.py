SERVER_INSTRUCTIONS = """\
This server exposes the existing UltraRAG MCP components without changing their
behavior. Component names are prefixed with their namespace, for example
corpus_build_text_corpus and retriever_retriever_search.
Namespaces: benchmark, corpus, custom, evaluation, generation, memory, prompt,
reranker, retriever, router, and sayhello.

Use the exact input schemas supplied with each tool. Important call order:
- Corpus: build a corpus before chunking it.
- Dense retrieval: retriever_init, then retriever_embed and retriever_index when
  building; after an existing index is available, retriever_init then search.
- BM25: retriever_init with backend='bm25', then bm25_index when building. In
  UltraRAG 0.3.0.2, initialize once more to load the newly saved index before
  bm25_search.
- Reranking and generation: call the corresponding *_init tool before use.

The inherited build tool generates UltraRAG server metadata; it is not document
ingestion or retrieval indexing. Tools that build, embed, index, evaluate, save
memory, or initialize services may write files or consume substantial resources.
Web/API tools may use the network and credentials. GPU/vLLM tools are not part
of the initial CPU-tested path. Confirm explicit paths and overwrite intent
before write operations, and keep runtime paths under the configured workspace.

Direct retriever calls return passages to the MCP client and do not create a
separate search-results file. This vanilla gateway does not add project-root
enforcement, metadata filters, citation locators, a read-only policy, or any
other extension behavior.
"""
