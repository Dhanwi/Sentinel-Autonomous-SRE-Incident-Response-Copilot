## Issue #2 — Ingestion Pipeline & Vector Store

### Chunk size: 1000 characters, overlap: 200 characters
Runbooks are structured around discrete sections (Symptoms, Diagnosis, Root
Cause, Resolution, Prevention), each typically running 150-400 words
(~900-1800 characters) in this dataset. A chunk_size of 1000 keeps most
individual sections intact as a single chunk without being so large that
retrieval becomes imprecise — a 3000-character chunk would often contain
multiple unrelated sections, diluting the embedding's relevance signal for
any single query.

The 200-character overlap (20% of chunk_size) exists specifically to prevent
the case where a section boundary sits mid-chunk: without overlap, a
Diagnosis step that spans a chunk boundary would have its second half
orphaned into the next chunk with no context connecting it back to "this is
still about diagnosis." 20% overlap is a standard starting ratio that
balances this against not duplicating so much content that retrieval returns
near-identical chunks for the same query.

Combined with the markdown-aware separator list
(`["\n## ", "\n### ", "\n\n", "\n", " ", ""]`), the splitter *prefers*
breaking at a section header even before it needs to respect the 1000-char
limit — so in practice most chunks correspond to exactly one runbook section,
and the character limits mostly act as a safety net for the rare
oversized section rather than the primary determinant of where splits happen.

### Embedding model: local `sentence-transformers/all-MiniLM-L6-v2` instead of OpenAIEmbeddings
The project's LLM provider is Groq (via `langchain-groq`), which does not
offer an embeddings endpoint — Groq is inference-only. Rather than adding an
unrelated OpenAI dependency (and API key) purely for embeddings, we use a
local `sentence-transformers` model via `langchain-huggingface`. This runs
fully offline after the first download, costs nothing per-query, and removes
an external network dependency from both local dev and CI. The tradeoff is
slightly lower retrieval quality than a top-tier hosted embedding model —
acceptable for a documentation corpus of this size and domain.

### `TextLoader` instead of `UnstructuredMarkdownLoader`
`UnstructuredMarkdownLoader` parses markdown into structured elements and
pulls in a heavy dependency chain (the `unstructured` library and its
system-level dependencies). Given the markdown-aware separators already
handle section boundaries well, `TextLoader` + `RecursiveCharacterTextSplitter`
achieves comparable chunk quality for this dataset with a much lighter
footprint — worth revisiting only if runbooks start including tables or
complex nested structures that plain-text splitting handles poorly.