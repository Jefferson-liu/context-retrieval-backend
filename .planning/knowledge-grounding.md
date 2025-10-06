# SAFE + IRCoT Agentic Retrieval System (Conceptual Implementation Plan)

This document defines the conceptual architecture, flow, and design principles for implementing a **SAFE-style, IRCoT-grounded retrieval and attribution system**. It is **framework-agnostic** — it avoids specific libraries or SDKs, leaving implementation details to the coding agent with extended context.

---

## 1. Objective

Implement a retrieval-generation pipeline that:

* Answers queries as a **list of verified clauses**.
* Ensures **each clause is grounded** in specific, retrievable sources.
* Uses **iterative reasoning (IRCoT)** for complex, multi-hop queries.
* Enforces **in-generation sentence-level attribution (SAFE)** — no clause is emitted without verifiable evidence.
* Supports a corpus of **rapidly changing Markdown documents** with minimal recomputation.

---

## 2. System Overview

### 2.1 Data Flow

```
Document Ingest
  ├── Sentence Extraction + Hashing
  ├── Contextual Embedding (vector lane)
  ├── Lexical Index Update (lexical lane)
  └── Metadata Sync (Postgres or equivalent)

Query Handling
  ├── Query Classification (simple vs. complex)
  ├── Agentic Controller (SAFE + IRCoT loop)
  │     ├── Clause Planning
  │     ├── Retrieval (vector + lexical)
  │     ├── Attribution Verification
  │     └── Acceptance / Revision
  └── Output Assembly [{clause, sources[], confidence}]
```

### 2.2 Design Layers

| Layer                  | Responsibility                                                             |
| ---------------------- | -------------------------------------------------------------------------- |
| **Data Layer**         | Store sentences, hashes, embeddings, metadata, and lexical index entries.  |
| **Retrieval Layer**    | Dual-lane retrieval (vector + lexical). Deduplicate and rerank candidates. |
| **Verification Layer** | Attribute and verify factual grounding for each clause (SAFE).             |
| **Controller Layer**   | Manage reasoning and retrieval loop (IRCoT).                               |
| **Routing Layer**      | Classify queries and route to fast or reasoning paths.                     |

---

## 3. Ingestion Strategy (Change-Aware)

### 3.1 Sentence Hashing

* Split Markdown into sentences.
* Compute normalized hash for each (lowercased, trimmed whitespace).
* Compare hashes against previously stored hashes to detect changed or new sentences.

### 3.2 Storage Simplification (No Version History)

* Persist only the latest sentence state alongside its hash for deduplication.
* Do not retain historical revisions or version timestamps within the database.
* When a sentence/chunk is removed, downstream references (e.g., response sources) simply set `chunk_id` and `doc_id` to `NULL`.

### 3.3 Dual-Lane Indexing

**Lexical lane (real-time)**

* Index sentences and metadata for full-text lexical search (BM25 or equivalent).
* Commit small deltas frequently.

**Vector lane (asynchronous)**

* Queue changed sentences for embedding.
* Embed in micro-batches to amortize GPU cost.
* Upsert vectors incrementally; compact periodically.

---

## 4. Query-Time Architecture

### 4.1 Routing

Classify each query as:

* **FastPath (simple)** — direct factual lookups.
* **ReasonPath (complex)** — open-ended, analytical, or multi-hop questions.

Routing can be heuristic or model-based.

### 4.2 Agentic Controller (SAFE + IRCoT)

For each query:

1. Initialize reasoning state.
2. Repeatedly plan and verify clauses until the answer is complete.

Each iteration performs:

* **Plan**: model proposes one clause, predicts reference need (none/single/multi), emits a subquery.

* **Retrieve**: use both lanes — semantic (vector) + lexical (BM25/FTS) — dedupe and rerank.

* **Verify (Attribution)**: apply multi-stage checks:

  * semantic similarity
  * rerank relevance
  * textual entailment (does source entail the clause?)

* **Accept or Revise**:

  * Accept if enough verified supports exist.
  * Revise the clause or broaden subquery if not.
  * Abort after retries to prevent infinite loops.

* **Stop Condition**: planner signals completion or coverage criteria met.

### 4.3 Acceptance Criteria (SAFE)

