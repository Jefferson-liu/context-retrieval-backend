"""Diagnostic report for file-summary runs.

Groups failures by diagnostic code, error type, and message.
Produces a ranked report with representative file paths.

Usage:
    python -m scripts.file_summary_diag_report
"""

from __future__ import annotations

import asyncio
from collections import defaultdict

from sqlalchemy import desc, func, select

from infrastructure.database import SessionLocal
from infrastructure.models import (
    RepoFileSummaryDiagnosticRecord,
    RepoFileSummaryRunRecord,
    RepoSubjectRecord,
)


async def main() -> None:
    async with SessionLocal() as session:
        # ── Section 1: Affected Runs ──────────────────────────────────

        runs_stmt = (
            select(RepoFileSummaryRunRecord)
            .where(
                (RepoFileSummaryRunRecord.status == "failed")
                | (RepoFileSummaryRunRecord.files_failed > 0)
            )
            .order_by(desc(RepoFileSummaryRunRecord.queued_at))
            .limit(50)
        )
        runs = (await session.execute(runs_stmt)).scalars().all()

        print("=" * 80)
        print("SECTION 1: AFFECTED RUNS (failed or partially failed)")
        print("=" * 80)
        if not runs:
            print("  (no failed or partially-failed runs found)")
        for r in runs:
            duration = ""
            if r.started_at and r.finished_at:
                delta = r.finished_at - r.started_at
                duration = f" duration={delta.total_seconds():.1f}s"
            print(
                f"  run_id={r.id}  status={r.status}  "
                f"seen={r.files_seen} ok={r.files_summarized} failed={r.files_failed}  "
                f"queued={r.queued_at}{duration}"
            )
            if r.error_message:
                print(f"    error: {r.error_message[:200]}")
        print()

        # ── Section 2: Top Failure Reasons ────────────────────────────

        freq_stmt = (
            select(
                RepoFileSummaryDiagnosticRecord.message,
                RepoFileSummaryDiagnosticRecord.details["diagnostic_code"].as_string().label("diagnostic_code"),
                RepoFileSummaryDiagnosticRecord.details["error_type"].as_string().label("error_type"),
                func.count().label("cnt"),
            )
            .group_by(
                RepoFileSummaryDiagnosticRecord.message,
                RepoFileSummaryDiagnosticRecord.details["diagnostic_code"].as_string(),
                RepoFileSummaryDiagnosticRecord.details["error_type"].as_string(),
            )
            .order_by(desc("cnt"))
        )
        freq_rows = (await session.execute(freq_stmt)).all()

        print("=" * 80)
        print("SECTION 2: TOP FAILURE REASONS (ranked by count)")
        print("=" * 80)
        if not freq_rows:
            print("  (no diagnostics found)")
        for rank, (message, diag_code, err_type, cnt) in enumerate(freq_rows, 1):
            print(f"  #{rank}  count={cnt}  code={diag_code}  error_type={err_type}")
            print(f"        message={message}")
        print()

        # ── Section 3: Representative Files ───────────────────────────

        files_stmt = (
            select(
                RepoFileSummaryDiagnosticRecord.file_summary_run_id,
                RepoFileSummaryDiagnosticRecord.message,
                RepoFileSummaryDiagnosticRecord.details,
                RepoFileSummaryDiagnosticRecord.created_at,
                RepoSubjectRecord.subject_path,
            )
            .join(
                RepoSubjectRecord,
                RepoSubjectRecord.id == RepoFileSummaryDiagnosticRecord.subject_id,
            )
            .order_by(desc(RepoFileSummaryDiagnosticRecord.created_at))
            .limit(500)
        )
        file_rows = (await session.execute(files_stmt)).all()

        # Group by (diagnostic_code, error_type) → list of subject_paths
        groups: dict[tuple[str | None, str | None], list[str]] = defaultdict(list)
        for _run_id, _msg, details, _created_at, subject_path in file_rows:
            code = details.get("diagnostic_code") if isinstance(details, dict) else None
            err_type = details.get("error_type") if isinstance(details, dict) else None
            groups[(code, err_type)].append(subject_path)

        print("=" * 80)
        print("SECTION 3: REPRESENTATIVE FILES (up to 5 per failure reason)")
        print("=" * 80)
        if not groups:
            print("  (no diagnostics found)")
        for (code, err_type), paths in groups.items():
            unique = list(dict.fromkeys(paths))  # preserve order, deduplicate
            print(f"  code={code}  error_type={err_type}  total_files={len(paths)}  unique={len(unique)}")
            for p in unique[:5]:
                print(f"    - {p}")
            if len(unique) > 5:
                print(f"    ... and {len(unique) - 5} more")
        print()


if __name__ == "__main__":
    asyncio.run(main())
