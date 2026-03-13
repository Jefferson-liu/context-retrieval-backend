from __future__ import annotations

import asyncio
import json

from langchain_core.messages import HumanMessage, SystemMessage

from config.settings import Settings
from services.repo_knowledge.prompt_loader import load_prompt, render_prompt
from services.repo_knowledge.retrieval.types import ContextCandidate, RerankResult

BUSINESS_RERANKER_SYSTEM_PROMPT = load_prompt("rerank_business_logic_system")


class BusinessLogicRerankerError(Exception):
    """Raised when the business-logic reranker cannot be constructed or executed."""


class BusinessLogicReranker:
    """Gemini-powered reranker that prioritizes business-logic relevance."""

    def __init__(
        self,
        *,
        chat_model: object,
        timeout_seconds: int,
        max_candidates: int,
    ) -> None:
        self.chat_model = chat_model
        self.timeout_seconds = max(5, timeout_seconds)
        self.max_candidates = max(1, max_candidates)

    async def rerank(self, *, query: str, candidates: list[ContextCandidate]) -> list[RerankResult]:
        if not candidates:
            return []

        limited = candidates[: self.max_candidates]
        payload = [
            {
                "subject_id": item.subject_id,
                "subject_path": item.subject_path,
                "language": item.language,
                "overall_summary": item.overall_summary,
                "group_function": item.group_function,
                "important_relationships": item.important_relationships,
                "similarity_score": item.similarity_score,
            }
            for item in limited
        ]

        user_prompt = render_prompt(
            "rerank_business_logic_user",
            query=query,
            candidates_json=json.dumps(payload, ensure_ascii=True),
        )

        response = await self._invoke_messages(
            messages=[
                SystemMessage(content=BUSINESS_RERANKER_SYSTEM_PROMPT),
                HumanMessage(content=user_prompt),
            ]
        )
        raw_text = self._response_to_text(response)
        parsed = _extract_json(raw_text)
        items = parsed.get("items")
        if not isinstance(items, list):
            raise BusinessLogicRerankerError("Reranker response missing items list")

        by_subject: dict[str, RerankResult] = {}
        for row in items:
            if not isinstance(row, dict):
                continue
            subject_id = row.get("subject_id")
            if not isinstance(subject_id, str) or not subject_id:
                continue
            raw_score = row.get("score")
            try:
                score = float(raw_score)
            except (TypeError, ValueError):
                score = 0.0
            score = max(0.0, min(score, 1.0))
            reason = row.get("reason")
            by_subject[subject_id] = RerankResult(
                subject_id=subject_id,
                rerank_score=score,
                reason=reason if isinstance(reason, str) else None,
            )

        results: list[RerankResult] = []
        for item in limited:
            result = by_subject.get(item.subject_id)
            if result is None:
                result = RerankResult(
                    subject_id=item.subject_id,
                    rerank_score=item.similarity_score,
                    reason="missing from reranker output; using similarity",
                )
            results.append(result)
        return results

    async def _invoke_messages(self, *, messages: list) -> object:
        if hasattr(self.chat_model, "ainvoke"):
            return await asyncio.wait_for(
                self.chat_model.ainvoke(messages),  # type: ignore[attr-defined]
                timeout=self.timeout_seconds,
            )
        loop = asyncio.get_running_loop()
        return await asyncio.wait_for(
            loop.run_in_executor(None, lambda: self.chat_model.invoke(messages)),  # type: ignore[attr-defined]
            timeout=self.timeout_seconds,
        )

    @staticmethod
    def _response_to_text(response: object) -> str:
        content = getattr(response, "content", None)
        if isinstance(content, str):
            return content
        if isinstance(content, list):
            parts: list[str] = []
            for item in content:
                if isinstance(item, str):
                    parts.append(item)
                elif isinstance(item, dict):
                    text = item.get("text")
                    if isinstance(text, str):
                        parts.append(text)
            return "\n".join(parts).strip()
        return str(response)


def create_business_logic_reranker(*, settings: Settings) -> BusinessLogicReranker:
    """Build the Gemini reranker used by repository context-pack retrieval."""
    if not settings.GEMINI_API_KEY:
        raise BusinessLogicRerankerError("GEMINI_API_KEY is not configured")

    try:
        from langchain_google_genai import ChatGoogleGenerativeAI
    except ImportError as exc:  # pragma: no cover - optional dependency
        raise BusinessLogicRerankerError("langchain-google-genai is required for reranking") from exc

    chat_model = ChatGoogleGenerativeAI(
        google_api_key=settings.GEMINI_API_KEY,
        model=settings.REPO_CONTEXT_RERANK_MODEL_NAME,
        temperature=0.0,
        timeout=settings.REPO_CONTEXT_RERANK_TIMEOUT_SECONDS,
    )
    return BusinessLogicReranker(
        chat_model=chat_model,
        timeout_seconds=settings.REPO_CONTEXT_RERANK_TIMEOUT_SECONDS,
        max_candidates=settings.REPO_CONTEXT_RERANK_MAX_CANDIDATES,
    )


def _extract_json(raw: str) -> dict:
    candidate = raw.strip()
    if candidate.startswith("```"):
        candidate = candidate.strip("`")
        if candidate.lower().startswith("json"):
            candidate = candidate[4:].strip()
    start = candidate.find("{")
    end = candidate.rfind("}")
    if start < 0 or end < 0 or end <= start:
        raise BusinessLogicRerankerError("Reranker output does not contain a JSON object")
    try:
        payload = json.loads(candidate[start : end + 1])
    except json.JSONDecodeError as exc:
        raise BusinessLogicRerankerError(f"Reranker output is not valid JSON: {exc}") from exc
    if not isinstance(payload, dict):
        raise BusinessLogicRerankerError("Reranker output JSON root must be an object")
    return payload
