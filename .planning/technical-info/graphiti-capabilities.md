# Graphiti Capabilities (What We Get Out-of-the-Box)

Source: `.planning/graphiti_reference.md` (OSS Graphiti on Neo4j, Python-friendly).

## Provided by Graphiti
- **Ingestion (LLM-backed):** `add_episode` (text/message/json) runs entity/fact extraction, provenance capture, temporal resolution (valid/invalid), and entity merge/dedup.
- **Direct triplet ingestion:** `add_triplet` for structured `(subject, predicate, object)` without LLM extraction.
- **Namespaces:** `group_id` for isolation (use tenant+product); applied across ingestion and search.
- **Temporal model:** validity vs ingestion time; supersession/expiry (`expired_at`) on conflicting facts; historical queries supported by temporal fields.
- **Embeddings + indexes:** vector storage in Neo4j with KNN indexes; full-text/BM25 indexes; combined hybrid search.
- **Hybrid search APIs:** `search(...)` and `_search(SearchConfig)` with presets (edge/node hybrid, graph-distance rerank, cross-encoder options); focal-node search supported.
- **Communities (optional):** clustering and summaries for higher-level retrieval.
- **Bootstrap helpers:** index/constraint builders for Neo4j.
- **MCP/server option:** exposes ingestion/search as tools over HTTP if we choose a service boundary.

## What we should NOT reimplement
- Fact supersession/temporal invalidation logic (use Graphiti’s built-in expired_at/valid_at handling).
- Entity resolution/dedup inside the KG (Graphiti merges entities when configured).
- Vector/full-text indexing and hybrid retrieval/reranking within the KG.
- KG-specific schema plumbing in Postgres (triplets/statements/events) once Graphiti is primary.

## What remains our responsibility
- **Tenancy/product mapping:** derive and pass `group_id` from tenant_id + product_id (and handle tenant-only mode if needed).
- **Provenance mapping:** include source system (Slack/document), user_id, reference_time, and any doc/chunk linkage in episode metadata.
- **Ingress orchestration:** chunk Slack threads/documents and decide when to call Graphiti vs chunk vector store (chunk vectors stay for passage retrieval).
- **Feature flags:** dual-write/read during POC; keep Postgres KG as fallback until cutover.
- **Auth/scope enforcement:** enforce scope before calling Graphiti; Graphiti isolation depends on correct `group_id`.
- **Latency posture:** avoid LLM-in-hot-path for query; rely on Graphiti search; control ingestion concurrency.
- **Observability:** configure logging/metrics/tracing around Graphiti client calls; health checks for Neo4j/Graphiti availability.
