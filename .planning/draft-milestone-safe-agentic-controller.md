# Draft: SAFE IRCoT Agentic Controller

## Goals
- Produce clause-based answers with guaranteed attribution.
- Coordinate IRCoT loops combining retrieval, reasoning, and verification.
- Persist rich telemetry for auditing and evaluation.

## Implementation Steps
1. **API Contract Update**
   - Define new response schema (Pydantic) with `clauses: List[ClauseResult]`, each containing `text`, `sources`, `confidence`, `status`.
   - Maintain backward-compatible fields (`response`) during transition via feature flag.
2. **Routing Layer**
   - Add lightweight classifier (rule-based initial) to choose FastPath vs ReasonPath.
   - Expose metrics counters to monitor path distribution.
3. **Controller Core**
   - Implement `AgenticQueryController` with phases:
     1. Plan clause using LLM prompt (context: query, accepted clauses, outstanding info).
     2. Invoke fusion retriever with clause-specific subquery.
     3. Run verification pipeline; accept clause when thresholds met else revise.
     4. Stop when planner signals done or max iterations reached.
   - Support deterministic fallback for zero-result cases (return "no evidence" clause).
4. **Verification Pipeline**
   - Stage 1: semantic similarity threshold on retrieved contexts.
   - Stage 2: cross-encoder reranker scoring top contexts.
   - Stage 3: entailment classifier to confirm each source supports the clause.
   - Aggregate composite score; attach to clause as confidence.
5. **Persistence Layer**
   - Create tables: `response_clauses`, `clause_sources`, `clause_verification_metrics`.
   - Update repositories to write/read clause data alongside existing response rows.
6. **LLM Prompt Assets**
   - Add prompts for clause planning, revision requests, and final answer assembly to `prompts/` directory.
7. **Feature Flag & Backward Compatibility**
   - Gate controller behind `ENABLE_SAFE_CONTROLLER` environment flag.
   - Provide transitional adapter converting clause list to legacy response text when flag disabled.
8. **Metrics & Logging**
   - Emit structured logs per clause (status, iterations, rejection reasons).
   - Add counters for verification failures, entailment mismatches, retrieval fallback usage.

## Testing Strategy
- Unit tests for planner (mock LLM) verifying iterations and replan behavior.
- Verification tests with labeled sample data (true/false clauses) ensuring acceptance logic works.
- End-to-end tests using deterministic embeddings/LLM stubs to validate clause outputs and persistence.
- Performance smoke test to capture latency impact under ReasonPath.

## Rollout Plan
- Stage deployment with feature flag off; run shadow logs comparing new controller vs legacy responses.
- Gradually enable for internal tenants once precision metrics acceptable.

## Open Questions
- Should we support streaming clause emission? (Defer to evaluation milestone.)
- What format should clause IDs take for UI diffing? (Tentative: UUID per clause.)
