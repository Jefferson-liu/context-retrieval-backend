# Agent Memory & Planning Protocols

You will use the `.planning/` directory to maintain a persistent state of the project's context, architecture, and technical health. 

**CRITICAL INSTRUCTION:** Before writing any code, you must ingest the relevant files in this folder to understand not just the *syntax* required, but the *purpose* and *impact* of the feature.

**CRITICAL INSTRUCTION:** Your memory is volatile. The file system is permanent. If you don't write it down here, it didn't happen.

**Definition:** Any response that includes code blocks, diffs, file creation/modification instructions, or concrete implementation steps counts as “writing code” and requires full ingestion of the `.planning/` context first.

---

## 📂 Folder Structure & Responsibilities

### 1. 🔴 `active-state.md` (HIGHEST PRIORITY)
**Purpose:** Session persistence and "Handover" notes.
**Location:** Root of `.planning/` folder.
- **When to read:** IMMEDIATELY upon starting a session to see what was left unfinished.
- **When to write:** At the end of every response or before you stop generating code.
- **Required section:** Always keep a `## 🧹 Tech Debt Snapshot (Janitor Queue)` section so cleanup work is visible and actionable.

### 2. 🟡 `system-context.md` (MANDATORY CONTEXT)
**Purpose:** Global architectural decisions, design patterns, and "The Rules of the System."
**Location:** Root of `.planning/` folder.
- **Content:** Tenancy strategies, coding styles (e.g., "Composition over Inheritance"), and global constraints.
- **When to read:** ALWAYS. This is the project's "Constitution."

### 3. `nontechnical-info/`
**Purpose:** Context, Product Goals, useful information.
**Strict Rule:** Do NOT store variable names, specific tech stack versions, or code snippets here.

* **Files to create/maintain:**
    * `project-manifest.md`: The high-level vision, target audience, and primary problem being solved.
    * `{feature-name}-context.md`: For specific epics/features, describe the *user value*, acceptance criteria, and business logic.
* **When to read:** Before starting any new feature to ensure code alignment with goals.

### 4. `technical-info/`
**Purpose:** Implementation details, architecture, and technical health tracking.

For every distinct feature or module, you must maintain these two files:

#### A. `{feature-name}-info.md`
**Purpose:** The "Source of Truth" for how the feature is built.
**Content Requirements:**
* **Architecture:** Diagrams (MermaidJS) or descriptions of data flow.
* **Key Components:** List of primary classes/functions and their responsibilities.
* **Data Models:** Schema definitions and relationships.
* **Integration Points:** How this feature interacts with other parts of the system.
* **Impact Analysis:** Explicitly state what other features might break if this feature is modified.

#### B. `{feature-name}-debt.md`
**Purpose:** Honest tracking of shortcuts, compromises, and future improvements.
**Content Requirements:**
* **Hacks/Workarounds:** Document any temporary code added to meet a deadline.
* **Performance Concerns:** Areas that work now but will fail at scale (O(n^2) loops, un-indexed queries).
* **Refactoring Wishlist:** "If we had 2 more weeks, we would rewrite X to use Y pattern."
* **Missing Tests:** Edge cases that are currently uncovered.

*Note: Any files in the root planning folder that aren't named in this list should be treated as general read-only context.*

---

## 🧠 Cognitive Offloading Protocol

You must treat the `.planning` folder as your external brain. Use this table to decide where to store information:

| **If you think...** | **You must write it to...** |
| :--- | :--- |
| "This is the **Global Vision** or **Target Audience**." | `nontechnical-info/project-manifest.md` |
| "This is a **User Story** or **Requirement** for this feature." | `nontechnical-info/{feature}-context.md` |
| "I should keep this in mind (**System Constraint**)" | `system-context.md` |
| "This is **how** this specific feature works (Tech Spec)." | `technical-info/{feature}-info.md` |
| "I need to fix this code later (Debt)." | `technical-info/{feature}-debt.md` |
| "I am stopping now, but need to resume X." | `active-state.md` |

---

## 🚦 The "Save Game" Protocol

To ensure we never lose track of work, you must maintain `active-state.md` using the following logic:

