import sys
from pathlib import Path

import pytest
from sqlalchemy import select, text

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from infrastructure.context import ContextScope
from infrastructure.database.database import create_tables, engine, get_db
from infrastructure.database.models.tenancy import Project, Tenant
from infrastructure.database.repositories import DocumentRepository, ChunkRepository
from infrastructure.database.repositories.knowledge_repository import (
    KnowledgeEntityAliasRepository,
    KnowledgeEntityRepository,
)
from infrastructure.database.setup import (
    DEFAULT_PROJECT_SLUG,
    DEFAULT_TENANT_SLUG,
    DEFAULT_USER_ID,
    configure_multi_tenant_rls,
    seed_default_tenant_and_project,
)
from schemas.knowledge_graph.raw_statement import RawStatement
from schemas.knowledge_graph.entities.raw_entity import RawEntity
from schemas.knowledge_graph.raw_extraction import RawExtraction
from schemas.knowledge_graph.triplets.raw_triplet import RawTriplet
from services.knowledge.entity_resolution_service import EntityResolutionService
from services.knowledge.knowledge_context import KnowledgeContextBuilder
from services.knowledge.knowledge_service import KnowledgeGraphService
from schemas.knowledge_graph.temporal_event import TemporalEvent
from infrastructure.database.models.knowledge import KnowledgeStatement, KnowledgeStatementTriplet
from infrastructure.database.repositories.knowledge_temporal_repository import (
    KnowledgeStatementRepository,
    KnowledgeStatementTripletRepository,
)


@pytest.fixture
def anyio_backend():
    return "asyncio"


class FakeLLM:
    """Stub chat model not exercised in this test."""

    async def ainvoke(self, _messages):
        return "stub"

    def with_structured_output(self, _schema):
        class StructuredStub:
            async def ainvoke(self, _inputs):
                return _schema()

        return StructuredStub()


class StubTemporalAgent:
    def __init__(self, results: list[TemporalEvent]) -> None:
        self.results = results
        self.calls: list[dict[str, str]] = []

    async def process_chunk(self, *, document_name: str, chunk_text: str, reference_timestamp: str, extra_inputs: dict | None = None):
        self.calls.append(
            {
                "document_name": document_name,
                "chunk_text": chunk_text,
                "reference_timestamp": reference_timestamp,
                "extra_inputs": extra_inputs or {},
            }
        )
        return self.results


@pytest.mark.anyio("asyncio")
async def test_knowledge_graph_pipeline_populates_entities_and_context():
    await create_tables()

    async with engine.begin() as conn:
        for table in (
            "knowledge_relationship_metadata",
            "knowledge_relationships",
            "knowledge_entity_aliases",
            "knowledge_entities",
            "chunks",
            "documents",
        ):
            await conn.execute(text(f"TRUNCATE {table} RESTART IDENTITY CASCADE"))
        await configure_multi_tenant_rls(conn)

    await seed_default_tenant_and_project()

    db_gen = get_db()
    session = await db_gen.__anext__()
    try:
        tenant_row = await session.execute(
            select(Tenant).where(Tenant.slug == DEFAULT_TENANT_SLUG)
        )
        tenant = tenant_row.scalar_one()

        project_row = await session.execute(
            select(Project).where(
                Project.slug == DEFAULT_PROJECT_SLUG,
                Project.tenant_id == tenant.id,
            )
        )
        project = project_row.scalar_one()

        await session.execute(
            text("SELECT set_app_context(:tenant_id, :project_ids)"),
            {"tenant_id": tenant.id, "project_ids": str(project.id)},
        )

        scope = ContextScope(
            tenant_id=tenant.id,
            project_ids=[project.id],
            user_id=DEFAULT_USER_ID,
        )

        doc_repo = DocumentRepository(session, scope)
        document = await doc_repo.create_document(
            doc_name="integration.md",
            content="TrackRec integrates with Salesforce to sync opportunities nightly.",
            doc_size=76,
            doc_type="text/markdown",
        )
        await session.flush()

        raw_statement = RawStatement(
            statement="TrackRec integrates with Salesforce nightly.",
            statement_type="FACT",
            temporal_type="STATIC",
        )
        extraction = RawExtraction(
            triplets=[
                RawTriplet(
                    subject_name="TrackRec",
                    subject_id=0,
                    predicate="INTEGRATES_WITH",
                    object_name="Salesforce",
                    object_id=1,
                    value="nightly sync",
                )
            ],
            entities=[
                RawEntity(entity_idx=0, name="TrackRec", type="Product", description="ATS platform"),
                RawEntity(entity_idx=1, name="Salesforce", type="Integration", description="CRM"),
            ],
        )
        temporal_result = TemporalEvent(
            statement=raw_statement,
            valid_at="2024-01-01T00:00:00Z",
            invalid_at=None,
            extraction=extraction,
        )
        temporal_agent = StubTemporalAgent([temporal_result])
        service = KnowledgeGraphService(
            session,
            scope,
            llm=FakeLLM(),
            entity_repository=KnowledgeEntityRepository(session, scope),
            alias_repository=KnowledgeEntityAliasRepository(session, scope),
            statement_repository=KnowledgeStatementRepository(session, scope),
            triplet_repository=KnowledgeStatementTripletRepository(session, scope),
            document_repository=DocumentRepository(session, scope),
            chunk_repository=ChunkRepository(session, scope),
            temporal_agent=temporal_agent,
        )

        await service.refresh_document_knowledge(
            document_id=document.id,
            document_name=document.doc_name,
            document_content=document.content,
        )
        await session.flush()

        entity_repo = KnowledgeEntityRepository(session, scope)
        entities = await entity_repo.list_entities()
        assert len(entities) == 2

        statement_rows = await session.execute(select(KnowledgeStatement))
        statements = statement_rows.scalars().all()
        assert statements, "Expected at least one knowledge statement"

        triplet_rows = await session.execute(select(KnowledgeStatementTriplet))
        triplets = triplet_rows.scalars().all()
        assert len(triplets) == 1

        builder = KnowledgeContextBuilder(
            session,
            scope,
            entity_repository=entity_repo,
            statement_repository=KnowledgeStatementRepository(session, scope),
            triplet_repository=KnowledgeStatementTripletRepository(session, scope),
            document_repository=doc_repo,
            resolution_service=KnowledgeEntityResolutionService(
                session,
                scope,
                entity_repository=entity_repo,
            ),
        )

        context_result = await builder.build_context("How does TrackRec integrate with Salesforce?")
        assert context_result.entities, "Expected entities to be resolved"
        assert context_result.statements, "Expected knowledge statements to be generated"
        assert any("INTEGRATES_WITH" in stmt.summary for stmt in context_result.statements)
    finally:
        await session.close()
