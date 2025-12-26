# 🚦 Current Session State

**Status:** IN_PROGRESS  
**Current Feature:** Planning baseline for context retrieval + Graphiti KG

## ⏳ Context
Documented system context, project manifest, Graphiti KG POC spec, tenancy/auth scope, document/thread ingestion, vector store, and query/retrieval behaviors to align on scope, latency posture, and future Graphiti pivot.

## ✅ Recently Completed
- Added system context (tenancy, Graphiti pivot, low-latency expectation, external auth ownership).
- Added project manifest (vision, audience, scope/out-of-scope).
- Added technical spec for Graphiti KG POC (scoping, data flow, performance posture).
- Added tenancy/auth spec (scope resolution, RLS, placeholder roles).
- Added document/thread ingestion spec (chunking, embedding, vector upsert, KG extraction, summaries).
- Added query/retrieval spec (chunk search pipeline, KG search option, scoping).
- Added vector store spec (pgvector/Milvus behavior and scoping).
- Added Graphiti capabilities summary (what is built-in vs what remains our responsibility).
- Added initial Graphiti scaffolding (client bootstrap, scoping helper, ingestion/search adapters).
- Updated Graphiti ingestion adapter to support custom entity/edge types and edge_type_map inputs per new Graphiti docs.
- Reset codebase (new branch) to a minimal FastAPI app with health endpoint and startup DB init.
- Recreated minimal Postgres-backed data/chunk models and repositories with cascade delete.
- Wired config settings to load .env and default to Postgres async URL; installed python-dotenv so the import path is now satisfied.
- Recreated .codex/AGENTS.md persona after cleanup.
- Verified Postgres connectivity from the minimal service to ensure init_db succeeds.
- Added `scripts/reset_storage.py` maintenance script to drop/recreate SQL tables and wipe Graphiti data when needed.
- Normalized Slack thread ingestion (canonical JSON body, earliest Slack timestamp as Graphiti reference_time, richer chunk headers).
- Added per-thread anchor node + `mentioned_in_thread` edges in Graphiti to cluster entities by thread within the tenant/user group_id.
- Updated thread chunking to pack whole messages (no mid-message splits), emit per-chunk Graphiti episodes using the chunk’s first timestamp as reference_time, and link extracted entities from each chunk to the thread anchor.
- Switched thread chunking to LangChain's RecursiveJsonSplitter with message-atomic JSON chunks (messages serialized to strings), preserving message boundaries while recording per-chunk first_ts.
- Removed thread titles from the API and Graphiti payload; thread records now use derived internal titles only.
- Fixed thread anchor edge creation by setting required Graphiti `created_at` on `EntityEdge`.
- Thread ingestion responses now surface aggregated Graphiti entities/edges and invalidated edges.
- Made OpenAI API key configurable via settings and propagate it to Graphiti client for LLM-backed ingestion.

## 🚧 Current Hurdles / WIP
- Need details from external auth service: exact fields for tenant/product/user/roles and delivery mechanism (headers/token claims).
- Need confirmation on additional context sources beyond Slack threads (files, other systems).
- Need concrete latency/SLO targets and any future compliance/retention requirements once provided.
- Need to add ingest/query endpoints on the new minimal stack and wire Graphiti usage by default (no flag).

## ⏭️ IMMEDIATE NEXT STEPS
1. Capture auth payload contract (fields, source, headers vs tokens) and update system-context + technical spec.
2. List and prioritize additional context sources (if any) and update manifest/spec accordingly.
3. Record target latency/SLO numbers and any compliance/retention rules when available.
4. Add endpoints to create/list/delete data records and their chunks using the new repositories; integrate Graphiti ingestion by default (no feature flag).
