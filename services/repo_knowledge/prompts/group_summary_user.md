Prompt version: {prompt_version}
Group id: {group_id}
Group key: {group_key}
Group label: {group_label}
Layer hint: {layer_hint}
Infrastructure seed: {is_infrastructure_seed}
Representative subject ids: {representative_subject_ids}
Dependency neighbor paths: {dependency_neighbor_paths}
Heuristics: {heuristics_json}

Member evidence:
{member_evidence}

Task:
- Treat this group as one sub-repository segment.
- Based on the member evidence, reconstruct the sub-business functional architecture for this segment.
- Abstract each business functional module and describe it as a Mermaid flowchart.
- Use `subgraph` to represent aggregation relationships between modules.
- Node names must use the original file names, object names, or function names from the evidence — do not invent abstract names.
- Edge labels must use descriptive names that explain the relationship.
- Appropriately ignore non-functional code such as logs, monitoring, tests, and auxiliary code, unless they are architecturally important. Deployment-related and architectural design patterns should be considered as supplements.
