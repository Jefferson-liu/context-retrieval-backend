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

## 🚧 Current Hurdles / WIP
- Need details from external auth service: exact fields for tenant/product/user/roles and delivery mechanism (headers/token claims).
- Need confirmation on additional context sources beyond Slack threads (files, other systems).
- Need concrete latency/SLO targets and any future compliance/retention requirements once provided.

## ⏭️ IMMEDIATE NEXT STEPS
1. Capture auth payload contract (fields, source, headers vs tokens) and update system-context + technical spec.
2. List and prioritize additional context sources (if any) and update manifest/spec accordingly.
3. Record target latency/SLO numbers and any compliance/retention rules when available.
