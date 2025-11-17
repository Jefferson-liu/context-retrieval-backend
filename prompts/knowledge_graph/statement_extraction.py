from langchain_core.prompts import ChatPromptTemplate

from .definitions import LABEL_DEFINITIONS


def _escape_value(value: str) -> str:
    if value is None:
        return ""
    return value.replace("{", "{{").replace("}", "}}")


def render_inputs(inputs: dict) -> str:
    if not inputs:
        return ""
    return "\n".join(f"- {k}: {_escape_value(str(v))}" for k, v in inputs.items())


def tidy(name: str) -> str:
    return name.replace("_", " ")


def render_definitions(defs: dict) -> str:
    if not defs:
        return ""
    out = []
    for section_key, section_dict in defs.items():
        out.append(f"==== {tidy(section_key).upper()} DEFINITIONS & GUIDANCE ====")
        for idx, (category, details) in enumerate(section_dict.items(), start=1):
            definition = details.get("definition", "")
            out.append(f"{idx}. {category}\n- Definition: {definition}")
    return "\n".join(out)


definitions = render_definitions(LABEL_DEFINITIONS)
_BASE_PROMPT = ChatPromptTemplate.from_template(
    """
You are an expert Product Manager and information-extraction assistant.
===Tasks===
1. Identify and extract atomic declarative statements from the chunk given the extraction guidelines
2. Label these (1) as Fact, Opinion, or Prediction and (2) temporally as Static or Dynamic

===Extraction Guidelines===
- Structure statements to clearly show subject-predicate-object relationships
- Each statement should express a single, complete relationship
- Avoid complex or compound predicates
- Must be understandable without external context
- Resolve co-references and pronouns (e.g., "your nearest competitor" → "main_entity's nearest competitor")
- Resolve abstract references such as "the company" to actual entity names
- Expand abbreviations and acronyms to full forms
- Statements must be tied to a single temporal event
- Include explicit dates, times, quantitative qualifiers
- Break statements that contain multiple temporal events
- Extract both static and dynamic versions when described

===Example===
Example Chunk:
## US012: Signup Funnel Experiment Dashboard

**As a** product manager at a B2B SaaS startup
**I want** a dashboard that tracks experiment performance across the signup funnel
**So that** I can quickly see which variants drive more activations and where drop-offs happen

Example Statements:
1. A product manager at a B2B SaaS startup wants a dashboard that tracks experiment performance across the signup funnel. (FACT, STATIC)
2. Multiple signup variants are live across marketing and product surfaces. (FACT, DYNAMIC)
3. Clicking a specific experiment row shows the breakdown of control versus variant performance over time. (FACT, DYNAMIC)
4. The experiment detail view shows confidence intervals, sample sizes, and current experiment status. (FACT, STATIC)
5. Product managers must be able to add and edit a free-text note on the experiment detail view. (FACT, STATIC)

Return an empty list if no statements exist. Otherwise respond using the structured output schema provided by your tool and include no extra commentary.

===Inputs===
{inputs}

===Definitions & Guidance===
{definitions}


"""
)

statement_extraction_prompt = _BASE_PROMPT.partial(definitions=definitions)


def build_statement_extraction_prompt(inputs: dict):
    """Return a prepared statement extraction prompt with rendered inputs. Inputs will be chunks and optional metadata"""
    return statement_extraction_prompt.partial(inputs=render_inputs(inputs))


__all__ = [
    "build_statement_extraction_prompt",
]
