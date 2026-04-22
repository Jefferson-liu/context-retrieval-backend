# Graphiti Knowledge Graph – Technical Spec (POC)

## Core Responsibility
Use Graphiti (Neo4j-backed) as the knowledge graph for ingesting, storing, and retrieving product-relevant facts extracted from external context (e.g., Slack threads), with strict tenant/product scoping and low-latency search.

## Architecture & Data Flow (target)
- Input: external context payloads (initially Slack threads) plus auth-scoped identifiers (tenant_id, product_id, user_id, role placeholder).
- Processing:
  - Ingestion pipeline extracts entities/facts (LLM-driven where applicable).
  - Graphiti client writes episodes/entities/edges scoped by `group_id` derived from tenant/product.
  - Temporal handling/invalidation managed by Graphiti’s supersession model.
- Output:
  - Search APIs (Graphiti hybrid search) return facts/edges with provenance and temporal fields for downstream answer generation.

## Key Components (planned)
- Graphiti client bootstrap (Neo4j URI/creds, index/constraint builder).
- Ingestion adapter mapping extracted items to Graphiti episodes/triples with `group_id` = tenant+product; supports optional custom entity/edge types and edge_type_map for structured extraction.
- Retrieval adapter for hybrid search (semantic + keyword) with low latency; no LLM in the hot path.
- Feature flag to enable Graphiti-backed KG while retaining legacy fallback until cutover.
- Settings-driven OpenAI key: `get_graphiti_client` now sources `OPENAI_API_KEY` from settings and sets it for Graphiti LLM-backed ingestion.

## Data Model & Scoping
- Namespace via `group_id`: combine tenant_id and product_id (e.g., `tenant:product`), with option to operate tenant-only if product-as-metadata mode is required.
- Store provenance: source system (Slack), reference time, and user_id for auditing/traceability (roles remain placeholders).
- Ontology: includes explicit `HasFeature` edge from `Product -> Feature` to model product feature membership (alongside existing `Feature -> Product` `Implements` links).

## Performance Targets (qualitative)
- Chatbot-grade latency: avoid blocking LLM calls on query paths; prefer precomputed embeddings and Graphiti hybrid search.
- Keep ingestion concurrency tuned to avoid impacting query latency (separate from request path where possible).

## Cross-Feature Dependencies
- Depends on upstream auth/context provider for tenant/product/user scope and roles (placeholders).
- Exposes results to the assistant/Slackbot query flow; must respect scope in all searches.

## Maintenance / Troubleshooting
- Use `python -m scripts.reset_storage` (with `--force` to skip confirmation) to drop/recreate the Postgres tables **and** invoke `graphiti_core.utils.maintenance.graph_data_operations.clear_data` followed by `Graphiti.build_indices_and_constraints()`. This wipes all tenants' KG data, so only run in local/testing environments.

## Known Gaps
- Targeted graph cleanup now exists for `/data/{id}` by persisting per-record episode UUID mappings and deleting them through `Graphiti.remove_episode(...)` before SQL delete.
- Remaining gap: existing historical records created before mapping persistence may still have orphaned episodes and require scoped/full reset cleanup.
