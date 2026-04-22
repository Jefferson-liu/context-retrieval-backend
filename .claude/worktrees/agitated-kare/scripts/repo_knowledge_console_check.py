from __future__ import annotations

from pathlib import Path
from tempfile import TemporaryDirectory
import sys
import asyncio
from dataclasses import dataclass
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def run() -> int:
    results: list[tuple[str, bool, str]] = []

    def record(name: str, ok: bool, detail: str = "") -> None:
        results.append((name, ok, detail))

    # dependency checks
    try:
        import tree_sitter_language_pack  # type: ignore  # noqa: F401

        record("dep_tree_sitter_language_pack", True, "import ok")
    except Exception as exc:
        record("dep_tree_sitter_language_pack", False, f"exception={exc}")

    try:
        import langchain_text_splitters  # type: ignore  # noqa: F401

        record("dep_langchain_text_splitters", True, "import ok")
    except Exception as exc:
        record("dep_langchain_text_splitters", False, f"exception={exc}")

    try:
        import langchain_google_genai  # type: ignore  # noqa: F401

        record("dep_langchain_google_genai", True, "import ok")
    except Exception as exc:
        record("dep_langchain_google_genai", False, f"exception={exc}")

    # discovery check
    try:
        from services.repo_knowledge.discovery_service import iter_repo_files

        with TemporaryDirectory() as d:
            root = Path(d)
            (root / "src").mkdir()
            (root / "src" / "main.py").write_text("print('ok')", encoding="utf-8")
            (root / "src" / "ignore.txt").write_text("x", encoding="utf-8")
            (root / "node_modules").mkdir()
            (root / "node_modules" / "lib.js").write_text("x", encoding="utf-8")

            files = list(
                iter_repo_files(
                    root_path=root,
                    include_extensions={".py", ".js"},
                    excluded_dirs={"node_modules"},
                    exclude_globs=["src/ignore.*"],
                )
            )
            got = [item.relative_path for item in files]
            expected = ["src/main.py"]
            record("discovery_filters", got == expected, f"got={got}, expected={expected}")
    except Exception as exc:
        record("discovery_filters", False, f"exception={exc}")

    # import-resolution check
    try:
        from services.repo_knowledge.import_resolution import python_import_candidates, ts_js_import_candidates

        abs_candidates = python_import_candidates(current_file="pkg/mod.py", reference="pkg.util.helpers")
        rel_candidates = python_import_candidates(current_file="pkg/mod.py", reference=".util")
        ts_candidates = ts_js_import_candidates(current_file="src/app/main.ts", reference="./utils")

        ok = (
            "pkg/util/helpers.py" in abs_candidates
            and "pkg/util.py" in rel_candidates
            and "src/app/utils.ts" in ts_candidates
        )
        record("import_resolution", ok, f"abs={len(abs_candidates)}, rel={len(rel_candidates)}, ts={len(ts_candidates)}")
    except Exception as exc:
        record("import_resolution", False, f"exception={exc}")

    # parser strict checks
    try:
        from services.repo_knowledge.parsing.tree_sitter_python import TreeSitterPythonParser

        out = TreeSitterPythonParser().parse(
            file_path="pkg/mod.py",
            source_text=(
                "import os\n"
                "from pkg.util import helper\n\n"
                "class A(Base):\n"
                "    def run(self):\n"
                "        helper()\n"
            ),
        )
        unavailable = [
            d.message
            for d in out.diagnostics
            if "not installed" in d.message.lower() or "unavailable" in d.message.lower()
        ]
        ok = bool(out.symbols) and bool(out.edges) and not unavailable
        record("python_parser_strict", ok, f"symbols={len(out.symbols)}, edges={len(out.edges)}, diagnostics={unavailable}")
    except Exception as exc:
        record("python_parser_strict", False, f"exception={exc}")

    try:
        from services.repo_knowledge.parsing.tree_sitter_ts_js import TreeSitterTsJsParser

        out = TreeSitterTsJsParser(enabled_languages={"typescript", "javascript"}).parse(
            file_path="src/app.ts",
            source_text=(
                "import { helper } from './util';\n"
                "export class Runner extends Base {\n"
                "  run() { helper(); }\n"
                "}\n"
            ),
        )
        unavailable = [
            d.message
            for d in out.diagnostics
            if "not installed" in d.message.lower() or "unavailable" in d.message.lower()
        ]
        ok = bool(out.edges) and not unavailable
        record("ts_js_parser_strict", ok, f"symbols={len(out.symbols)}, edges={len(out.edges)}, diagnostics={unavailable}")
    except Exception as exc:
        record("ts_js_parser_strict", False, f"exception={exc}")

    # chunking strict check
    try:
        from services.repo_knowledge.chunking_service import RepoChunkingService

        chunks = RepoChunkingService(chunk_size=80, chunk_overlap=10).chunk_text(
            text="\n".join([f"line {i}" for i in range(120)]),
            extension=".py",
        )
        record("chunking_service", len(chunks) > 1 and all(bool(c) for c in chunks), f"chunks={len(chunks)}")
    except Exception as exc:
        record("chunking_service", False, f"exception={exc}")

    # summary file_summary strict checks
    try:
        from services.repo_knowledge.summarization.file_summarizer import RepoFileSummarizer
        from services.repo_knowledge.summarization.types import SummaryInput

        class FakeChatModel:
            def __init__(self, responses: list[str]) -> None:
                self.responses = list(responses)

            async def ainvoke(self, messages):  # noqa: ANN001
                if not self.responses:
                    raise RuntimeError("No responses left")
                return SimpleNamespace(content=self.responses.pop(0))

        summarizer = RepoFileSummarizer(
            chat_model=FakeChatModel(
                ['{"file_cluster":["a.py"],"overall_summary":"ok","important_relationships":[],"group_function":null}']
            ),  # type: ignore[arg-type]
            prompt_version="v1",
            max_input_chars=1000,
            map_chunk_chars=500,
            retry_count=1,
            timeout_seconds=5,
        )
        result = asyncio.run(
            summarizer.summarize(
                payload=SummaryInput(
                    source_run_id="run-1",
                    subject_id="subject-1",
                    subject_path="a.py",
                    language="python",
                    parse_status="success",
                    chunk_texts=["print('ok')"],
                    neighbors=[],
                )
            )
        )
        record("summary_single_pass", result.output.overall_summary == "ok", f"mode={result.raw_output.get('mode')}")
    except Exception as exc:
        record("summary_single_pass", False, f"exception={exc}")

    try:
        from services.repo_knowledge.summarization.context_assembler import SummaryContextAssembler

        @dataclass
        class _Chunk:
            content: str

        @dataclass
        class _Snapshot:
            parse_status: str

        @dataclass
        class _Subject:
            id: str
            subject_path: str
            language: str | None

        class _FakeChunkRepo:
            async def list_for_subject(self, *, run_id: str, subject_id: str):  # noqa: ANN001
                return [_Chunk("a"), _Chunk("b")]

        class _FakeEdgeRepo:
            async def list_neighbors_for_file(self, *, run_id: str, subject_id: str, limit_each_direction: int):  # noqa: ANN001
                return []

        assembler = SummaryContextAssembler(
            chunk_repo=_FakeChunkRepo(),  # type: ignore[arg-type]
            edge_repo=_FakeEdgeRepo(),  # type: ignore[arg-type]
            neighbor_limit_each_direction=3,
        )
        context = asyncio.run(
            assembler.build(
                source_run_id="run-1",
                snapshot=_Snapshot(parse_status="success"),  # type: ignore[arg-type]
                subject=_Subject(id="subject-1", subject_path="a.py", language="python"),  # type: ignore[arg-type]
            )
        )
        record("summary_context_assembler", context.chunk_texts == ["a", "b"], f"chunks={len(context.chunk_texts)}")
    except Exception as exc:
        record("summary_context_assembler", False, f"exception={exc}")

    # embedding/retrieval helper checks
    try:
        from services.repo_knowledge.embeddings.text_builder import build_file_summary_embedding_text

        summary = SimpleNamespace(
            overall_summary="Handles checkout workflow",
            group_function="Checkout and payment orchestration",
            file_cluster=["services/payment.py"],
            important_relationships=["calls PaymentGateway"],
        )
        subject = SimpleNamespace(subject_path="services/checkout.py", language="python")
        snapshot = SimpleNamespace(parse_status="success")
        payload = build_file_summary_embedding_text(
            summary=summary,  # type: ignore[arg-type]
            subject=subject,  # type: ignore[arg-type]
            snapshot=snapshot,  # type: ignore[arg-type]
        )
        ok = bool(payload.text_for_embedding) and len(payload.text_hash) == 64
        record("embedding_text_builder", ok, f"kind={payload.kind}")
    except Exception as exc:
        record("embedding_text_builder", False, f"exception={exc}")

    try:
        from services.repo_knowledge.retrieval.context_pack_service import _build_repo_brief

        fake_item = SimpleNamespace(
            candidate=SimpleNamespace(
                group_function="Processes billing state transitions",
                overall_summary="Billing service",
                subject_path="services/billing.py",
            )
        )
        brief = _build_repo_brief(items=[fake_item])
        record("context_pack_helpers", "business functions" in brief.lower(), brief)
    except Exception as exc:
        record("context_pack_helpers", False, f"exception={exc}")

    # grouping + segment-architect strict checks
    try:
        from services.repo_knowledge.grouping.hybrid_path_dependency import HybridPathDependencyGrouper
        from services.repo_knowledge.grouping.types import GroupFileEdge, GroupFileNode

        nodes = [
            GroupFileNode(
                subject_id="n1",
                subject_path="services/recommendation/ingest.py",
                language="python",
                overall_summary="ingest",
                group_function=None,
                important_relationships=[],
            ),
            GroupFileNode(
                subject_id="n2",
                subject_path="services/recommendation/rank.py",
                language="python",
                overall_summary="rank",
                group_function=None,
                important_relationships=[],
            ),
            GroupFileNode(
                subject_id="n3",
                subject_path="routers/recommendation/routes.py",
                language="python",
                overall_summary="routes",
                group_function=None,
                important_relationships=[],
            ),
            GroupFileNode(
                subject_id="n4",
                subject_path="services/billing/charge.py",
                language="python",
                overall_summary="charge",
                group_function=None,
                important_relationships=[],
            ),
        ]
        edges = [
            GroupFileEdge(from_subject_id="n1", to_subject_id="n2", edge_type="imports"),
            GroupFileEdge(from_subject_id="n3", to_subject_id="n2", edge_type="imports"),
        ]
        grouper = HybridPathDependencyGrouper(
            path_depth=2,
            merge_min_affinity=0.35,
            max_member_files=60,
            representative_count=3,
        )
        grouped = grouper.build_groups(file_nodes=nodes, file_edges=edges)
        record("grouping_hybrid", len(grouped.groups) == 2, f"groups={len(grouped.groups)} members={grouped.members_seen}")
    except Exception as exc:
        record("grouping_hybrid", False, f"exception={exc}")

    try:
        from services.repo_knowledge.architecture.segment_architect import RepoSegmentArchitect
        from services.repo_knowledge.architecture.types import SegmentMemberEvidence, SegmentArchitectureInput

        class FakeGroupChatModel:
            def __init__(self, responses: list[str]) -> None:
                self.responses = list(responses)

            async def ainvoke(self, messages):  # noqa: ANN001
                if not self.responses:
                    raise RuntimeError("No responses left")
                return SimpleNamespace(content=self.responses.pop(0))

        summarizer = RepoSegmentArchitect(
            chat_model=FakeGroupChatModel(
                [
                    '{"name":"Recommendation feature","overall_summary":"Combines ranking and delivery.",'
                    '"business_purpose":"Delivers personalized recommendations","responsibilities":["Rank candidates"],'
                    '"tags":["recommendation"],"representative_subject_ids":["s1"],"is_infrastructure":false,"confidence":0.8}'
                ]
            ),  # type: ignore[arg-type]
            prompt_version="v1",
            max_input_chars=8000,
            retry_count=1,
            timeout_seconds=5,
        )
        out = asyncio.run(
            summarizer.summarize(
                payload=SegmentArchitectureInput(
                    source_run_id="run-1",
                    source_file_summary_run_id="extract-1",
                    group_id="g1",
                    group_key="services/recommendation",
                    group_label="services/recommendation",
                    layer_hint="service",
                    is_infrastructure_seed=False,
                    heuristics={},
                    dependency_neighbor_paths=["routers/recommendation/routes.py"],
                    representative_subject_ids=["s1"],
                    members=[
                        SegmentMemberEvidence(
                            subject_id="s1",
                            subject_path="services/recommendation/rank.py",
                            language="python",
                            overall_summary="Ranks candidates",
                            group_function=None,
                            important_relationships=[],
                            is_representative=True,
                            rank=1,
                        )
                    ],
                )
            )
        )
        record("segment_architect_schema", bool(out.output.name) and out.output.confidence >= 0.0, out.output.name)
    except Exception as exc:
        record("segment_architect_schema", False, f"exception={exc}")

    print("REPO_KNOWLEDGE_STRICT_CONSOLE_TESTS")
    passed = 0
    for name, ok, detail in results:
        print(f"{'PASS' if ok else 'FAIL'} | {name} | {detail}")
        if ok:
            passed += 1

    total = len(results)
    failed = total - passed
    print(f"SUMMARY | passed={passed} failed={failed} total={total}")
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    raise SystemExit(run())
