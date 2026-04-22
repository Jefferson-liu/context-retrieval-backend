# Spec-Driven Change Scoping Technical Debt

## Current Gaps
- No canonical template yet for a scoped-change plan artifact in this repo.
- No scoring rubric yet for confidence in scoped boundaries.
- No historical benchmark showing planning quality vs. implementation rework.

## Risks
- Over-scoping due to noisy graph/reference expansion.
- Under-scoping when specs omit implicit domain constraints.
- Drift between product terminology and codebase terminology.

## Deferred Work
- Add a reusable plan schema (JSON/Markdown hybrid) for machine + human consumption.
- Define confidence scoring based on evidence density and dependency depth.
- Add a post-implementation feedback loop to measure scoping accuracy.
- Decide whether to keep planning as manual workflow or introduce partial automation.

## Missing Tests / Validation
- No repeatable evaluation set of specs to validate planning consistency.
- No acceptance test for traceability completeness in scoped plans.
