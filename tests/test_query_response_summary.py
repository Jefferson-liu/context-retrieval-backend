import pytest

from schemas import Clause, Source
from services.queries.response_summarizer import ResponseSummarizer


class _FakeChain:
    def __init__(self, response: str) -> None:
        self.response = response
        self.last_input = None

    async def ainvoke(self, payload):
        self.last_input = payload
        return self.response


@pytest.mark.anyio
async def test_response_summarizer_formats_statements_and_sources():
    fake_chain = _FakeChain("Condensed answer [1][2]")
    summarizer = ResponseSummarizer(chain=fake_chain)

    clauses = [
        Clause(
            statement="The onboarding flow now supports SSO authentication.",
            sources=[
                Source(
                    doc_id=1,
                    chunk_id=10,
                    content="Onboarding supports SSO via Okta.",
                    doc_name="Release Notes",
                )
            ],
        ),
        Clause(
            statement="Customers also receive contextual tips inside the dashboard.",
            sources=[
                Source(
                    doc_id=2,
                    chunk_id=4,
                    content="Dashboard shows contextual tips based on activity.",
                    doc_name="Product Brief",
                )
            ],
        ),
    ]

    result = await summarizer.summarize(user_query="What changed?", clauses=clauses)

    assert result.text == "Condensed answer [1][2]"
    assert fake_chain.last_input["user_query"] == "What changed?"
    assert "- The onboarding flow now supports SSO authentication. [1]" in fake_chain.last_input["statements_block"]
    assert "- Customers also receive contextual tips inside the dashboard. [2]" in fake_chain.last_input["statements_block"]
    assert result.source_lines[0].startswith("[1] Release Notes, chunk 10")
    assert result.source_lines[1].startswith("[2] Product Brief, chunk 4")


@pytest.mark.anyio
async def test_response_summarizer_reuses_citations_for_duplicates():
    fake_chain = _FakeChain("Usage grew materially [1]")
    summarizer = ResponseSummarizer(chain=fake_chain)

    shared_source = Source(
        doc_id=3,
        chunk_id=None,
        content="Usage spiked by 45% in Q2.",
        doc_name="Metrics Report",
    )
    clauses = [
        Clause(statement="Usage spiked by 45% quarter over quarter.", sources=[shared_source]),
        Clause(statement="Usage spiked by 45% in Q2.", sources=[shared_source]),
    ]

    result = await summarizer.summarize(user_query="Summarize usage.", clauses=clauses)

    statements_block = fake_chain.last_input["statements_block"]
    assert statements_block.count("[1]") == 2
    assert len(result.ordered_sources) == 1
    assert result.source_lines[0].startswith("[1] Metrics Report")
