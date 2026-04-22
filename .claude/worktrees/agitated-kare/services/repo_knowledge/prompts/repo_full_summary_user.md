Prompt version: {prompt_version}
Used tech stack: {tech}
Repository path: {repo_path}

Task:
Write a concise README for this repository so a developer can quickly understand the architecture and organization.

Reference README structure:
1. Project Overview (required)
2. Quick Start (leave blank if insufficient data)
3. Tech Stack and Key Dependencies (optional as available)
4. Project File Structure
5. Core Features Overview
6. Key Entry Points
7. Other Relevant Sections (optional, only if supported by evidence)

Important program entry files and traces:
{entry_points_trace}

Related upstream/downstream repository information:
{related_repo_info}

You can use tool calls to inspect directory structure, file code, reference graph, and file summaries as needed.
Only keep content you are confident about.

Return final output using:
【markdown_start】
markdown content
【markdown_end】
