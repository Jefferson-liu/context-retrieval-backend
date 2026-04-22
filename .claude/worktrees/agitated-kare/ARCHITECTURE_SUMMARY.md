# Context Retrieval Backend - Architecture Summary

**Generated:** 2024
**Repository:** context-retrieval-backend

---

## System Overview

This is a **FastAPI-based backend service** that integrates with **Graphiti** (a knowledge graph system built on Neo4j) to ingest, chunk, and semantically search product management artifacts such as documents and Slack-like conversation threads.

The system enables:
- Multi-tenant data ingestion with chunking
- Knowledge graph construction from unstructured text
- Semantic search across ingested knowledge
- Thread-based conversation context capture
- Custom ontology mapping for PM-specific entities (Products, Features, Decisions, etc.)

---

## Tech Stack

### Core Framework
- **FastAPI** - Async web framework
- **Python 3.10+** - With modern type hints
- **SQLAlchemy 2.0** - Async ORM for PostgreSQL
- **PostgreSQL** - Primary data store (via asyncpg)

### Knowledge Graph
- **Graphiti Core** - Knowledge graph abstraction layer
- **Neo4j** - Graph database backend
- **OpenAI/Gemini** - LLM providers for entity extraction
- **LangChain** - Text splitting and chunking utilities

### Dependencies
- **Pydantic** - Schema validation
- **python-dotenv** - Environment configuration
- **uvicorn** - ASGI server

---

## Architecture Layers

The system follows a **strict layered architecture** with clear separation of concerns:

```
┌─────────────────────────────────────────────────────┐
│                   API Layer (Routers)                │
│  - HTTP request/response handling                    │
│  - Input validation                                  │
│  - Dependency injection                              │
└────────────────┬────────────────────────────────────┘
                 │
┌────────────────▼────────────────────────────────────┐
│               Service Layer                          │
│  - Business logic                                    │
│  - Orchestration                                     │
│  - Framework-agnostic                                │
└────────────────┬────────────────────────────────────┘
                 │
┌────────────────▼────────────────────────────────────┐
│            Repository Layer                          │
│  - Database operations                               │
│  - ORM interactions                                  │
│  - Returns domain models                             │
└────────────────┬────────────────────────────────────┘
                 │
┌────────────────▼────────────────────────────────────┐
│          Infrastructure Layer                        │
│  - Database connections                              │
│  - External service clients (Graphiti, Neo4j)        │
│  - Configuration management                          │
└─────────────────────────────────────────────────────┘
```

---

## Core Modules

### 1. **Entry Point** (`main.py`)
- Initializes FastAPI application
- Sets up lifespan context for:
  - Database initialization (`init_db`)
  - Graphiti bootstrap (`ensure_bootstrap`)
- Registers four main routers:
  - `/documents` - Document ingestion
  - `/threads` - Slack thread ingestion
  - `/data` - Generic data CRUD
  - `/search` - Graphiti-powered search

### 2. **Configuration** (`config/`)
- `settings.py` - Environment-based configuration
  - Database URL (PostgreSQL)
  - Neo4j credentials
  - LLM API keys (OpenAI, Anthropic, Gemini)
  - Multi-tenancy defaults
  - Model selection (OpenAI vs Gemini)

### 3. **Infrastructure** (`infrastructure/`)

#### Database (`database.py`)
- Async SQLAlchemy engine setup
- Session factory (`SessionLocal`)
- `Base` declarative class for ORM models
- `get_session()` FastAPI dependency

#### Graphiti Client (`graphiti/graphiti_client.py`)
- Singleton Graphiti client factory
- Supports both OpenAI and Gemini backends
- Handles Neo4j connection management
- `build_group_id()` - Tenant/user scoping for knowledge graphs

#### Ontology (`graphiti/ontology.py`)
**Custom PM-focused entity types:**
- `Product`, `Feature`, `Decision`, `Issue`, `Release`
- `Person`, `Team`, `Component`

**Custom relationship types:**
- `WorksOn`, `Owns`, `DependsOn`, `Implements`, `Blocks`, `Decides`, `Mentions`, `HasFeature`

**Edge type mapping** - Defines valid relationships between entity types

#### Models (`models/data.py`)
**Database schema:**
- `DataRecord` - Root data item (multi-tenant)
  - Fields: `id`, `tenant_id`, `user_id`, `title`, `body`, `created_at`
  - Relationships: `chunks`, `graphiti_episodes`
- `ChunkRecord` - Text chunks belonging to data
  - Fields: `id`, `data_id`, `chunk_index`, `content`
- `GraphitiEpisodeRecord` - Tracks Graphiti episode UUIDs
  - Links SQL records to Neo4j episodes
  - Enables cascade deletion

### 4. **Repositories** (`infrastructure/repositories/`)

#### DataRepository (`data_repository.py`)
- `create_with_chunks()` - Atomic data + chunks creation
- `list()` - Tenant/user-scoped listing
- `get()` - Single record retrieval
- `delete()` - Cascade deletion