A clause is accepted only if:

* Required number of references are found.
* All supporting sources entail the clause.
* No contradictions are detected.
* Key terms in the clause appear in the sources (coverage test).

Each clause returns `{clause, sources[], confidence}`.

---

## 5. Retrieval & Verification Logic

### 5.1 Retrieval Policies

* Always run **vector retrieval first**.
* If scores are weak or zero, fallback to **lexical retrieval**.
* Merge and deduplicate results by `(doc_id, sent_id)`.
* Apply cross-encoder or equivalent reranker for semantic ordering.

### 5.2 Verification Stages

1. **Semantic proximity** — check vector similarity.
2. **Relevance** — reranker or scoring model.
3. **Entailment** — textual entailment or NLI classifier.
4. **Composite scoring** — weighted mean of the above.
5. **Confidence metric** — average composite score of accepted supports.

---

## 6. Change Management & Consistency

* **Atomic snapshot**: treat all retrieval results as referencing the latest stored sentences only.
* **Citation policy**: record `(doc_id, sent_id)` for live sentences; set identifiers to `NULL` when the source no longer exists (chunk deleted).
* **Conflict policy**:

  * If multiple sources disagree, output multiple clauses or favor the most recently stored sentence.
  * Allow the agent to signal uncertainty explicitly.

---

## 7. Performance Design

| Parameter            | Target         | Rationale                   |
| -------------------- | -------------- | --------------------------- |
| ANN candidates       | 64             | balances recall and latency |
| Lexical candidates   | 64             | coverage for fresh content  |
| Rerank top           | 32             | precision vs. speed         |
| Verification top     | 2–3 supports   | ensures grounding           |
| Clause loop max      | 6              | IRCoT sweet spot            |
| Acceptance threshold | ~0.6 composite | tuned empirically           |

**Batching:** micro-batch embeddings, reranker pairs, and entailment checks.

**Queueing:** maintain a bounded queue of pending embeddings; lexical lane covers interim freshness.

---

## 8. Evaluation & Metrics

* **Attribution precision**: % clauses whose cited sentences entail them.
* **Contradiction rate**: should approach 0.
* **Coverage**: proportion of subtopics covered in complex queries.
* **Latency per query**: avg. clause cycles × retrieval time.
* **Embedding backlog age**: time between sentence update and embedding availability.

**Alert thresholds:**

* contradiction rate > 0 ⇒ investigate attribution.
* embedding backlog > target window ⇒ scale embedding jobs.

---

## 9. Rollout Plan

1. **Shadow mode:** run new agentic controller alongside existing query flow; log differences.
2. **FastPath first:** replace simple lookups with the new verifier (1 cycle).
3. **ReasonPath next:** enable IRCoT loop for complex queries; monitor performance.
4. **Tighten thresholds:** refine acceptance and confidence cutoffs.
5. **Enable adaptive routing:** dynamically switch between fast and reasoning paths.

---

## 10. Design Principles Recap

* **Precision over recall:** never emit unverified clauses.
* **Freshness via lexical lane:** BM25 or equivalent makes new text queryable instantly.
* **Semantic stability via vector lane:** embeddings update asynchronously.
* **Explainability:** every clause → sources → document spans.
* **Incremental cost:** only changed sentences are reprocessed.
* **Agentic grounding:** the model plans, retrieves, and verifies iteratively.

---

## 11. Key Concepts for Reference (Research Roots)

| Concept                  | Core Idea                                | Reference                                            |
| ------------------------ | ---------------------------------------- | ---------------------------------------------------- |
| **SAFE**                 | Sentence-level in-generation attribution | ensures no hallucinated clause is emitted.           |
| **IRCoT**                | Interleaving retrieval with reasoning    | improves multi-hop reasoning accuracy and grounding. |
| **ReAct**                | Reasoning + Acting loop                  | enables tool usage (search) during thought process.  |
| **Contextual Retrieval** | Context-enriched embeddings              | reduces retrieval misses on markdown-like corpora.   |
| **RAG**                  | External knowledge grounding             | provides freshness, provenance, and modularity.      |

---

### Implementation Outcome

When implemented, this system will:

