import json
from typing import Any, List

from langchain_core.language_models import BaseChatModel
from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, SystemMessage
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from pydantic import BaseModel, ValidationError


class QuerySubquestions(BaseModel):
    subquestions: List[str]


class CoverageResult(BaseModel):
    covers_all_subquestions: bool


class SubquestionDecomposer:
    def __init__(self, llm: BaseChatModel):
        self.llm = llm

    async def get_required_subquestions(
        self,
        message_history: List[BaseMessage],
        user_query: str,
    ) -> List[str]:
        system_prompt = (
            "You are an expert at generating queries for a vector search system.\n"
            "You break queries into only the NECESSARY subqueries.\n"
            "If the user's query is already atomic (answerable as a single fact or step), "
            "return the user's query as the only subquery.\n"
            "Vector search works best when matching relevant words, so avoid overly broad or vague subqueries.\n"
            "Otherwise, return 2 to 6 subquestions, each one sentence and single-aspect."
        )

        prompt = ChatPromptTemplate.from_messages(
            [
                SystemMessage(content=system_prompt),
                MessagesPlaceholder("history"),
                HumanMessage(
                    content=(
                        "Given the conversation so far and the user's query, output JSON only.\n"
                        "Schema: {\"subquestions\": string[]}\n\n"
                        f"User query: {user_query}\n\n"
                        "Examples:\n"
                        "- Input: \"who's the designer at TrackRec?\" -> {\"subquestions\": [\"designer at TrackRec\"]}\n"
                        "- Input: \"What are the aspects that make up the business of TrackRec?\" -> "
                        "{\"subquestions\": [\"TrackRec product\", \"TrackRec customers\", "
                        "\"TrackRec revenue model\", \"Business advantages\"]}\n"
                        "- Input: \"Who works at TrackRec?\" -> "
                        "{\"subquestions\": [\"TrackRec employees\", \"TrackRec roles\", "
                        "\"TrackRec team structure\", \"TrackRec leadership\"]}"
                    )
                ),
            ]
        )

        chain = prompt | self.llm
        raw_response = await chain.ainvoke({"history": message_history})
        response_text = self._coerce_to_text(raw_response)
        return self._parse_subquestions(response_text, user_query)

    async def covers_all_subquestions(self, response: str, subquestions: List[str]) -> bool:
        prompt = ChatPromptTemplate.from_messages(
            [
                SystemMessage(content="You are an expert at analyzing responses for topic coverage."),
                HumanMessage(
                    content=(
                        "Does the following response cover all of these topics? "
                        f"Topics: {', '.join(subquestions)}\n\nResponse: {response}"
                    )
                ),
            ]
        )
        bool_llm = self.llm.with_structured_output(CoverageResult)
        chain = prompt | bool_llm
        result: CoverageResult = await chain.ainvoke({"subquestions": subquestions, "response": response})
        return result.covers_all_subquestions

    def _coerce_to_text(self, raw: Any) -> str:
        if isinstance(raw, tuple) and raw:
            raw = raw[0]

        if isinstance(raw, AIMessage):
            content = raw.content
            if isinstance(content, str):
                return content
            if isinstance(content, list):
                parts: List[str] = []
                for item in content:
                    if isinstance(item, str):
                        parts.append(item)
                    elif isinstance(item, dict):
                        parts.append(item.get("text", ""))
                return "".join(parts)
            return str(content)
        if isinstance(raw, BaseMessage):
            return str(raw.content)
        return str(raw)

    def _parse_subquestions(self, text: str, fallback_query: str) -> List[str]:
        cleaned = text.strip().replace("</invoke>", "").replace("</tool_output>", "")
        candidate_payloads: List[str] = []

        brace_start = cleaned.find("{")
        brace_end = cleaned.rfind("}")
        if brace_start != -1 and brace_end != -1 and brace_end > brace_start:
            candidate_payloads.append(cleaned[brace_start:brace_end + 1])

        bracket_start = cleaned.find("[")
        bracket_end = cleaned.rfind("]")
        if bracket_start != -1 and bracket_end != -1 and bracket_end > bracket_start:
            candidate_payloads.append(cleaned[bracket_start:bracket_end + 1])

        candidate_payloads.append(cleaned)

        for payload in candidate_payloads:
            try:
                loaded = json.loads(payload)
            except json.JSONDecodeError:
                continue

            if isinstance(loaded, list):
                loaded = {"subquestions": loaded}

            if not isinstance(loaded, dict):
                continue

            try:
                model = QuerySubquestions.model_validate(loaded)
            except ValidationError:
                continue

            normalized = [sq.strip() for sq in model.subquestions if isinstance(sq, str) and sq.strip()]
            if normalized:
                return normalized

        lines = [
            line.strip("- •\t ").strip()
            for line in cleaned.splitlines()
            if line.strip()
        ]
        candidates = [line for line in lines if len(line.split()) > 1]
        if candidates:
            return candidates

        default_query = fallback_query.strip()
        return [default_query] if default_query else []
