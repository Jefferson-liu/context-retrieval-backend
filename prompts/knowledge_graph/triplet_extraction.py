from typing import Dict, Optional

from langchain_core.prompts import ChatPromptTemplate

from .predicate_definitions import PREDICATE_DEFINITIONS


def render_predicate_instructions(predicate_instructions: Optional[Dict[str, str]]) -> str:
    """
    Render the optional predicate_instructions dict into the instruction block.
    If none are provided, returns an empty string.
    """
    if not predicate_instructions:
        return ""
    lines = [
        "-------------------------------------------------------------------------",
        "Predicate Instructions:",
        "Please try to stick to the following predicates, do not deviate unless you can't find a relevant definition.",
    ]
    for pred, instruction in predicate_instructions.items():
        lines.append(f"- {pred}: {instruction}")
    return "\n".join(lines)


triplet_extraction_prompt = ChatPromptTemplate.from_template(
    """
You are an information-extraction assistant.

**Task:** Given a statement, follow the steps below and produce structured entities and triplets.

**Guidelines**
First, NER:
- Identify the entities in the statement, their types, and concise, context-independent descriptions.
- Avoid copying long quotes from the text.
- Do not include calendar dates or temporal expressions in any field.
- Extract numeric values as `_Numeric_` entities where the name is the unit (e.g., `GBP`) and `numeric_value` is the quantity.

Second, Triplet extraction:
- Identify the subject entity (the actor) and the object entity (the target) for each relation.
- Choose predicates that reflect the relationship (e.g., `WORKS_AT`, `BELIEVES`). Prefer definitions from the schema if provided.
- Extract a triplet for every predicate expressed in the statement.
- Exclude temporal expressions from every field.
- Continue until all relevant predicates are captured.



===Examples===
Example 1 Statement: "The ProfilePage displays a completion banner when the candidate has fewer than three complete experiences."
Example 1 Output: {{
  "triplets": [
    {{
      "subject_name": "ProfilePage",
      "subject_id": 0,
      "predicate": "DISPLAYS",
      "object_name": "completion banner",
      "object_id": 1,
      "value": null
    }}
  ],
  "entities": [
    {{
      "entity_idx": 0,
      "name": "ProfilePage",
      "type": "UI Page",
      "description": "Candidate-facing profile page in the product"
    }},
    {{
      "entity_idx": 1,
      "name": "completion banner",
      "type": "UI Component",
      "description": "Guidance banner that nudges candidates to complete their profile"
    }},
    {{
      "entity_idx": 2,
      "name": "count",
      "type": "Numeric",
      "description": "Numeric value representing the minimum number of complete experiences",
      "numeric_value": 3
    }}
  ]
}}

Example 2 Statement: "The matching engine recommends up to 5 jobs to each candidate."
Example 2 Output: {{
  "triplets": [
    {{
      "subject_name": "matching engine",
      "subject_id": 0,
      "predicate": "RECOMMENDS",
      "object_name": "jobs",
      "object_id": 1,
      "value": "up to 5"
    }}
  ],
  "entities": [
    {{
      "entity_idx": 0,
      "name": "matching engine",
      "type": "Service",
      "description": "Backend service that recommends jobs to candidates"
    }},
    {{
      "entity_idx": 1,
      "name": "jobs",
      "type": "Object",
      "description": "Open roles that candidates can apply to"
    }},
    {{
      "entity_idx": 2,
      "name": "count",
      "type": "Numeric",
      "description": "Numeric value representing the number of jobs recommended",
      "numeric_value": 5
    }}
  ]
}}

Example 3 Statement: "Olga is the designer at TrackRec."
Example 3 Output: {{
  "triplets": [
    {{
      "subject_name": "Olga",
      "subject_id": 0,
      "predicate": "HOLDS_ROLE",
      "object_name": "Designer",
      "object_id": 1,
      "value": null
    }},
    {{
      "subject_name": "Olga",
      "subject_id": 0,
      "predicate": "PART_OF",
      "object_name": "TrackRec",
      "object_id": 2,
      "value": null
    }}
  ],
  "entities": [
    {{
      "entity_idx": 0,
      "name": "Olga",
      "type": "Person",
      "description": "Designer working on the TrackRec product"
    }},
    {{
      "entity_idx": 1,
      "name": "Designer",
      "type": "Role",
      "description": "Product design role in the company"
    }},
    {{
      "entity_idx": 2,
      "name": "TrackRec",
      "type": "Organization",
      "description": "Recruitment platform and agency building its own product"
    }}
  ]
}}

Example 4 Statement: "The product team discussed several ideas during the weekly planning meeting."
Example 4 Output: {{
  "triplets": [],
  "entities": []
}}

Return empty lists if no entities or triplets can be extracted. Respond only with the structured extraction result defined by your tool and include no commentary.

{rendered_predicate_instructions}

**Statement:** "{statement}"
"""
)



def build_triplet_extraction_prompt(statement: str):
    """Return the partialized triplet extraction prompt."""
    return triplet_extraction_prompt.partial(
        statement=statement,
        rendered_predicate_instructions=render_predicate_instructions(PREDICATE_DEFINITIONS),
    )


__all__ = [
    "build_triplet_extraction_prompt",
]
