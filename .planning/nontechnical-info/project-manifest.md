# Project Manifest

## Vision
Deliver a context retrieval backend that ingests external sources (starting with Slack threads) and extracts product-relevant knowledge to aid an assistant for product management work.

## Audience
- Product managers and adjacent stakeholders using a Slack-based assistant.
- Multi-tenant environment with per-product scoping; users must never see data from other tenants/products.

## Problems We Solve
- Centralize scattered product discussions (Slack threads) into searchable, structured context.
- Preserve provenance so answers can cite where facts came from.
- Provide low-latency responses suitable for a chat experience.

## Out of Scope (current)
- Owning user/product identity or role definitions (handled by external auth/service).
- Compliance/retention policies (not yet provided).
