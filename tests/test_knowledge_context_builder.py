import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from datetime import datetime, timezone

from services.knowledge.knowledge_context import KnowledgeContextBuilder


@pytest.fixture
def anyio_backend():
    return "asyncio"

class _Entity:
    def __init__(self, entity_id, name, entity_type, description=None):
        self.id = entity_id
        self.name = name
        self.entity_type = entity_type
        self.description = description


class _Statement:
    def __init__(self, statement_id, document_id, statement_text, valid_at=None, invalid_at=None):
        self.id = statement_id
        self.document_id = document_id
        self.statement = statement_text
        self.statement_type = "FACT"
        self.temporal_type = "STATIC"
        self.valid_at = valid_at
        self.invalid_at = invalid_at
        self.created_at = datetime.now(timezone.utc)
        self.updated_at = self.created_at


class _Triplet:
    def __init__(self, statement_id, subject_id, object_id, predicate, value=None):
        self.statement_id = statement_id
        self.subject_entity_id = subject_id
        self.object_entity_id = object_id
        self.predicate = predicate
        self.value = value


class _Document:
    def __init__(self, doc_id, name):
        self.id = doc_id
        self.doc_name = name


class _FakeResolutionService:
    def __init__(self, responses):
        self.responses = responses
        self.calls = []

    async def resolve(self, query, *, limit=None, min_confidence=None):
        self.calls.append({"query": query, "limit": limit, "min_confidence": min_confidence})
        return self.responses


class _FakeEntityRepository:
    def __init__(self, entities):
        self.entities = {entity.id: entity for entity in entities}

    async def list_entities_by_ids(self, entity_ids):
        return {
            entity_id: self.entities[entity_id]
            for entity_id in entity_ids
            if entity_id in self.entities
        }


class _FakeTripletRepository:
    def __init__(self, triplets):
        self.triplets = triplets

    async def list_triplets_for_entities(self, entity_ids):
        scoped = []
        targets = set(entity_ids)
        for triplet in self.triplets:
            if (
                triplet.subject_entity_id in targets
                or triplet.object_entity_id in targets
            ):
                scoped.append(triplet)
        return scoped


class _FakeStatementRepository:
    def __init__(self, statements):
        self.statements = {str(stmt.id): stmt for stmt in statements}

    async def list_statements_by_ids(self, statement_ids):
        return {
            statement_id: self.statements[statement_id]
            for statement_id in statement_ids
            if statement_id in self.statements
        }


class _FakeDocumentRepository:
    def __init__(self, documents):
        self.documents = {doc.id: doc for doc in documents}

    async def get_documents_by_ids(self, document_ids):
        return {
            doc_id: self.documents[doc_id]
            for doc_id in document_ids
            if doc_id in self.documents
        }


@pytest.mark.anyio
async def test_builder_collects_relationship_statements():
    resolver = _FakeResolutionService(
        [
            EntityCandidate(
                id=1,
                name="TrackRec",
                entity_type="Product",
                description="Applicant tracking platform",
                confidence=0.91,
            )
        ]
    )
    entity_repo = _FakeEntityRepository(
        [
            _Entity(1, "TrackRec", "Product", "Applicant tracking"),
            _Entity(2, "Salesforce", "Integration"),
        ]
    )
    triplets = [
        _Triplet(
            statement_id="stmt-1",
            subject_id=1,
            object_id=2,
            predicate="INTEGRATES_WITH",
            value="Syncs opportunities nightly",
        ),
    ]
    statements = [_Statement("stmt-1", document_id=5, statement_text="TrackRec integrates with Salesforce nightly.")]
    triplet_repo = _FakeTripletRepository(triplets)
    statement_repo = _FakeStatementRepository(statements)
    document_repo = _FakeDocumentRepository([_Document(5, "Integration Guide")])

    builder = KnowledgeContextBuilder(
        db=None,
        context=None,
        resolution_service=resolver,
        entity_repository=entity_repo,
        triplet_repository=triplet_repo,
        statement_repository=statement_repo,
        document_repository=document_repo,
    )

    result = await builder.build_context("How does TrackRec connect to Salesforce?")

    assert len(result.entities) == 1
    assert result.entities[0].name == "TrackRec"
    assert result.statements, "Expected at least one knowledge statement"
    statement = result.statements[0]
    assert statement.doc_name == "Integration Guide"
    assert "INTEGRATES_WITH" in statement.summary

    system_message = result.to_system_message()
    assert "Known product entities" in system_message
    assert "Integration Guide" in system_message


@pytest.mark.anyio
async def test_builder_returns_empty_when_no_entities_match():
    resolver = _FakeResolutionService([])
    entity_repo = _FakeEntityRepository([])
    triplet_repo = _FakeTripletRepository([])
    statement_repo = _FakeStatementRepository([])
    document_repo = _FakeDocumentRepository([])

    builder = KnowledgeContextBuilder(
        db=None,
        context=None,
        resolution_service=resolver,
        entity_repository=entity_repo,
        triplet_repository=triplet_repo,
        statement_repository=statement_repo,
        document_repository=document_repo,
    )

    result = await builder.build_context("Tell me about anything")

    assert result.entities == []
    assert result.statements == []
    assert result.to_system_message() == ""