### A. Start of Session (Resume)
Check `active-state.md`. If the "Status" is `IN_PROGRESS`, you must alert the user before making any decisions. Aim to continue the "Next Steps" defined in that file unless told otherwise.

### B. End of Session (Handoff)
Before you finish your output, you must determine if the task is **COMPLETE** or **IN_PROGRESS**.
* **If IN_PROGRESS:** Update `active-state.md` with:
    1. What was just finished.
    2. What broke (if anything).
    3. The exact next line of code or logic that needs to be written.
    4. A refreshed `## 🧹 Tech Debt Snapshot (Janitor Queue)` section listing newly introduced debt, debt paid down, and deferred cleanup.
* **If COMPLETE:** Clear the specific task details in `active-state.md` and set status to `IDLE`.
* **For both states:** Do not remove the tech-debt snapshot section; keep it current so the Codebase Janitor agent can maintain it.

---

## 🤖 Agent Workflow Rules

### Phase 1: Ingestion (Start of Task)
1. **Check State:** Read `active-state.md`.
2. **Check Constitution:** Read `system-context.md`. (CRITICAL for constraints like Tenancy).
3. **Check Non-Technical:** Read `nontechnical-info/project-manifest.md` to ground yourself in the user's needs.
4. **Check Technical Context:** If the file exists, read `technical-info/{feature}-info.md`.
5. **Check Debt:** Read `technical-info/{feature}-debt.md`. Can you pay down any debt while working on this new task?

### Phase 2: Implementation (During Task)
* If you make an architectural decision (e.g., choosing a specific library or pattern), note it down to be recorded later.
* If you realize a requirement conflicts with the `nontechnical-info`, STOP and ask the user for clarification.

### Phase 3: Documentation (End of Task)
* **Update Info:** If you changed how data flows or added a new component, update `{feature}-info.md`.
* **Log Debt:** If you wrote code that is "messy" or "temporary," you represent a liability to the codebase. You MUST log this in `{feature}-debt.md`.
* **Update Active Debt Snapshot:** Mirror important debt deltas in `active-state.md` under `## 🧹 Tech Debt Snapshot (Janitor Queue)` and reference the canonical `{feature}-debt.md` file.
* **Update README:** If the project README needs to reflect new changes, update it now.

---

## 📝 Template Examples

### Template for `active-state.md`
```markdown
# 🚦 Current Session State

**Status:** [IDLE | IN_PROGRESS | BLOCKED]
**Current Feature:** [e.g., User Authentication / API Rate Limiting]

## ⏳ Context
[Brief summary of what we are trying to achieve right now. e.g., "Implementing the JWT refresh token logic."]

## ✅ Recently Completed
- [x] Created `AuthService` class.
- [x] Defined Pydantic models for Login.

## 🚧 Current Hurdles / WIP
- The database migration for the `tokens` table has not been run yet.
- Need to decide on the expiration time for refresh tokens.

## 🧹 Tech Debt Snapshot (Janitor Queue)
- New debt: None.
- Debt paid down this session: None.
- Deferred cleanup / blockers: None.
- Canonical debt file: `.planning/technical-info/{feature}-debt.md`

## ⏭️ IMMEDIATE NEXT STEPS
1. Run the migration.
2. Write the unit test for `refresh_token()`.
3. Update `{auth}-info.md` with the new schema.

### Template for `system-context.md`
# 🏛️ System Context & Architecture

## Global Design Decisions
- **Tenancy:** Enforce per-tenant + per-product scoping.
- **Future Flexibility:** Keep the option open for "Product as Metadata" schema.

## Coding Patterns
- **Services:** Must not return ORM objects, only Pydantic models.
- **Error Handling:** Use `AppException` base class.

## Project Constraints
- **Database:** Postgres only. No NoSQL.

### Template for `{feature-name}-info.md`

# [Feature Name] Technical Spec

## Core Responsibility
[Brief sentence on what this code actually does]

## Architecture & Data Flow
- Input: [e.g., JSON via API / User Click]
- Processing: [Logic applied]
- Output: [Database State / UI Update]

## Key Files & Functions
- `MainController.py`: Handles validation.
- `Service.py`: Business logic.

## Cross-Feature Dependencies
- Depends on: [Auth Module]
- Used by: [Reporting Module]