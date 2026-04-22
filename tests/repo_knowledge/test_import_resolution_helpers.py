from services.repo_knowledge.import_resolution import python_import_candidates, ts_js_import_candidates


def test_python_import_candidates_absolute_and_relative() -> None:
    absolute = python_import_candidates(current_file="pkg/mod.py", reference="pkg.util.helpers")
    relative = python_import_candidates(current_file="pkg/mod.py", reference=".util")

    assert "pkg/util/helpers.py" in absolute
    assert "pkg/util.py" in relative


def test_ts_js_import_candidates_relative() -> None:
    candidates = ts_js_import_candidates(current_file="src/app/main.ts", reference="./utils")

    assert "src/app/utils.ts" in candidates
    assert "src/app/utils/index.ts" in candidates
