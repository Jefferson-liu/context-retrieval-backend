from __future__ import annotations

import argparse
import asyncio
import logging
from typing import Optional

from sqlalchemy import select, text

from config import settings
from infrastructure.context import ContextScope
from infrastructure.database.database import SessionLocal
from infrastructure.database.models.documents import Document
from langchain_anthropic import ChatAnthropic
from services.knowledge import KnowledgeGraphService

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")


async def _refresh(document_id: int, *, user_id: Optional[str]) -> None:
    async with SessionLocal() as session:
        result = await session.execute(select(Document).where(Document.id == document_id))
        document = result.scalar_one_or_none()
        if not document:
            logger.error("Document %s was not found", document_id)
            print("Document %s was not found" % document_id)
            return

        tenant_id = document.tenant_id
        project_id = document.project_id
        effective_user = user_id or document.created_by_user_id or "system"

        await session.execute(
            text("SELECT set_app_context(:tenant_id, :project_ids)"),
            {"tenant_id": tenant_id, "project_ids": str(project_id)},
        )

        scope = ContextScope(
            tenant_id=tenant_id,
            project_ids=[project_id],
            user_id=effective_user,
        )

        llm = ChatAnthropic(
            temperature=0,
            model_name="claude-3-5-haiku-latest",
            api_key=settings.ANTHROPIC_API_KEY,
        )
        service = KnowledgeGraphService(session, scope, llm=llm)
        await service.refresh_document_knowledge(
            document_id=document.id,
            document_name=document.doc_name or f"Document {document.id}",
            document_content=document.content or "",
        )
        await session.commit()
        logger.info(
            "Knowledge graph refreshed for document %s (project %s, tenant %s)",
            document.id,
            project_id,
            tenant_id,
        )
        print(
            "Knowledge graph refreshed for document %s (project %s, tenant %s)"
            % (document.id, project_id, tenant_id)
        )


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Run KnowledgeGraphService.refresh_document_knowledge for a single document."
    )
    parser.add_argument("--document-id", type=int, required=True, help="Target document ID")
    parser.add_argument(
        "--user-id",
        type=str,
        default=None,
        help="Optional user id to seed into the context (defaults to document owner).",
    )
    args = parser.parse_args()

    asyncio.run(_refresh(args.document_id, user_id=args.user_id))


if __name__ == "__main__":
    main()
