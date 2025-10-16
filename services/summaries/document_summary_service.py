from __future__ import annotations

from typing import Iterable, Optional, Sequence, List

from sqlalchemy.ext.asyncio import AsyncSession
from langchain_core.language_models import BaseChatModel
from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, SystemMessage
from infrastructure.context import ContextScope
from infrastructure.database.models.documents import DocumentSummary
from infrastructure.database.repositories.document_summary_repository import DocumentSummaryRepository


class DocumentSummaryService:
    """Coordinates storage concerns for document-level summaries."""

    def __init__(
        self,
        db: AsyncSession,
        context: ContextScope,
        llm: BaseChatModel,
        *,
        document_summary_repository: DocumentSummaryRepository | None = None,
    ):
        self.db = db
        self.context = context
        self.llm = llm
        self.document_summaries = document_summary_repository or DocumentSummaryRepository(db, context)

    async def upsert_summary(
        self,
        *,
        document_id: int,
        document_content: str,
        summary_tokens: Optional[int] = None,
        summary_hash: Optional[str] = None,
        milvus_primary_key: Optional[int] = None,
    ) -> DocumentSummary:
        """Persist the latest document summary snapshot."""

        messages: List[BaseMessage] = [
            SystemMessage(
                content=(
                    "You are a helpful assistant that summarizes document content. "
                    "Provide a concise summary that still captures the key points and ideas. This will be used by product managers to understand the document's content. Format your response as a plain text summary, without any additional commentary."
                )
            ),
            HumanMessage(content=document_content),
        ]
        summary_text = await self._generate_text(messages)

        return await self.document_summaries.upsert_summary(
            document_id=document_id,
            summary_text=summary_text,
            summary_tokens=summary_tokens,
            summary_hash=summary_hash,
            milvus_primary_key=milvus_primary_key,
        )

    async def _generate_text(self, messages: List[BaseMessage]) -> str:
        """Invoke the LLM and normalize the output into a plain string."""
        response = await self.llm.ainvoke(messages)
        if isinstance(response, AIMessage):
            content = response.content
            if isinstance(content, str):
                return content.strip()
            if isinstance(content, list):
                parts: List[str] = []
                for item in content:
                    if isinstance(item, str):
                        parts.append(item)
                    elif isinstance(item, dict):
                        parts.append(item.get("text", ""))
                return "".join(parts).strip()
        return str(response)

    async def get_summary(self, document_id: int) -> Optional[DocumentSummary]:
        """Return the stored summary for a document in the current scope."""
        return await self.document_summaries.get_by_document_id(document_id)

    async def list_summaries(self, document_ids: Iterable[int]) -> Sequence[DocumentSummary]:
        """Return summaries for several documents (used when aggregating to project-level views)."""
        return await self.document_summaries.list_by_document_ids(document_ids)

    async def delete_summary(self, document_id: int) -> bool:
        """Remove the summary associated with a document."""
        return await self.document_summaries.delete_by_document_id(document_id)
