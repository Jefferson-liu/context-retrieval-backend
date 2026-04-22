# Graphiti (Neo4j) – General-Purpose, Detailed Reference for Codex Agents

> Scope: **Graphiti OSS (graphiti-core) using Neo4j as the graph store.**  
> Goal: give an implementation agent practical, code-adjacent knowledge of Graphiti’s concepts, APIs, and operational knobs.

---

## 0) Mental model

Graphiti builds and maintains a **temporal knowledge graph** from “episodes” (pieces of information).  
Each episode can introduce or update:

- **Entities** (nodes)
- **Facts / relationships** (edges between entities)
- **Provenance** (which episode/source introduced the knowledge)
- **Time** (when the fact is true in the world vs when it was ingested)

Graphiti is designed to support:
- **Incremental updates** (add new episodes over time; no full rebuild)
- **Hybrid retrieval** (semantic + full-text + optional graph proximity)
- **History-aware memory** (old facts aren’t deleted; they become *superseded/expired*)

---

## 1) Core concepts & objects

### 1.1 Episode
An **Episode** is the unit of ingestion.

Episodes typically include:
- `name`: identifier you assign (human/debug friendly)
- `episode_body`: the content (text / conversation / JSON-like dict)
- `source`: an enum describing the input shape (text/message/json)
- `source_description`: metadata about origin (doc, system, etc.)
- `reference_time`: “world time” anchor (when the episode occurred / should be interpreted)

Why episodes matter:
- They preserve **provenance** (“where did this fact come from?”)
- They enable **temporal reasoning** (“what was true at time T?”)
- They enable **conflict resolution** when newer episodes update older facts

### 1.2 Entity (node)
An **Entity** is a node representing a thing: Person, Org, Product, Concept, etc.

Entity nodes commonly store:
- `uuid` (Graphiti’s internal unique identifier)
- `name` (human-readable label)
- `summary` and other extracted attributes (depending on config / custom ontology)
- optional `group_id` (namespace / multi-tenant partition)

### 1.3 Fact / Edge (relationship)
A **Fact** is usually an edge between two entities.

Edges commonly store:
- `name` or `relationship_type` (e.g., `WORKS_AT`, `LIKES`, etc.)
- `fact` (human-readable statement string)
- optional structured properties (if using custom edge types)
- **temporal fields** (see Bi-temporal model below)
- optional `group_id`

Graphiti often stores domain-specific predicate type as a **property** rather than a Neo4j relationship type,
so the Neo4j rel type can remain stable (e.g., `RELATES_TO`) while the predicate lives in `name`.
(Implementation details can vary by version/config; treat this as “likely default.”)

### 1.4 Group / namespace (`group_id`)
`group_id` is Graphiti’s built-in **namespacing mechanism** used across ingestion and retrieval.

Use it to:
- isolate data per tenant/project/user
- keep multiple disjoint graphs in one Neo4j DB
- ensure queries don’t mix unrelated contexts

**Rule:** be consistent — assign the same `group_id` to all episodes and facts that belong together.

### 1.5 Community (optional)
Graphiti can cluster the graph into **communities** (groups of strongly related entities)
and generate summaries for these clusters.

Use cases:
- higher-level “topic” retrieval
- graph-level summarization / organization
- query-time boost via community relevance (depending on search config)

---

## 2) Bi-temporal model (how time works)

Graphiti tracks two different “time axes”:

### 2.1 World/validity time (“when it is true”)
- Often represented as `valid_at` (start) and `invalid_at` (end), or similar fields.
- Derived from:
  - explicit dates in episode text
  - relative dates resolved against `reference_time`
  - sometimes defaulting to `reference_time` when no explicit time is present

### 2.2 System/ingestion time (“when we learned it”)
- Often represented as:
  - `created_at` (when inserted into the graph)
  - `expired_at` (when a fact is superseded by a later conflicting fact)

### 2.3 Supersession / invalidation behavior
When a new episode introduces a fact that **conflicts with** or **updates** an old fact,
Graphiti typically:
- keeps the old edge (history preserved)
- sets `expired_at` on the older edge
- inserts/keeps the newer edge as “current”

Implications for agents:
- You can answer:
  - “what is true now?” (facts without `expired_at`, or expired_at is null)
  - “what was believed at time T?” (facts where `created_at <= T < expired_at`)
  - “what was true in the world at time T?” (facts where `valid_at <= T < invalid_at`)

