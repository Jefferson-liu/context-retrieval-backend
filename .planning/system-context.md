# 🏛️ System Context & Architecture

## Global Design Decisions
- Service scope: context retrieval backend that ingests external context (e.g., Slack threads) to surface product-relevant information for an assistant.
- Data ownership: user/product identity and roles live in an external auth/service; we store only the minimum needed identifiers for scoping.
- Tenancy: enforce per-tenant + per-product scoping by default; keep the option open to treat product as metadata under a tenant if required later.
- Knowledge graph: pivoting to Graphiti (Neo4j-backed) for KG storage, search, and temporal handling; legacy Postgres KG to be phased out.
- Security: no cross-tenant/product leakage; all queries and writes must filter by tenant/product scope provided by upstream auth.
- Performance: optimize for low latency (chatbot/slackbot UX); keep query paths minimal and avoid long-tail LLM calls in the hot path.
- Roles: roles are defined by the external service; placeholders only until role/permission contracts are provided.
- Compliance: no explicit compliance constraints yet; add data retention/audit rules when provided.

## Project Constraints & Patterns
- Keep interfaces/flags that allow toggling between strict per-product scope and tenant-only scope (product as metadata).
- Favor feature flags for Graphiti adoption to preserve fallback paths.
- Provenance matters: track source system (e.g., Slack), tenant_id, product_id, user_id with each stored item.
