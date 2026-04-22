## Plan: File-Summary Diagnostics & Cost Reporting

**TL;DR:** Build a proper diagnostic script from the existing `tmp_file_summary_diag_report.py` template. Token usage **cannot** be reported today — `usage_metadata` exists on every `AIMessage` in LangGraph state but is discarded before persistence. Minimal fix: extract aggregated tokens from agent state, add a `usage` key to the existing `raw_output` JSON (zero migration), and optionally add run-level rollup columns later.

---

### Section A: "Why file summaries failed" — Diagnostic Script

**Current state:** `tmp_file_summary_diag_report.py` already queries runs + diagnostics but dumps flat text with no grouping. Three known diagnostic codes exist in `_classify_file_summary_failure()` (`services/repo_knowledge/file_summary_service.py`): `thought_signature_missing`, `agent_timeout`, `summary_failed`.

**Steps (Phase 1: single script, you run locally)**

1. **Create `scripts/file_summary_diag_report.py`** — replace the tmp file with a proper script using the `SessionLocal` + async SQLAlchemy pattern:
   - **Query 1 — Run health:** Latest 50 runs filtered to `status='failed'` OR `files_failed > 0`, showing id, status, seen/ok/failed, error_message, timestamps
   - **Query 2 — Failure frequency:** Group diagnostics by `(message, details->diagnostic_code, details->error_type)` ordered by count DESC
   - **Query 3 — Files by run:** Join diagnostics ↔ `repo_subjects` for `subject_path`, limit 500
   - **Output:** Three sections: Affected Runs table, Top Failure Reasons (ranked), Representative Files (up to 5 paths per diagnostic_code+error_type pair)

2. *Depends on 1.* **Run the script** and capture output.

**Relevant files:**
- `tmp_file_summary_diag_report.py` — template
- `infrastructure/models/repo_knowledge.py` — ORM models (`RepoFileSummaryRunRecord`, `RepoFileSummaryDiagnosticRecord`, `RepoSubjectRecord`)
- `infrastructure/repositories/repo_file_summary_diagnostic_repository.py` — join pattern reference

---

### Section B: "Can we report costs today?" — **No**

| Location | What exists | Token/Cost data? |
|---|---|---|
| `repo_file_summary_runs` columns | `model_provider`, `model_name`, `prompt_version` | **None** |
| `repo_file_summaries.raw_output` JSON | `{"mode":"agent","raw_text":"...","tool_trace":[...],"agent":{"message_count":N}}` | **No** — only `message_count` extracted |
| `react_agent_runtime.py` `ReActAgentResult.state` | Full LangGraph state with all `AIMessage` objects | **Available but discarded** — each `AIMessage` has `usage_metadata` with `input_tokens`, `output_tokens`, `total_tokens` |
| `file_summarizer.py` `_invoke_agent()` | Calls `_message_count(state)` | Only counts messages, ignores `usage_metadata` |
| `gemini_react_smoke.out` | Test run output proving Gemini returns usage | `{'input_tokens': 58, 'output_tokens': 89, 'total_tokens': 147, 'input_token_details': {'cache_read': 0}}` |

**Verdict:** The data is generated and present in-memory on every agent run, but systematically discarded at `file_summarizer.py` L579 where only `message_count` is kept.

---

### Section C: Detailed Usage & Cost Tracking

#### What data is available per LangGraph step

Each `AIMessage` in the LangGraph state provides (verified via `gemini_react_smoke.out`):

```python
AIMessage(
    content="I need to examine...",           # Agent reasoning / thought process
    tool_calls=[                               # Tools the model decided to invoke
        {"name": "return_file_code", "args": {...}, "id": "call_abc123", "type": "tool_call"}
    ],
    usage_metadata={                           # ← TOKEN USAGE PER LLM STEP
        "input_tokens": 58,
        "output_tokens": 89,
        "total_tokens": 147,
        "input_token_details": {"cache_read": 0},
        "output_token_details": {"reasoning": 72},
    },
    response_metadata={                        # ← MODEL METADATA
        "finish_reason": "STOP",
        "model_name": "gemini-3-flash-preview",
        "model_provider": "google_genai",
    },
)
```