---

## 3) Neo4j backend: what Graphiti expects

### 3.1 Neo4j version
Graphiti relies on Neo4j 5.x capabilities (notably vector indexing and full-text features).
Choose a recent 5.x.

### 3.2 Indices and constraints
Graphiti typically initializes:
- node uniqueness constraints (e.g., `uuid`)
- indexes on time fields used in temporal filtering
- full-text indexes over text fields (names, summaries, fact strings)
- vector indexes for embedding properties used in semantic search

This initialization is usually done via an API call like:
- `build_indices_and_constraints()` (or equivalent in your version)

**Operational note:** run index/constraint bootstrap once per DB before real traffic.

---

## 4) Installation & basic setup (Python)

### 4.1 Install
Typical: `pip install graphiti-core` (exact package name can vary by release).

### 4.2 Initialize Graphiti with Neo4j
Most common pattern:

```py
from graphiti_core import Graphiti

graphiti = Graphiti(
    neo4j_uri="bolt://localhost:7687",
    neo4j_user="neo4j",
    neo4j_password="password",
)
```

Then (recommended) bootstrap:

```py
await graphiti.build_indices_and_constraints()
```

### 4.3 Using a custom Neo4j database
If you need to use a specific Neo4j database (multi-db deployments),
Graphiti typically allows passing a Neo4j driver that is configured with `database="..."`.
(Exact class names differ by version; the common approach is: create a driver/graph-driver
with the desired database, then pass it to Graphiti.)

---

## 5) Ingestion APIs

Graphiti supports two main ingestion styles:

1) **Episode ingestion** (preferred for natural language + provenance + time)
2) **Direct triplet ingestion** (when you already have structured triples)

### 5.1 Add an episode
Conceptually:

```py
from graphiti_core import EpisodeType
from datetime import datetime

await graphiti.add_episode(
    name="episode_id_or_title",
    episode_body="Some text, conversation, or JSON dict",
    source=EpisodeType.text,            # or message/json
    source_description="where it came from",
    reference_time=datetime.utcnow(),   # important for temporal resolution
    group_id="tenant_or_project_scope", # optional but recommended
)
```

**EpisodeType patterns**
- `EpisodeType.text`: plain text blobs (documents, notes)
- `EpisodeType.message`: conversation transcripts (speaker: message)
- `EpisodeType.json`: structured dicts (records, events)

**What happens inside `add_episode`**
- parse episode content
- extract entities + edges (often via an LLM extraction pipeline)
- resolve/merge entities against existing graph
- insert new/updated edges with temporal fields
- update entity summaries (depending on configuration)
- optionally update communities (if enabled)

### 5.2 Bulk ingestion
Graphiti typically provides a bulk method (name varies) such as:

- `add_episode_bulk([...])`

Use it for:
- initial imports
- large batch updates

Tradeoffs:
- bulk ingestion may skip/relax some conflict-resolution work for speed
  (depends on version)
- tune concurrency to avoid provider rate limits

### 5.3 Direct triple ingestion
If you already know `(subject, predicate, object)` deterministically:

```py
from graphiti_core.nodes import EntityNode
from graphiti_core.edges import EntityEdge
from datetime import datetime
import uuid

s = EntityNode(uuid=str(uuid.uuid4()), name="Alice", group_id="g")
o = EntityNode(uuid=str(uuid.uuid4()), name="Acme Corp", group_id="g")
e = EntityEdge(
    group_id="g",
    source_node_uuid=s.uuid,
    target_node_uuid=o.uuid,
    name="WORKS_AT",
    fact="Alice works at Acme Corp",
    created_at=datetime.utcnow(),
)
await graphiti.add_triplet(s, e, o)
```

Use cases:
- importing structured relational facts
- enforcing exact semantics without LLM extraction
- integrating with upstream structured extractors

### 5.4 Custom ontology (typed entities + typed edges)
Graphiti supports custom schemas using **Pydantic models**.

You define:
- entity types (e.g., `Person`, `Company`, `Product`)
- edge types (e.g., `Employment`, `Purchase`, `LocatedIn`)
- a mapping from entity-type pairs to edge types (`edge_type_map`)

Then provide them during ingestion so the extractor fills structured fields.

Conceptually:

