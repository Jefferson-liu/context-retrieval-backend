from typing import List, Dict
from langchain_text_splitters import MarkdownHeaderTextSplitter, RecursiveCharacterTextSplitter

class Chunker:
    def __init__(self):
        self.chunk_size = 512
        self.overlap_size = 20
        
    async def chunk_text(self, content: str, filename: str = "") -> List[Dict[str, str]]:
        """
        Chunk general documents by paragraphs and semantic boundaries
        """
        headers_to_split_on = [
            ("#", "header 1"),
            ("##", "header 2"),
            ("###", "header 3"),
        ]
        md_splitter = MarkdownHeaderTextSplitter(headers_to_split_on)
        text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=self.chunk_size,
            chunk_overlap=self.overlap_size
        )
        
        sections = md_splitter.split_text(content)
        
        for section in sections:
            section.metadata["source"] = filename

        chunks = await text_splitter.atransform_documents(sections)
        
        results = []
        for chunk in chunks:
            results.append({
                "content": chunk.page_content,
                "source": chunk.metadata.get("source", ""),
                "metadata": {k: v for k, v in chunk.metadata.items() if k != "source"}
            })
        return results