#### ChunkRepository (`chunk_repository.py`)
- `list_for_data()` - Get all chunks for a data record

#### GraphitiEpisodeRepository (`graphiti_episode_repository.py`)
- `create_batch()` - Batch episode UUID storage
- `list_episode_uuids_for_data()` - Retrieve UUIDs for cleanup

### 5. **Services** (`services/`)

#### DataService (`data_service.py`)
**Core operations:**
- `create_record()` - Ingest document with chunking
  - Splits text using LangChain
  - Creates SQL records
  - Sends episodes to Graphiti via `add_episode_bulk()`
- `create_records_bulk()` - Batch ingestion with per-file error handling
- `list_records()` - List tenant/user data
- `get_record()` - Get record with chunks
- `delete_record()` - Delete from both SQL and Neo4j

#### ThreadService (`thread_service.py`)
**Thread-specific ingestion:**
- `ingest_thread()` - Process Slack-like conversation threads
  - Normalizes message formats
  - Chunks messages using `RecursiveJsonSplitter`
  - Creates `Thread` node in Neo4j
  - Links entities to threads via `mentioned_in_thread` edges
  - Preserves temporal ordering

**Helper functions:**
- `_normalize_thread_messages()` - Parse Slack format
- `_attach_thread_context()` - Create thread node + relationships
- `_thread_uuid()` - Deterministic UUID generation

#### ChunkingService (`chunking.py`)
- `chunk_document()` - Generic text chunking
- `chunk_thread()` - JSON-aware thread chunking
- Uses LangChain's `RecursiveCharacterTextSplitter` and `RecursiveJsonSplitter`

#### SearchService (`search_service.py`)
- Thin wrapper around Graphiti search
- Supports multi-tenant group IDs
- Returns fact triples with validity timestamps

### 6. **Routers** (`routers/`)

#### Scope Management (`scope.py`)
- `get_scope()` - FastAPI dependency for tenant/user context
- Can use placeholder defaults for development
- Production mode requires explicit tenant/user

#### Data Router (`data_router.py`)
- `POST /data` - Create single record
- `POST /data/bulk` - Batch upload
- `GET /data` - List records
- `GET /data/{id}` - Get record with chunks
- `DELETE /data/{id}` - Delete record

#### Document Router (`document_router.py`)
- `POST /documents` - Upload documents (form-data or JSON)
- Supports multiple file uploads

#### Thread Router (`thread_router.py`)
- `POST /threads` - Ingest Slack thread
- Accepts array of message objects

#### Search Router (`search_router.py`)
- `GET /search?q=<query>` - Semantic search across knowledge graph

### 7. **Schemas** (`schemas/`)
- `DataCreateRequest`, `DataResponse`
- `ThreadCreateRequest`, `ThreadIngestResponse`
- Pydantic models for validation

### 8. **Scripts** (`scripts/`)
- `reset_storage.py` - Wipe SQL + Neo4j data for testing

---

## Execution Flows

### Document Ingestion Flow
```
POST /data
  ↓
DataRouter
  ↓
DataService.create_record()
  ├─→ chunk_document() → LangChain splitting
  ├─→ DataRepository.create_with_chunks() → SQL insert
  └─→ Graphiti.add_episode_bulk() → Neo4j ingestion
      ├─→ Entity extraction (LLM)
      ├─→ Relationship detection
      └─→ GraphitiEpisodeRepository.create_batch()
```

### Thread Ingestion Flow
```
POST /threads
  ↓
ThreadRouter
  ↓
ThreadService.ingest_thread()
  ├─→ _normalize_thread_messages() → Parse Slack format
  ├─→ chunk_thread() → JSON-aware chunking
  ├─→ DataRepository.create_with_chunks() → SQL insert
  └─→ For each chunk:
      ├─→ Graphiti.add_episode() → Neo4j ingestion
      ├─→ _attach_thread_context() → Create Thread node
      └─→ Link entities → mentioned_in_thread edges
```

### Search Flow
```
GET /search?q=<query>
  ↓
SearchRouter
  ↓
SearchService.search()
  ↓
Graphiti.search()
  ├─→ Embed query (OpenAI/Gemini)
  ├─→ Neo4j vector similarity search
  └─→ Return ranked fact triples
```

### Deletion Flow
```
DELETE /data/{id}
  ↓
DataService.delete_record()
  ├─→ GraphitiEpisodeRepository.list_episode_uuids_for_data()
  ├─→ For each episode: Graphiti.remove_episode() → Neo4j cleanup
  └─→ DataRepository.delete() → SQL cascade delete
```

---

## Multi-Tenancy Strategy

**Tenant/User Scoping:**
- All data records include `tenant_id` and `user_id` columns
- Composite index: `(tenant_id, user_id)` on `data_records`
- Graphiti uses `group_id` = `{tenant_id}_{user_id}` (sanitized)
- All queries filtered by scope (via `get_scope()` dependency)

