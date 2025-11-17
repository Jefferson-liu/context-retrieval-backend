from __future__ import annotations

from collections import OrderedDict
from dataclasses import dataclass
from typing import List, Sequence, Tuple

from langchain_core.language_models import BaseChatModel
from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.runnables import Runnable

from schemas import Clause, Source


@dataclass
class SummaryResult:
    text: str
    ordered_sources: OrderedDict[str, Source]
    source_lines: List[str]
    statements_block: str


class ResponseSummarizer:
    """Uses an LLM to collapse clause statements into a concise, cited response."""

    _SOURCE_SNIPPET_LIMIT = 160

    def __init__(
        self,
        llm: BaseChatModel | None = None,
        *,
        chain: Runnable | None = None,
    ) -> None:
        if chain is None:
            if llm is None:
                raise ValueError("Either an LLM or a prepared chain must be provided.")
            chain = self._build_chain(llm)
        self._chain = chain

    async def summarize(self, *, user_query: str, clauses: Sequence[Clause]) -> SummaryResult:
        statements_block, ordered_sources = self._prepare_blocks(clauses)
        if not statements_block:
            return SummaryResult(text="", ordered_sources=ordered_sources, source_lines=[], statements_block="")

        source_lines = self._format_source_lines(ordered_sources)
        payload = {
            "user_query": user_query,
            "statements_block": statements_block,
            "sources_block": "\n".join(source_lines) if source_lines else "None provided",
        }
        summary_text = await self._chain.ainvoke(payload)
        return SummaryResult(
            text=(summary_text or "").strip(),
            ordered_sources=ordered_sources,
            source_lines=source_lines,
            statements_block=statements_block,
        )

    def _build_chain(self, llm: BaseChatModel) -> Runnable:
        prompt = ChatPromptTemplate.from_messages(
            [
                (
                    "system",
                    (
                        "You are a meticulous editor who turns overlapping statements into a concise paragraph.\n"
                        "Always answer the user's question using only the provided statements and sources.\n"
                        "Keep the response under 120 words, remove duplicates, and maintain inline citations "
                        "such as [1] that refer to the source list. Do not invent new citations."
                    ),
                ),
                (
                    "human",
                    (
                        "User question:\n{user_query}\n\n"
                        "Candidate statements (each may include citations):\n{statements_block}\n\n"
                        "Source details:\n{sources_block}\n\n"
                        "Write a single paragraph that answers the question with coherent prose, resolves conflicts, "
                        "and preserves the necessary citations."
                    ),
                ),
            ]
        )
        return prompt | llm | StrOutputParser()

    def _prepare_blocks(self, clauses: Sequence[Clause]) -> Tuple[str, OrderedDict[str, Source]]:
        source_registry: OrderedDict[Tuple[int, int | None], Tuple[str, Source]] = OrderedDict()
        statement_lines: List[str] = []

        for clause in clauses:
            statement = (clause.statement or "").strip()
            if not statement:
                continue

            citation_labels: List[str] = []
            for source in clause.sources:
                key = (source.doc_id, source.chunk_id)
                if key not in source_registry:
                    label = str(len(source_registry) + 1)
                    source_registry[key] = (label, source)
                else:
                    label = source_registry[key][0]
                citation_labels.append(label)

            citation_suffix = ""
            if citation_labels:
                unique_labels = sorted(set(citation_labels), key=citation_labels.index)
                citation_suffix = " " + "".join(f"[{label}]" for label in unique_labels)

            statement_lines.append(f"- {statement}{citation_suffix}")

        ordered_sources: OrderedDict[str, Source] = OrderedDict()
        for label, src in (value for value in source_registry.values()):
            ordered_sources[label] = src
        statements_block = "\n".join(statement_lines)
        return statements_block, ordered_sources

    def _format_source_lines(self, ordered_sources: OrderedDict[str, Source]) -> List[str]:
        lines: List[str] = []
        for label, source in ordered_sources.items():
            chunk_suffix = f", chunk {source.chunk_id}" if source.chunk_id is not None else ""
            snippet = self._shorten_text(source.content or "", limit=self._SOURCE_SNIPPET_LIMIT)
            lines.append(f"[{label}] {source.doc_name}{chunk_suffix} - {snippet}")
        return lines

    @staticmethod
    def _shorten_text(text: str, *, limit: int) -> str:
        collapsed = " ".join(text.split())
        if len(collapsed) <= limit:
            return collapsed
        truncated = collapsed[: limit - 3].rstrip()
        return f"{truncated}..."
