from __future__ import annotations

from typing import Optional

from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.prompts import (
    ChatPromptTemplate,
    HumanMessagePromptTemplate,
    SystemMessagePromptTemplate,
)
from pydantic import BaseModel, Field


class ExtractedEntity(BaseModel):
    name: str = Field(..., min_length=1)
    entity_type: str = Field(..., min_length=1)
    description: Optional[str] = None


class ExtractedRelationship(BaseModel):
    source: str = Field(..., min_length=1)
    target: str = Field(..., min_length=1)
    relationship_type: str = Field(..., min_length=1)
    description: Optional[str] = None


class KnowledgeExtractionResult(BaseModel):
    entities: list[ExtractedEntity] = Field(default_factory=list)
    relationships: list[ExtractedRelationship] = Field(default_factory=list)


class KnowledgeExtractor:
    """LLM-backed helper for identifying entities and relationships in documents."""

    def __init__(self, llm: BaseChatModel) -> None:
        self.llm = llm
        self._prompt = ChatPromptTemplate.from_messages([
            SystemMessagePromptTemplate.from_template(
                "You are an expert knowledge-graph extractor. "
                "Read the provided document and identify named entities and the relationships between them. "
                "Classify each entity with a concise type (e.g., Person, Product, Organization, Concept) and "
                "summarize with short descriptions. "
                "Only return information that is explicitly supported by the document."
            ),
            HumanMessagePromptTemplate.from_template(
                "Document name: {document_name}\n"
                "Document content:\n{document_content}\n\n"
                "Respond strictly as JSON matching this schema:\n"
                "{{\n"
                '  "entities": [{{"name": string, "entity_type": string, "description": string?}}],\n'
                '  "relationships": [{{"source": string, "target": string, "relationship_type": string, "description": string?}}]\n'
                "}}\n"
                "The `source` and `target` values must reference entity names returned in `entities`."
            ),
        ])

    async def extract(
        self,
        *,
        document_name: str,
        document_content: str,
    ) -> KnowledgeExtractionResult:
        chain = self._prompt | self.llm.with_structured_output(KnowledgeExtractionResult)
        return await chain.ainvoke(
            {"document_name": document_name or "Document", "document_content": document_content}
        )
