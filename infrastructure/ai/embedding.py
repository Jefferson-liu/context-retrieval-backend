from infrastructure.utils.prompt_loader import load_prompt
from typing import List
from infrastructure.external.anthropic_interface import get_anthropic_response
from sentence_transformers import SentenceTransformer

class Embedder:
    def __init__(self):
        self.embedding_model = SentenceTransformer('BAAI/llm-embedder')

    async def contextualize_chunk_content(self, chunk_content: str, full_content: str) -> str:
        """Add contextual information to a single chunk for better search retrieval"""
        prompt = [{"type": "text", "text": load_prompt("contextualize_chunk")}]
        prompt.append({"type": "text", "text": f"Document: {full_content}", "cache_control": "ephemeral"})
        prompt.append({"type": "text", "text": f"Chunk: {chunk_content}"})
        context = await get_anthropic_response(prompt)
        return context, chunk_content

    async def generate_embedding(self, text: str) -> List[float]:
        """Generate semantic embedding for the given text using SentenceTransformer"""
        embedding = self.embedding_model.encode(text)
        return embedding.tolist()
