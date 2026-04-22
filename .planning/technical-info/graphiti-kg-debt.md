# Graphiti KG – Technical Debt

## Backfill / Migration Debt
- No backfill job exists for records ingested before `graphiti_episodes` mapping was introduced. Those episodes cannot be targeted for per-record delete and may need reset/cleanup scripts.

## Operational Debt
- `/data/{id}` delete currently deletes Graphiti episodes sequentially. This is correct but can be slow for records with many chunks.
- No retry/backoff policy exists for transient Neo4j/Graphiti delete failures.

## Testing Debt
- No automated integration test currently asserts that deleting a data record removes mapped Neo4j episodes and keeps SQL state consistent.
