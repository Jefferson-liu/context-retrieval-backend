from __future__ import annotations

import os
import re


_WINDOWS_DRIVE_PATH_RE = re.compile(r"^(?P<drive>[A-Za-z]):[\\/](?P<rest>.*)$")


def coerce_local_source_path(source_path: str, *, host_os_name: str | None = None) -> str:
    """Normalize source_path across host OS boundaries.

    On non-Windows hosts, a Windows drive path like
    ``C:\\Users\\name\\repo`` is converted to ``/mnt/c/Users/name/repo``.
    """

    raw = source_path.strip()
    os_name = host_os_name or os.name
    match = _WINDOWS_DRIVE_PATH_RE.match(raw)
    if not match:
        return raw
    if os_name == "nt":
        return raw

    drive = match.group("drive").lower()
    rest = match.group("rest").replace("\\", "/")
    return f"/mnt/{drive}/{rest}"


def repair_repo_run_json_windows_paths(raw_json: str) -> str:
    """Escape odd backslash runs in repo-run JSON path fields.

    This repairs invalid JSON produced by pasting raw Windows paths into
    ``source_path``/``repo_address`` string values.
    """

    repaired = raw_json
    for field_name in ("source_path", "repo_address"):
        repaired = _repair_json_string_field_backslashes(repaired, field_name=field_name)
    return repaired


def _repair_json_string_field_backslashes(payload: str, *, field_name: str) -> str:
    pattern = re.compile(
        rf'("{re.escape(field_name)}"\s*:\s*")(?P<value>(?:[^"\\]|\\.)*)(")',
        flags=re.DOTALL,
    )

    def _replace(match: re.Match[str]) -> str:
        prefix = match.group(1)
        value = match.group("value")
        suffix = match.group(3)
        return f"{prefix}{_normalize_backslash_runs(value)}{suffix}"

    return pattern.sub(_replace, payload, count=1)


def _normalize_backslash_runs(value: str) -> str:
    """Ensure each consecutive backslash run has even length for JSON parsing."""

    output: list[str] = []
    idx = 0
    while idx < len(value):
        if value[idx] != "\\":
            output.append(value[idx])
            idx += 1
            continue

        run_end = idx
        while run_end < len(value) and value[run_end] == "\\":
            run_end += 1
        run_len = run_end - idx
        if run_len % 2 == 1:
            run_len += 1
        output.append("\\" * run_len)
        idx = run_end

    return "".join(output)
