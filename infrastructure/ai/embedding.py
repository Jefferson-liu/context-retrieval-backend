from infrastructure.utils.prompt_loader import load_prompt
from typing import List
from infrastructure.external.llm_provider import get_llm_provider
from sentence_transformers import SentenceTransformer
import asyncio

class Embedder:
    def __init__(self):
        self.embedding_model = SentenceTransformer('BAAI/llm-embedder')
        self.llm_provider = get_llm_provider()

    async def contextualize_chunk_content(self, chunk_content: str, full_content: str) -> str:
        """Add contextual information to a single chunk for better search retrieval"""
        prompt_text = f"{load_prompt('contextualize_chunk')}\n\nDocument: {full_content}\n\nChunk: {chunk_content}"
        context = await self.llm_provider.get_response(prompt_text)
        return context

    async def generate_embedding(self, text: str) -> List[float]:
        """Generate semantic embedding for the given text using SentenceTransformer"""
        loop = asyncio.get_event_loop()
        embedding = await loop.run_in_executor(None, self.embedding_model.encode, text)
        return embedding.tolist()