`ToolMessage` objects have `name`, `tool_call_id`, and `content` (the tool's response) but **no token usage** — tools don't consume LLM tokens directly. The cost of *processing* a tool result is on the *next* `AIMessage` step.

---

**Phase 2: New `repo_file_summary_usage` table + full trace capture (requires migration)**

#### Step 3 — New table: `repo_file_summary_usage`

SQL-queryable aggregate columns for fast analysis, plus a `steps` JSON column with the complete per-step trace.

```
Table: repo_file_summary_usage
─────────────────────────────────────────────────────────────────
PK   id                    String(36)    UUID
FK   file_summary_run_id   String(36)    → repo_file_summary_runs.id  ON DELETE CASCADE
FK   subject_id            String(36)    → repo_subjects.id           ON DELETE CASCADE
     model_provider        String(32)    e.g. "google_genai"
     model_name            String(128)   e.g. "gemini-3-flash-preview"
     status                String(16)    "completed" | "failed" | "skipped"
     error_message         Text          nullable — if agent failed, the error
     ── Aggregate token columns (SQL-queryable) ──
     total_input_tokens    Integer       default=0  sum of all AIMessage input_tokens
     total_output_tokens   Integer       default=0  sum of all AIMessage output_tokens
     total_tokens          Integer       default=0  sum of all AIMessage total_tokens
     cached_input_tokens   Integer       default=0  sum of input_token_details.cache_read
     reasoning_tokens      Integer       default=0  sum of output_token_details.reasoning
     ── Step counts ──
     llm_step_count        Integer       default=0  number of AIMessage steps
     tool_call_count       Integer       default=0  total tool invocations across all steps
     ── Timing ──
     duration_ms           Integer       nullable — wall-clock time for agent invocation
     ── Detailed trace ──
     steps                 JSON          ordered array of every message (see schema below)
     ── Timestamps ──
     created_at            DateTime(tz)  server_default=now
─────────────────────────────────────────────────────────────────
Indexes:
  ix_repo_file_summary_usage_run        (file_summary_run_id)
  ix_repo_file_summary_usage_subject    (subject_id)
```

#### `steps` JSON schema

Every message from the LangGraph state, in order:

```json
[
  {
    "step_index": 0,
    "role": "system",
    "content": "You are a code analysis agent..."
  },
  {
    "step_index": 1,
    "role": "human",
    "content": "Analyze the following file: src/main.py..."
  },
  {
    "step_index": 2,
    "role": "ai",
    "content": "I need to examine the imports and structure. Let me look at the directory.",
    "input_tokens": 1200,
    "output_tokens": 150,
    "total_tokens": 1350,
    "cached_input_tokens": 0,
    "reasoning_tokens": 50,
    "finish_reason": "STOP",
    "model_name": "gemini-3-flash-preview",
    "tool_calls": [
      {
        "id": "call_abc123",
        "name": "return_directory",
        "arguments": {"use_path": "src/"}
      }
    ]
  },
  {
    "step_index": 3,
    "role": "tool",
    "name": "return_directory",
    "tool_call_id": "call_abc123",
    "content_preview": "{\"entries\": [\"main.py\", \"utils.py\", ...]}"
  },
  {
    "step_index": 4,
    "role": "ai",
    "content": "Now I can see the file structure. Let me read the actual code.",
    "input_tokens": 2500,
    "output_tokens": 300,
    "total_tokens": 2800,
    "cached_input_tokens": 500,
    "reasoning_tokens": 0,
    "finish_reason": "STOP",
    "model_name": "gemini-3-flash-preview",
    "tool_calls": [
      {
        "id": "call_def456",
        "name": "return_file_code",
        "arguments": {"use_path": "src/main.py", "start_line": 1, "max_lines": 250}
      }
    ]
  },
  {
    "step_index": 5,
    "role": "tool",
    "name": "return_file_code",
    "tool_call_id": "call_def456",
    "content_preview": "import asyncio\nfrom pathlib import Path\n..."
  },
  {
    "step_index": 6,
    "role": "ai",
    "content": "{\"overall_summary\": \"Entry point for...\", \"file_cluster\": [...], ...}",
    "input_tokens": 5000,
    "output_tokens": 800,
    "total_tokens": 5800,
    "cached_input_tokens": 1000,
    "reasoning_tokens": 200,
    "finish_reason": "STOP",
    "model_name": "gemini-3-flash-preview",
    "tool_calls": []
  }
]
```

**Key properties:**
- AI steps have full `content` (the agent's reasoning/thought process — essential for optimization)
- AI steps have per-step token breakdown: `input_tokens`, `output_tokens`, `cached_input_tokens`, `reasoning_tokens`
- AI steps list their `tool_calls` with name + arguments (the "decision" to call a tool)
- Tool steps have `content_preview` (truncated to 2000 chars to avoid JSON bloat; full result is in the tool itself)
- `content_preview` on tool responses: truncate to avoid multi-MB JSON rows from large file reads

#### Step 4 — New ORM model: `RepoFileSummaryUsageRecord`

In `infrastructure/models/repo_knowledge.py`, following the existing pattern from `RepoFileSummaryDiagnosticRecord`.

#### Step 5 — New repository: `RepoFileSummaryUsageRepository`

In `infrastructure/repositories/repo_file_summary_usage_repository.py`:
- `create(...)` — insert one usage record
- `list_for_run(*, file_summary_run_id, limit, offset)` — paginated list joined with `repo_subjects` for `subject_path`
- `aggregate_for_run(*, file_summary_run_id)` — returns summed token columns + count

#### Step 6 — Trace extraction helper: `extract_full_trace_from_state()` in `react_agent_runtime.py`

New function alongside existing `extract_agent_response_text()`:

```python
def extract_full_trace_from_state(state: dict[str, Any]) -> dict:
    """Extract ordered step trace with per-step token usage from LangGraph state.

    Returns:
        {
            "total_input_tokens": int,
            "total_output_tokens": int,
            "total_tokens": int,
            "cached_input_tokens": int,
            "reasoning_tokens": int,
            "llm_step_count": int,
            "tool_call_count": int,
            "steps": [...]
        }
    """
```

Logic:
- Iterate `state["messages"]` in order
- For each message, check `type` attribute: `"system"`, `"human"`, `"ai"`, `"tool"`
- For `ai` messages:
  - Read `usage_metadata` dict → extract `input_tokens`, `output_tokens`, `total_tokens`, `.input_token_details.cache_read`, `.output_token_details.reasoning`
  - Read `response_metadata` → extract `finish_reason`, `model_name`
  - Read `tool_calls` list → extract `id`, `name`, `arguments` for each
  - Read `content` (use `response_to_text()` for normalization)
  - Accumulate into aggregate totals
- For `tool` messages:
  - Read `name`, `tool_call_id`, `content` (truncate to 2000 chars)
- For `system`/`human`:
  - Read `content` only (no token data on these)

#### Step 7 — Modify `_invoke_agent()` and `summarize()` in `file_summarizer.py`

`_invoke_agent()` changes:
- After calling `invoke_react_agent(...)`, also call `extract_full_trace_from_state(agent_result.state)`
- Time the invocation with `time.perf_counter()` → `duration_ms`
- Return the trace dict alongside existing return values

`summarize()` changes:
- Return the trace dict as part of `SummaryResult` (new field: `usage_trace: dict | None`)
- For `deterministic_empty` mode: `usage_trace = None` (no LLM invocation occurred)

#### Step 8 — Persist usage record in `file_summary_service.py` worker

In `RepoFileSummaryWorker.execute()`, after each successful file summarization:
- Call `usage_repo.create(...)` with the trace data from `SummaryResult.usage_trace`
- `status="completed"`, populate all aggregate + steps columns

On per-file failure (in the `except` block):
- Call `usage_repo.create(...)` with `status="failed"`, `error_message=str(exc)`, and empty/partial trace
- This captures that the attempt happened even if it failed, enabling cost tracking on failures too

#### Step 9 — New API endpoints

In `routers/repo_knowledge_file_summary_router.py`:

```
GET /repo-knowledge/file-summary-runs/{file_summary_run_id}/usage
```
- Query params: `limit` (1-500, default=100), `offset` (≥0), `subject_path_prefix` (optional), `status` (optional: "completed"|"failed"|"skipped")
- Returns paginated list of usage records with `subject_path` from joined `repo_subjects`
- Response includes steps JSON for full trace detail

```
GET /repo-knowledge/file-summary-runs/{file_summary_run_id}/usage/summary
```
- Returns aggregated totals for the entire run: `SUM(total_input_tokens)`, `SUM(total_output_tokens)`, `SUM(total_tokens)`, `SUM(cached_input_tokens)`, `SUM(reasoning_tokens)`, `COUNT(*)`, `AVG(duration_ms)`, breakdown by status

#### Step 10 — Response schemas in `schemas/repo_knowledge_file_summary.py`

```python
class RepoFileSummaryUsageItem(BaseModel):
    file_summary_run_id: str
    subject_id: str
    subject_path: str
    model_provider: str
    model_name: str
    status: str
    error_message: str | None
    total_input_tokens: int
    total_output_tokens: int
    total_tokens: int
    cached_input_tokens: int
    reasoning_tokens: int
    llm_step_count: int
    tool_call_count: int
    duration_ms: int | None
    steps: list[dict]          # Full ordered trace
    created_at: datetime

class RepoFileSummaryUsageListResponse(BaseModel):
    items: list[RepoFileSummaryUsageItem]
    limit: int
    offset: int

class RepoFileSummaryUsageSummaryResponse(BaseModel):
    file_summary_run_id: str
    file_count: int
    completed_count: int
    failed_count: int
    skipped_count: int
    total_input_tokens: int
    total_output_tokens: int
    total_tokens: int
    cached_input_tokens: int
    reasoning_tokens: int
    avg_duration_ms: float | None
    avg_tokens_per_file: float | None
```

---

**Phase 3: Run-Level Rollup columns (optional, requires second migration)**

11. *(Optional)* Add columns to `repo_file_summary_runs`: `total_input_tokens`, `total_output_tokens`, `total_tokens` — increment in worker loop alongside `files_summarized`. Avoids the aggregate query in Phase 2 Step 9's summary endpoint.
12. *(Optional)* Simple pricing dict per `(model_provider, model_name)` to compute `estimated_cost_usd` at run level.

---

### Example analysis queries enabled by Phase 2

```sql
-- Per-run cost summary
SELECT file_summary_run_id,
       COUNT(*) AS file_count,
       SUM(total_input_tokens) AS input_tokens,
       SUM(total_output_tokens) AS output_tokens,
       SUM(total_tokens) AS tokens,
       SUM(cached_input_tokens) AS cached,
       SUM(reasoning_tokens) AS reasoning,
       AVG(duration_ms) AS avg_ms
FROM repo_file_summary_usage
GROUP BY file_summary_run_id;

-- Most expensive files (optimization targets)
SELECT u.subject_id, s.subject_path, u.total_tokens, u.llm_step_count, u.tool_call_count, u.duration_ms
FROM repo_file_summary_usage u
JOIN repo_subjects s ON s.id = u.subject_id
WHERE u.file_summary_run_id = '<run_id>'
ORDER BY u.total_tokens DESC
LIMIT 20;

-- Tool usage frequency across a run (which tools burn the most steps?)
SELECT tool_call->>'name' AS tool_name, COUNT(*) AS call_count
FROM repo_file_summary_usage u,
     jsonb_array_elements(u.steps) AS step,
     jsonb_array_elements(step->'tool_calls') AS tool_call
WHERE u.file_summary_run_id = '<run_id>'
  AND step->>'role' = 'ai'
GROUP BY tool_call->>'name'
ORDER BY call_count DESC;

-- Cache hit effectiveness
SELECT file_summary_run_id,
       SUM(cached_input_tokens) AS cached,
       SUM(total_input_tokens) AS total_input,
       ROUND(100.0 * SUM(cached_input_tokens) / NULLIF(SUM(total_input_tokens), 0), 1) AS cache_hit_pct
FROM repo_file_summary_usage
GROUP BY file_summary_run_id;

-- Failed file costs (money spent on failures)
SELECT file_summary_run_id, COUNT(*) AS failed_files, SUM(total_tokens) AS wasted_tokens
FROM repo_file_summary_usage
WHERE status = 'failed'
GROUP BY file_summary_run_id;
```

---

### Verification

1. **Diagnostic script:** Run `scripts/file_summary_diag_report.py` → ranked failure report with run IDs, counts, grouped paths
2. **Usage table:** After Phase 2, run file-summary on a small repo (2-3 files), then:
   - Query `SELECT subject_id, total_input_tokens, total_output_tokens, llm_step_count, tool_call_count FROM repo_file_summary_usage WHERE file_summary_run_id = '<id>'` → confirm non-zero values
   - Query `SELECT steps FROM repo_file_summary_usage LIMIT 1` → confirm full ordered trace with per-step tokens and agent reasoning
3. **API:** `GET /repo-knowledge/file-summary-runs/<id>/usage` → returns list with steps. `GET .../usage/summary` → returns aggregate totals.
4. **Failed files:** Trigger a timeout on a large file, confirm a `status='failed'` row is still created with partial trace data.

### Decisions
- **Separate `repo_file_summary_usage` table** — not embedded in `raw_output` JSON. Enables SQL analysis, API access, and independent lifecycle.
- **Aggregate columns + detailed JSON steps** — best of both worlds: fast SQL for dashboards, deep JSON for optimization deep-dives.
- **Tool content truncated to 2000 chars in steps** — prevents JSON bloat from large file reads while preserving enough for debugging.
- **Usage record created on failure too** — captures wasted tokens, essential for cost optimization.
- **Phase 3 (run-level rollup) deferred** — aggregate query on the usage table is fast enough for now.
- **Scope boundary:** This plan covers capture + storage + API. Does not add UI dashboards or alerting.

### Files to create/modify

| File | Action | Phase |
|---|---|---|
| `infrastructure/models/repo_knowledge.py` | Add `RepoFileSummaryUsageRecord` | 2 |
| `infrastructure/repositories/repo_file_summary_usage_repository.py` | **New** — CRUD + aggregation | 2 |
| `services/repo_knowledge/summarization/react_agent_runtime.py` | Add `extract_full_trace_from_state()` | 2 |
| `services/repo_knowledge/summarization/file_summarizer.py` | Modify `_invoke_agent()` + `summarize()` to return trace | 2 |
| `services/repo_knowledge/file_summary_service.py` | Persist usage record in worker loop | 2 |
| `schemas/repo_knowledge_file_summary.py` | Add usage response schemas | 2 |
| `routers/repo_knowledge_file_summary_router.py` | Add `/usage` + `/usage/summary` endpoints | 2 |
| `scripts/file_summary_diag_report.py` | **New** — diagnostic script | 1 |