* Produce verifiable, source-linked answers with explicit provenance.
* Automatically adapt between simple and complex query flows.
* Keep knowledge up to date without costly re-indexing.
* Maintain full transparency and auditability for every generated statement.

---

*End of conceptual specification.*

---

## Implementation Feasibility & Translation Plan (2025-10-04)

### Current Baseline Snapshot
- **Ingestion**: `DocumentProcessingService` already handles upload → chunk → embed → pgvector and maintains tenant/project scoping. LLM contextualization runs inline; git mirroring and Milvus support add complexity but are optional.
- **Retrieval**: `QueryService` embeds queries, performs vector search via the gateway (pgvector/Milvus), and synthesizes a single free-form answer using the same LLM provider.
- **Data Model**: Documents, chunks, embeddings, queries, responses, and sources exist; there is no sentence-level storage, lexical index, or SAFE-style clause table.
- **Infra Hooks**: Context scoping + RLS are in place; background job infrastructure is minimal (no task queue yet).

### Lean Alignment Decisions
1. **Keep** multi-tenant scoping, pgvector indexing, and async ingestion since they are core to SAFE/IRCoT requirements.
2. **Remove** non-essential extras for the lean baseline:
  - Milvus adapter/tests/scripts (retain config stubs but disable until we need multi-store support again).
  - Git-backed `DocumentFileService` commits (keep raw document persistence in Postgres only).
3. **Refactor** LLM usage so contextualization and answer generation are separated; the SAFE controller will own reasoning loops instead of `QueryService` directly calling the provider.

### Capability Gaps vs. SAFE + IRCoT Spec
| Capability | Status | Notes |
| --- | --- | --- |
| Sentence hashing + latest-state storage | Missing | Requires new `document_sentences` table with hashes; no historical versions retained. |
| Dual-lane retrieval (vector + lexical) | Partial | Vector exists; need lexical index (Postgres FTS or Tantivy) + fusion logic. |
| Retrieval reranking + verification | Missing | Need reranker model integration and textual entailment checks. |
| SAFE clause generation | Missing | Requires new controller that outputs `{clause, sources[], confidence}` and persistence for clauses/citations. |
| Query routing (FastPath vs ReasonPath) | Missing | Need classifier or heuristics + request metadata. |
| Background embedding queue | Missing | Ingestion currently inline; need task dispatch for changed sentences. |

### Technical Feasibility Summary
- **Database**: PostgreSQL can support additional tables (sentence hashes, lexical index via `tsvector`). No migration blockers.
- **Model Hosting**: SentenceTransformer already bundled; adding reranker/NLI models is feasible using the same executor pattern. Need caching to avoid repeated downloads.
- **Service Layer**: Existing repository/service architecture allows adding new repositories/services without breaking API contracts.
- **Testing**: Pytest suite is active; we will extend with table-level and controller-level tests. Removing Milvus/git dependencies simplifies CI.
- **Risks**: Largest unknown is orchestrating IRCoT loop efficiently without a task runner; solution is to build deterministic loop with capped retries inside request lifecycle for now.
- **Versioning Approach**: No dedicated version tracking beyond optional git mirroring; database rows represent only the latest sentence state.

### Milestone Breakdown
1. **Milestone – Lean Core Refactor**
  - Remove Milvus/Git integrations, dead code paths, and dependent tests.
  - Tighten `VectorStoreGateway` to pgvector-only while keeping extension point documented.
  - Simplify DocumentProcessingService to operate purely in-database.
2. **Milestone – Change-Aware Ingestion & Dual Retrieval**
  - Introduce sentence hashing tables + migrations, ingestion diffing, and lexical indexing.
  - Add background-friendly embedding queue interfaces (in-process stub acceptable initially).
  - Implement retrieval fusion (vector + lexical) with dedupe and reranking scaffolding.
3. **Milestone – SAFE IRCoT Query Engine**
  - Build agentic controller for clause planning/retrieval loops.
  - Add verification pipeline (semantic similarity thresholds, entailment checks) and clause persistence.
  - Update API contract to return clause list with sources/confidence; adjust tests accordingly.

Each milestone will ship with a companion draft describing schema diffs, API contracts, test plans, and rollout steps. See newly added milestone files for details.
