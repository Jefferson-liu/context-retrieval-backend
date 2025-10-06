# Milestone: SAFE IRCoT Agentic Controller

## Objective
Deliver a clause-based answering engine that enforces SAFE-style attribution and iteratively retrieves evidence using IRCoT loops.

## Success Criteria
- `/api/query` returns structured payload containing ordered clauses, each with supporting sources and confidence scores.
- Agentic controller orchestrates planning → retrieval → verification cycles with bounded retries.
- Verification pipeline performs semantic similarity checks, reranking, and textual entailment gating before accepting clauses.
- Response data stored in new tables (clauses, clause_sources, verification_metrics) for auditability.

## Scope
- Implement routing layer to classify queries into FastPath vs ReasonPath.
- Build `AgenticQueryController` managing clause planning with configurable max iterations.
- Integrate fusion retriever outputs into controller along with clause planner prompts.
- Add verification stack: cross-encoder reranker, entailment model, composite scoring.
- Update persistence layer to store clauses, per-clause sources, and verification telemetry.
- Extend API schemas/tests to cover new response shape.

## Out of Scope
- UI changes beyond API contract definition.
- External tool integrations (e.g., calculators); focus on retrieval + verification.
- Long-running async jobs (controller executes within request context for now).

## Deliverables
1. Controller + planner modules with unit tests for clause planning and retry behavior.
2. Verification utilities with configurable thresholds and tests (positive/negative entailment cases).
3. Database migrations for clause-level storage and repository methods.
4. Updated schemas/responses plus integration tests covering SAFE acceptance criteria.

## Dependencies
- Completion of Change-Aware Ingestion & Dual Retrieval milestone.

## Risks & Mitigations
- **Risk**: LLM planner may be slow or unstable → cache prompts, implement deterministic fallback heuristics.
- **Risk**: Entailment model performance → evaluate open-source models (e.g., `facebook/bart-large-mnli`) and monitor metrics; provide configuration hook for future swap.
- **Risk**: Increased response latency → expose tracing, implement max iteration guard rails, and consider streaming API if needed.

## Verification Plan
- Unit tests for clause acceptance/rejection across verification thresholds.
- Integration tests using synthetic documents ensuring each clause maps back to citations.
- Regression tests for FastPath (simple queries) verifying quick path still works without IRCoT overhead.

## Follow-up Tasks
- Capture telemetry (attribution precision, latency) for Evaluation & Ops Hardening milestone.
- Explore UI updates to display clause-level answers with citations.