```py
entity_types={"Person": PersonModel, "Company": CompanyModel}
edge_types={"Employment": EmploymentEdgeModel}
edge_type_map={("Person", "Company"): "Employment"}

await graphiti.add_episode(..., entity_types=entity_types, edge_types=edge_types, edge_type_map=edge_type_map)
```

This is how you get:
- typed properties on nodes/edges
- more predictable extraction
- domain-specific attributes (dates, amounts, roles, etc.)

---

## 6) Retrieval / querying APIs

Graphiti is designed so **query-time does not require LLM calls** by default.
It relies on:
- vector similarity (semantic)
- full-text BM25 (keyword)
- optional reranking
- optional graph proximity boosts

### 6.1 Simple search
Conceptually:

```py
results = await graphiti.search(
    "question text",
    group_id="scope",
)
```

Typical result is a list of matching **edges (facts)** with metadata:
- fact string
- source/target nodes
- temporal fields
- scores (depending on API)

### 6.2 Focal-node search (graph proximity reranking)
If you want results centered around a particular entity:

```py
results = await graphiti.search(
    "question about Jane",
    focal_node_uuid=jane_uuid,
    group_id="scope",
)
```

This often:
- runs hybrid retrieval first
- then reranks by graph distance to focal node

### 6.3 Advanced search with SearchConfig / “recipes”
Graphiti typically provides:
- a lower-level `_search(SearchConfig)` API
- a set of prebuilt “recipes” (config presets) like:
  - combined node+edge hybrid search with RRF fusion
  - edge hybrid search + node-distance rerank
  - edge hybrid search + cross-encoder rerank
  - node hybrid search + MMR diversity

Pattern:

```py
from graphiti_core.search import SearchConfig, SEARCH_PRESET

cfg = SEARCH_PRESET.EDGE_HYBRID_SEARCH_NODE_DISTANCE
results = await graphiti._search(cfg, query="...", focal_node_uuid=..., group_id="...")
```

Use this when:
- you need control over node vs edge vs community retrieval
- you want rerankers (cross-encoder) or diversity (MMR)
- you need different top-k per channel (semantic vs BM25)

### 6.4 What “hybrid” means operationally
Hybrid retrieval commonly means:
1) embed the query
2) vector-search against stored embeddings of nodes/edges
3) full-text query against indexed text fields
4) fuse rankings (e.g., Reciprocal Rank Fusion)
5) optionally rerank (node-distance, cross-encoder)
6) return results with enough structure to build an answer

### 6.5 Temporal querying patterns (agent-side)
Graphiti may not expose full temporal predicates in one call, but you can:
- filter results by temporal fields returned by Graphiti, OR
- run Cypher directly on Neo4j against the same schema

Common filters:
- **current facts:** `expired_at is null`
- **as-known-at time T:** `created_at <= T < expired_at (or expired_at is null)`
- **true-in-world-at time T:** `valid_at <= T < invalid_at (or invalid_at is null)`

---

## 7) MCP Server (optional service mode)

Graphiti offers an MCP server that exposes Graphiti operations as tools over HTTP transport.

Typical characteristics:
- endpoints like `/mcp/` plus a `/health` endpoint
- supports:
  - adding episodes
  - searching (hybrid retrieval)
  - browsing entities/episodes
  - group/namespace scoping

When to use MCP server:
- you want Graphiti as a standalone service
- you want multiple apps/agents to share one KG service
- you want a clean network boundary around Neo4j credentials

---

## 8) Embeddings & vector search (Neo4j)

Graphiti’s semantic search depends on:
- generating embeddings for:
  - query text
  - stored text fields (entity summaries, fact strings, etc.)
- storing them as vector properties in Neo4j
- creating vector indexes for fast KNN search

Practical notes:
- Embedding dimensionality must match the vector index definition.
- If you switch embedding models, you must rebuild vectors and indexes accordingly.
- Ensure the Neo4j instance has sufficient memory/disk for vector indexes at scale.

---

## 9) Concurrency, rate limits, and throughput

Graphiti ingestion often makes external model calls (LLM extraction, embeddings).

Key knob:
- `SEMAPHORE_LIMIT` (or similar): controls max concurrent tasks
  - raise for faster bulk ingestion
  - lower if you hit rate limits (429s) or resource saturation

Guidance:
- Bulk imports: moderate concurrency, batch episodes, observe Neo4j write throughput.
- Live systems: keep concurrency stable and avoid large spikes.

