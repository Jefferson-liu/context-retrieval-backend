import asyncio
from typing import List

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage
from langchain_openai import ChatOpenAI
from langchain_core.language_models.chat_models import BaseChatModel
from sentence_transformers import SentenceTransformer

from config import settings
from infrastructure.utils.prompt_loader import load_prompt

class Embedder:
    def __init__(self, llm: BaseChatModel):
        self.embedding_model = SentenceTransformer('BAAI/llm-embedder')
        self.llm = llm

    async def contextualize_chunk_content(self, chunk_content: str, full_content: str) -> str:
        """Add contextual information to a single chunk for better search retrieval"""
        if chunk_content == full_content:
            return ""

        prompt_parts = load_prompt("contextualize_chunk")
        human_prompt = prompt_parts["user"]
        replacements = {
            "{chunk}": chunk_content,
            "{content}": full_content,
        }
        for placeholder, value in replacements.items():
            human_prompt = human_prompt.replace(placeholder, value)

        messages = [
            SystemMessage(content=prompt_parts["system"]),
            HumanMessage(content=human_prompt),
        ]

        response = await self.llm.ainvoke(messages)

        if isinstance(response, AIMessage):
            content = response.content
            if isinstance(content, list):
                parts: List[str] = []
                for item in content:
                    if isinstance(item, dict):
                        parts.append(item.get("text", ""))
                    elif isinstance(item, str):
                        parts.append(item)
                return "".join(parts).strip()
            if isinstance(content, str):
                return content.strip()
        return str(response)

    async def generate_embedding(self, text: str) -> List[float]:
        """Generate semantic embedding for the given text using SentenceTransformer"""
        loop = asyncio.get_event_loop()
        embedding = await loop.run_in_executor(None, self.embedding_model.encode, text)
        return embedding.tolist()