**Development Mode:**
- `USE_PLACEHOLDER_SCOPE=true` → Uses default tenant/user
- Production: Requires explicit scope in requests

---

## Key Design Patterns

### 1. **Dependency Injection**
- FastAPI `Depends()` for session, scope, and Graphiti client
- Enables testability and decoupling

### 2. **Repository Pattern**
- All SQL operations isolated in repositories
- Services never write raw SQL/ORM queries

### 3. **Service Layer Orchestration**
- Services coordinate between repositories and external systems
- Business logic lives here, not in routers

### 4. **Cascade Operations**
- SQL: Foreign keys with `ondelete="CASCADE"`
- Graphiti: Manual episode cleanup before SQL deletion

### 5. **Transactional Boundaries**
- Per-request transactions via `get_session()`
- Explicit `commit()` in routers after service calls
- Rollback on errors

### 6. **Chunking Strategy**
- Documents: Fixed-size text chunks (default 2000 chars)
- Threads: JSON-aware chunking preserving message atomicity
- Overlapping chunks for context continuity

---

## Data Flow Diagram

```
┌─────────────┐
│   FastAPI   │  ← HTTP Requests (REST API)
└──────┬──────┘
       │
       ├──→ Routers (validate, extract scope)
       │
       ├──→ Services (orchestrate logic)
       │     │
       │     ├──→ Chunking (LangChain)
       │     │
       │     ├──→ Repositories (SQL ORM)
       │     │     │
       │     │     └──→ PostgreSQL
       │     │           ├─ data_records
       │     │           ├─ chunks
       │     │           └─ graphiti_episodes
       │     │
       │     └──→ Graphiti Client
       │           │
       │           └──→ Neo4j
       │                 ├─ Entities (nodes)
       │                 ├─ Relationships (edges)
       │                 └─ Episodes
       │
       └──→ Return JSON response
```

---

## Critical Dependencies

### SQL ↔ Neo4j Linkage
- `GraphitiEpisodeRecord` stores episode UUIDs
- Enables cleanup when deleting SQL records
- Prevents orphaned Neo4j data

### Graphiti Ontology
- Custom entity/edge types defined in `ontology.py`
- Passed to every `add_episode()` call
- Guides LLM extraction

### Multi-Provider Support
- OpenAI: Default LLM/embedder
- Gemini: Alternative with custom client config
- Configured via `MODEL` environment variable

---

## Testing Strategy

### Scripts
- `reset_storage.py` - Wipes both SQL and Neo4j
- Useful for integration testing

### Repository Layer
- Unit test repositories with in-memory SQLite
- Mock Graphiti client for service tests

---

## Deployment Considerations

### Environment Variables
```
DATABASE_URL=postgresql+asyncpg://...
NEO4J_URI=bolt://...
NEO4J_USER=neo4j
NEO4J_PASSWORD=...
PERSONAL_OPENAI_KEY=sk-...
GEMINI_API_KEY=...
MODEL=openai|gemini
APP_ENV=dev|prod
USE_PLACEHOLDER_SCOPE=0|1
DEFAULT_TENANT_ID=demo_tenant
DEFAULT_USER_ID=demo_user
SEMAPHORE_LIMIT=10
```

### Database Migrations
- Uses `Base.metadata.create_all()` on startup
- For production, use Alembic for schema migrations

### Graphiti Bootstrap
- `ensure_bootstrap()` creates Neo4j indices/constraints
- Runs once on application startup

---

## Architecture Principles (per AGENTS.md)

### Coding Standards
1. **Layered Architecture** - Strict separation (Router → Service → Repository)
2. **Type Hints** - All function signatures typed
3. **No Raw SQL in Services** - All SQL in repositories
4. **Pydantic Everywhere** - Validation at API boundary
5. **Custom Exceptions** - Mapped to HTTP status codes

### Memory Protocol
- `.planning/` folder for documentation
- `active-state.md` for session persistence
- `technical-info/` for feature specs
- `nontechnical-info/` for product context

---

## Future Enhancements

### Planned Improvements
- **Incremental Updates** - Update existing episodes instead of re-ingesting
- **Advanced Search** - Filters by entity type, date range, tenant
- **Graph Analytics** - Centrality, clustering, community detection
- **Export/Import** - Bulk graph export for backups
- **Webhook Support** - Real-time ingestion from Slack, Notion, etc.

### Technical Debt
- No Alembic migrations yet (uses `create_all()`)
- Limited error handling in Graphiti calls
- No retry logic for Neo4j transient failures
- Missing comprehensive test suite

---

## Summary

This backend serves as a **knowledge graph ingestion pipeline** for product management artifacts. It bridges SQL (for structured data/audit) and Neo4j (for semantic relationships), using Graphiti as an abstraction layer with LLM-powered entity extraction.

The architecture prioritizes **clean separation**, **multi-tenancy**, and **extensibility** through a custom ontology system tailored to product management entities.
