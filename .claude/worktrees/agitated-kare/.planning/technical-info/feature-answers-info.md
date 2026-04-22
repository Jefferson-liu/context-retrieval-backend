# Feature Answers – Technical Spec

## Status
Removed from runtime on 2026-02-08.

## Core Responsibility
This feature previously generated feature-centric answers by combining Graphiti search context with an Anthropic-backed LLM prompt.

## Removal Summary
- Removed endpoint: `POST /feature-answers`.
- Removed routing from `main.py`.
- Removed implementation files:
  - `routers/feature_answer_router.py`
  - `services/feature_answer_service.py`
  - `schemas/feature_answer.py`
  - `infrastructure/ai/anthropic_client.py`
  - `services/prompts/*`
- Removed direct dependencies no longer needed by this feature:
  - `anthropic`
  - `langchain-anthropic`

## Integration Impact
- Remaining ingestion/search/data APIs are unaffected because they do not import or depend on feature-answer modules.
- If feature answers are reintroduced, they should be rebuilt behind a clear interface and covered by endpoint/service tests before enabling in `main.py`.
