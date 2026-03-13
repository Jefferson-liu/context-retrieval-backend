from __future__ import annotations

import logging
from pathlib import Path

logger = logging.getLogger(__name__)


def python_import_candidates(*, current_file: str, reference: str) -> list[str]:
    """Return candidate in-repo file paths for a Python import string."""
    ref = reference.strip()
    if not ref:
        return []

    candidates: list[str] = []
    leading_dots = len(ref) - len(ref.lstrip("."))
    trimmed = ref.lstrip(".")

    if leading_dots > 0:
        base = Path(current_file).parent
        for _ in range(max(leading_dots - 1, 0)):
            base = base.parent
        module_path = base / trimmed.replace(".", "/") if trimmed else base
        candidates.extend(
            [
                module_path.with_suffix(".py").as_posix(),
                (module_path / "__init__.py").as_posix(),
            ]
        )
    else:
        module_parts = trimmed.split(".")
        for idx in range(len(module_parts), 0, -1):
            module = ".".join(module_parts[:idx])
            module_path = Path(module.replace(".", "/"))
            candidates.extend(
                [
                    module_path.with_suffix(".py").as_posix(),
                    (module_path / "__init__.py").as_posix(),
                ]
            )

    output = _normalize_candidates(candidates)
    logger.debug(
        "Python import candidates current_file=%s reference=%s candidate_count=%s",
        current_file,
        reference,
        len(output),
    )
    return output


def ts_js_import_candidates(*, current_file: str, reference: str) -> list[str]:
    """Return candidate in-repo file paths for TS/JS relative import strings."""
    ref = reference.strip().strip('"').strip("'")
    if not ref or not ref.startswith("."):
        return []

    base = (Path(current_file).parent / ref).as_posix()
    base_path = Path(base)

    candidates: list[str] = []
    if base_path.suffix:
        candidates.append(base_path.as_posix())
    else:
        for ext in [".ts", ".tsx", ".js", ".jsx"]:
            candidates.append(base_path.with_suffix(ext).as_posix())
            candidates.append((base_path / f"index{ext}").as_posix())

    output = _normalize_candidates(candidates)
    logger.debug(
        "TS/JS import candidates current_file=%s reference=%s candidate_count=%s",
        current_file,
        reference,
        len(output),
    )
    return output


def _normalize_candidates(candidates: list[str]) -> list[str]:
    unique_candidates: list[str] = []
    seen: set[str] = set()
    for item in candidates:
        norm = Path(item).as_posix().lstrip("./")
        if norm not in seen:
            seen.add(norm)
            unique_candidates.append(norm)
    return unique_candidates