---

## 10) Observability & debugging

### 10.1 Logging
Graphiti emits logs for:
- index/constraint bootstrap
- ingestion steps
- provider errors (rate limits, parse failures)
- database errors (constraint/index conflicts)

### 10.2 Tracing
Graphiti has support for OpenTelemetry-style tracing in some versions.
If enabled, you can trace:
- ingestion pipeline stages
- query execution stages
- external provider calls

### 10.3 Health checks
In MCP server mode, a `/health` endpoint is typically available for:
- liveness checks
- load balancer probes

### 10.4 Neo4j Browser for inspection
Since it’s Neo4j:
- inspect nodes/edges directly in Neo4j Browser / Bloom
- validate:
  - entity merges
  - fact edges
  - temporal fields
  - group_id partitions
  - indexes existence

---

## 11) Common patterns for agents (practical playbook)

### Pattern A: “Add memory → answer question”
1) `add_episode(...)` for new information  
2) `search(query, group_id=...)` to retrieve top facts  
3) Construct an answer using retrieved facts (include provenance/episode pointers if desired)

### Pattern B: “Entity-centric reasoning”
1) Find entity node UUID via node search
2) Use `search(..., focal_node_uuid=entity_uuid)` to prioritize nearby facts
3) Optionally traverse the entity neighborhood with Cypher for full context

### Pattern C: “Time-aware answers”
1) Retrieve facts via Graphiti search
2) Filter by `valid_at/invalid_at` or `created_at/expired_at` according to question
3) Answer with explicit timestamps when available

### Pattern D: “Strict schema / structured extraction”
1) Define Pydantic entity/edge models
2) Provide `entity_types`, `edge_types`, `edge_type_map` to ingestion
3) Prefer structured properties over free-form fact strings for downstream logic

---

## 12) Things to be careful about

- **Consistency of `group_id`:** missing/incorrect group scoping causes retrieval leakage.
- **Embedding model changes:** require re-embedding + index rebuild to avoid dimension mismatch.
- **Bulk ingestion semantics:** may not perfectly replicate incremental conflict resolution in all versions.
- **Entity deduplication:** extraction/merge behavior is probabilistic; consider custom keys or stronger schemas if needed.
- **Temporal interpretation:** if episodes lack explicit dates, `reference_time` becomes critical.

---

## 13) Minimal “hello world” (end-to-end)

```py
import asyncio
from datetime import datetime
from graphiti_core import Graphiti, EpisodeType

async def main():
    g = Graphiti(
        neo4j_uri="bolt://localhost:7687",
        neo4j_user="neo4j",
        neo4j_password="password",
    )

    await g.build_indices_and_constraints()

    await g.add_episode(
        name="e1",
        episode_body="Jane bought wool runners last week. Jane is allergic to wool.",
        source=EpisodeType.text,
        source_description="note",
        reference_time=datetime.utcnow(),
        group_id="demo",
    )

    facts = await g.search("Can Jane wear wool runners?", group_id="demo")
    for f in facts[:10]:
        # exact fields vary by version; print what you have
        print(f)

asyncio.run(main())
```

---

## 14) What to look up in your pinned Graphiti version (agent TODO checklist)

Graphiti’s OSS evolves quickly. For the exact version you pin, confirm:
- exact method names:
  - `build_indices_and_constraints` vs similar
  - `add_episode_bulk` naming and semantics
  - `search` return types / fields
  - `_search` / `SearchConfig` module names
- which properties and labels are used in Neo4j:
  - edge relationship type name (`RELATES_TO` or variant)
  - where embeddings are stored (node property names)
  - index names created at bootstrap
- MCP server supported tools and request/response schema

The above document gives the stable mental model and usage patterns; the final mile is aligning to the pinned release’s identifiers.

---

---
title: Graph Namespacing
subtitle: Using group_ids to create isolated graph namespaces
---

## Overview

Graphiti supports the concept of graph namespacing through the use of `group_id` parameters. This feature allows you to create isolated graph environments within the same Graphiti instance, enabling multiple distinct knowledge graphs to coexist without interference.

Graph namespacing is particularly useful for:

- **Multi-tenant applications**: Isolate data between different customers or organizations
- **Testing environments**: Maintain separate development, testing, and production graphs
- **Domain-specific knowledge**: Create specialized graphs for different domains or use cases
- **Team collaboration**: Allow different teams to work with their own graph spaces

