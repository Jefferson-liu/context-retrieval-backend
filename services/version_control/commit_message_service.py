from __future__ import annotations
from config.settings import COMMIT_MESSAGE_MODEL
from typing import Optional
from infrastructure.ai.model_factory import build_chat_model
from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.prompts import (
    ChatPromptTemplate,
    HumanMessagePromptTemplate,
    SystemMessagePromptTemplate,
)


class CommitMessageService:
    """Generate short, descriptive commit messages for repository updates."""

    def __init__(self) -> None:
        self.llm = build_chat_model(COMMIT_MESSAGE_MODEL)
        self._prompt = ChatPromptTemplate.from_messages(
            [
                SystemMessagePromptTemplate.from_template(
                    "You write concise git commit messages (imperative mood, <= 72 characters). "
                    "Keep only essential nouns/verbs, avoid punctuation at the end, "
                    "and omit trailing periods. Do not include issue references."
                ),
                HumanMessagePromptTemplate.from_template(
                    "Action: {action}\n"
                    "Document name: {doc_name}\n"
                    "{details_block}"
                    "Respond with a single commit message."
                ),
            ]
        )

    async def generate_message(
        self,
        *,
        action: str,
        doc_name: str,
        details: Optional[str] = None,
    ) -> str:
        details_block = ""
        if details:
            details_block = f"Details: {details}\n"

        chain = self._prompt | self.llm
        response = await chain.ainvoke(
            {
                "action": action,
                "doc_name": doc_name or "document",
                "details_block": details_block,
            }
        )

        message = response.content if isinstance(response.content, str) else ""
        return self._sanitize(message) or self._fallback(action, doc_name)

    def _sanitize(self, message: str) -> str:
        cleaned = message.strip().splitlines()[0] if message else ""
        return cleaned[:72]

    def _fallback(self, action: str, doc_name: str) -> str:
        noun = doc_name or "document"
        return f"{action.capitalize()} {noun}"

