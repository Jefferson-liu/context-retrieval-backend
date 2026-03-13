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
- Treat this group as one Repo Manager segment.
- Infer the segment's business role and internal architectural structure.
- Produce a Mermaid flowchart for this segment using file names, object names, or function names that appear in the evidence.
- Ignore tests, logging, and incidental utility detail unless they are architecturally important.