## How Namespacing Works

In Graphiti, every node and edge can be associated with a `group_id`. When you specify a `group_id`, you're effectively creating a namespace for that data. Nodes and edges with the same `group_id` form a cohesive, isolated graph that can be queried and manipulated independently from other namespaces.

### Key Benefits

- **Data isolation**: Prevent data leakage between different namespaces
- **Simplified management**: Organize and manage related data together
- **Performance optimization**: Improve query performance by limiting the search space
- **Flexible architecture**: Support multiple use cases within a single Graphiti instance

## Using group_ids in Graphiti

### Adding Episodes with group_id

When adding episodes to your graph, you can specify a `group_id` to namespace the episode and all its extracted entities:

```python
await graphiti.add_episode(
    name="customer_interaction",
    episode_body="Customer Jane mentioned she loves our new SuperLight Wool Runners in Dark Grey.",
    source=EpisodeType.text,
    source_description="Customer feedback",
    reference_time=datetime.now(),
    group_id="customer_team"  # This namespaces the episode and its entities
)
```

### Adding Fact Triples with group_id

When manually adding fact triples, ensure both nodes and the edge share the same `group_id`:

```python
from graphiti_core.nodes import EntityNode
from graphiti_core.edges import EntityEdge
import uuid
from datetime import datetime

# Define a namespace for this data
namespace = "product_catalog"

# Create source and target nodes with the namespace
source_node = EntityNode(
    uuid=str(uuid.uuid4()),
    name="SuperLight Wool Runners",
    group_id=namespace  # Apply namespace to source node
)

target_node = EntityNode(
    uuid=str(uuid.uuid4()),
    name="Sustainable Footwear",
    group_id=namespace  # Apply namespace to target node
)

# Create an edge with the same namespace
edge = EntityEdge(
    group_id=namespace,  # Apply namespace to edge
    source_node_uuid=source_node.uuid,
    target_node_uuid=target_node.uuid,
    created_at=datetime.now(),
    name="is_category_of",
    fact="SuperLight Wool Runners is a product in the Sustainable Footwear category"
)

# Add the triplet to the graph
await graphiti.add_triplet(source_node, edge, target_node)
```

### Querying Within a Namespace

When querying the graph, specify the `group_id` to limit results to a particular namespace:

```python
# Search within a specific namespace
search_results = await graphiti.search(
    query="Wool Runners",
    group_id="product_catalog"  # Only search within this namespace
)

# For more advanced node-specific searches, use the _search method with a recipe
from graphiti_core.search.search_config_recipes import NODE_HYBRID_SEARCH_RRF

# Create a search config for nodes only
node_search_config = NODE_HYBRID_SEARCH_RRF.model_copy(deep=True)
node_search_config.limit = 5  # Limit to 5 results

# Execute the node search within a specific namespace
node_search_results = await graphiti._search(
    query="SuperLight Wool Runners",
    group_id="product_catalog",  # Only search within this namespace
    config=node_search_config
)
```

## Best Practices for Graph Namespacing

1. **Consistent naming**: Use a consistent naming convention for your `group_id` values
2. **Documentation**: Maintain documentation of your namespace structure and purpose
3. **Granularity**: Choose an appropriate level of granularity for your namespaces
   - Too many namespaces can lead to fragmented data
   - Too few namespaces may not provide sufficient isolation
4. **Cross-namespace queries**: When necessary, perform multiple queries across namespaces and combine results in your application logic

## Example: Multi-tenant Application

Here's an example of using namespacing in a multi-tenant application:

```python
async def add_customer_data(tenant_id, customer_data):
    """Add customer data to a tenant-specific namespace"""
    
    # Use the tenant_id as the namespace
    namespace = f"tenant_{tenant_id}"
    
    # Create an episode for this customer data
    await graphiti.add_episode(
        name=f"customer_data_{customer_data['id']}",
        episode_body=customer_data,
        source=EpisodeType.json,
        source_description="Customer profile update",
        reference_time=datetime.now(),
        group_id=namespace  # Namespace by tenant
    )

async def search_tenant_data(tenant_id, query):
    """Search within a tenant's namespace"""
    
    namespace = f"tenant_{tenant_id}"
    
    # Only search within this tenant's namespace
    return await graphiti.search(
        query=query,
        group_id=namespace
    )
```