Prompt version: {prompt_version}
Used tech stack: {tech}
Repository path: {repo_path}

Task:
Produce a business-logic-focused summary of this repository. The goal is to document **what the software does and how it does it** — not how to set it up.

Required README structure:
1. **Project Overview** (required) — Project name and 2-4 sentences explaining what the project does, who it serves, and the core problem it solves.
2. **Project Structure** — High-level directory layout showing where the key code lives.
3. **Core Features** (required, this is the most important section) — Identify each distinct business feature or subsystem. For EACH feature, create a dedicated subsection with:
   - **Key Files**: List the specific files that implement this feature (with paths).
   - **How It Works**: A detailed explanation of the actual logic — algorithms, scoring formulas, data transformations, decision trees, pipeline stages, matching rules, etc. Do NOT be vague. If there is a scoring engine, explain what factors are weighted and how. If there is a pipeline, describe each stage and what it does to the data.
   - **Data Flow**: Where inputs come from, how they are processed, and what outputs are produced.
4. **Key Entry Points** — The main entry files and API endpoints for the application.
5. **Cross-Cutting Concerns** (optional) — Only if the repo has notable patterns like shared middleware, event systems, or data access layers that span multiple features.

DO NOT include: environment setup, installation instructions, quick start guides, `.env` configuration, `localhost` URLs, dependency install commands, database migration steps, or tech stack/dependency lists.

Use tool calls to inspect directory structure, file code, reference graphs, and file summaries to understand the business logic deeply. Do not guess — only include information verified through inspection.

Return your final output as pure markdown — no wrapper text, no JSON, no commentary. Just the README.
