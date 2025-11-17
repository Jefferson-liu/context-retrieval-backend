from __future__ import annotations

import logging
from typing import Any, Optional

from langchain_core.callbacks.base import BaseCallbackHandler
from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.prompts import (
    ChatPromptTemplate,
    HumanMessagePromptTemplate,
    SystemMessagePromptTemplate,
)
from pydantic import BaseModel, Field
from infrastructure.ai.model_factory import build_chat_model
from config.settings import KNOWLEDGE_EXTRACTION_MODEL

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


logger = logging.getLogger(__name__)


def _message_content_to_text(content: Any) -> str:
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts = []
        for item in content:
            if isinstance(item, dict):
                text = item.get("text")
                if text:
                    parts.append(text)
            else:
                parts.append(str(item))
        return "".join(parts)
    if content is None:
        return ""
    return str(content)


class KnowledgeExtractor:
    """LLM-backed helper for identifying entities and relationships in documents."""

    def __init__(self) -> None:
        self.llm = build_chat_model(model_name=KNOWLEDGE_EXTRACTION_MODEL)
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
        normalized_name = document_name or "Document"
        prompt_values = {
            "document_name": document_name or "Document",
            "document_content": document_content,
        }
        prompt_value = self._prompt.invoke(prompt_values)
        messages = prompt_value.to_messages()
        for idx, message in enumerate(messages):
            logger.info(
                "Knowledge extractor prompt message[%d] (%s): %s",
                idx,
                getattr(message, "type", message.__class__.__name__),
                _message_content_to_text(getattr(message, "content", "")),
            )

        chain = self._prompt | self.llm.with_structured_output(KnowledgeExtractionResult)
        logger.info(
            "Invoking knowledge extractor LLM model %s",
            self.llm.__class__.__name__,
        )
        return await chain.ainvoke(prompt_values)