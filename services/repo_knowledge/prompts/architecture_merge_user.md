Prompt version: {prompt_version}

[Repository README]:
{repo_readme_markdown}

[Repository Sub-architecture Descriptions]:
{segment_artifacts}

Task:
- Based on the Repository README and Sub-architecture Descriptions, reconstruct the high-level business functional architecture of the entire code repository.
- Abstract each business functional module and describe it as a Mermaid flowchart.
- Merge the segment-level artifacts into one repo-level Mermaid architecture diagram.
- Preserve the most important execution or dependency relationships between segments.
- Use `subgraph` to represent aggregation relationships between major subsystems.
- Node names must use the original file names, object names, or function names — do not invent abstract names.
- Edge labels must use descriptive names that explain the relationship.
- Keep the diagram readable; prune incidental detail.
