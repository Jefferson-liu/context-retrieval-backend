# Agent Customization Technical Spec

## Core Responsibility
Defines workspace-level custom agents that enforce specialized workflows for repository operations.

## Architecture & Data Flow
- Input: User invokes a custom agent from chat.
- Processing: Agent frontmatter scopes tools and discovery behavior; body instructions enforce workflow constraints.
- Output: Structured edits and maintenance actions aligned with repository governance.

## Current Agent(s)
- `.github/agents/codebase-janitor.agent.md`
  - Purpose: cleanup-oriented repository maintenance (stale artifacts/tests), `.gitignore` hygiene, and `.planning` synchronization.
  - Deletion policy: auto-delete low-risk junk artifacts (for example `*.err`, `*.out`) when confidence is high; require confirmation with reasons when ambiguous.
  - Ignore-file policy: prefer root `.gitignore`; only propose nested ignore files for explicit subproject boundaries and ask first.
  - Operational note: low-risk cleanup tranches completed for `*.err`/`*.out`, project-local `__pycache__/` and standard local cache/build artifacts (`.pytest_cache`, `.coverage*`, `htmlcov`, etc.).
  - Reference-based cleanup result: deleted unreferenced top-level temp artifacts (`temp.txt`, `tmp_gemini_react_smoke.py`, `win_dep_check.txt`); retained `tmp_file_summary_diag_report.py` because it is referenced by `.github/prompts/plan-fileSummaryDiagnosticsAndCostReporting.prompt.md`.
  - Tools: `read`, `search`, `edit`, `execute`, `todo`.
  - Invocation: user-invocable via agent picker.

## Integration Points
- `.planning/active-state.md`: read before action, update at task end.
- `.planning/system-context.md`: global constraints and architecture constitution.
- `.planning/nontechnical-info/project-manifest.md`: product-level alignment.
- `.planning/technical-info/*-info.md` and `*-debt.md`: touched-domain documentation and debt tracking.
- `.gitignore`: updated during cleanup passes to prevent recurring junk artifacts.

## Impact Analysis
- If agent instructions are loosened, cleanup may remove important files or generate noisy churn.
- If `.planning` update requirements are removed, maintenance history and handoff quality degrade.
- If tool scope is broadened unnecessarily, agent role focus may drift from janitorial duties.
