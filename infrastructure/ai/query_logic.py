from os import system
from typing import List
from pydantic import BaseModel
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_core.language_models import BaseChatModel
from langchain_core.messages import BaseMessage, AIMessage, HumanMessage, SystemMessage
from schemas import Source, Clause

class QuerySubquestions(BaseModel):
    subquestions: List[str]
    
class CoverageResult(BaseModel):
    covers_all_subquestions: bool

class QueryReasoner:
    def __init__(self, llm: BaseChatModel):
        self.llm = llm

    async def get_required_subquestions(self, message_history: List[BaseMessage], user_query: str)  -> List[str]:
        system = (
        "You break queries into only the NECESSARY subquestions.\n"
        "If the user's query is already atomic (answerable as a single fact or step), "
        "return the user's query as the only subquestion.\n"
        "Otherwise, return 2 to 6 subquestions, each one sentence and single-aspect."
        )

        prompt = ChatPromptTemplate.from_messages([
        SystemMessage(content=system),
        MessagesPlaceholder("history"),
        HumanMessage(content=(
            "Given the conversation so far and the user's query, output JSON only.\n"
            "Schema: {\"subquestions\": string[]}\n\n"
            f"User query: {user_query}\n\n"
            "Examples:\n"
            "- Input: \"who's the designer at TrackRec?\" → {\"subquestions\": [\"who's the designer at TrackRec?\"]}\n"
            "- Input: \"What are the aspects that make up the business?\" → "
            "{\"subquestions\": [\"What is the product?\", \"Who are the customers?\", "
            "\"What is the revenue model?\", \"What differentiates it?\"]}"
        ))
        ])
        topic_llm = self.llm.with_structured_output(QuerySubquestions)
        chain = prompt | topic_llm
        result: QuerySubquestions = await chain.ainvoke({"history": message_history})
        return result.subquestions

    async def covers_all_subquestions(self, response: str, subquestions: List[str]) -> bool:
        prompt = ChatPromptTemplate.from_messages([
            SystemMessage(content="You are an expert at analyzing responses for topic coverage."),
            HumanMessage(content="Does the following response cover all of these topics? "
             f"Topics: {", ".join(subquestions)}\n\nResponse: {response}")
        ])
        bool_llm = self.llm.with_structured_output(CoverageResult)
        chain = prompt | bool_llm
        result: CoverageResult = await chain.ainvoke({"subquestions": subquestions, "response": response})
        return result.covers_all_subquestions
    
