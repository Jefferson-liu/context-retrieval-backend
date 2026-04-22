from services.repo_knowledge.parsing.tree_sitter_python import TreeSitterPythonParser
from services.repo_knowledge.parsing.tree_sitter_ts_js import TreeSitterTsJsParser


def test_python_parser_best_effort_output() -> None:
    parser = TreeSitterPythonParser()
    source = """
import os
from pkg.util import helper

class A(Base):
    def run(self):
        helper()
"""
    graph = parser.parse(file_path="pkg/mod.py", source_text=source)

    unavailable = [
        item.message
        for item in graph.diagnostics
        if "not installed" in item.message.lower() or "unavailable" in item.message.lower()
    ]
    assert not unavailable, f"python parser unavailable: {unavailable}"

    assert any(edge.edge_type == "imports" for edge in graph.edges)
    assert any(symbol.subject_type == "class" for symbol in graph.symbols)
    assert any(symbol.subject_type == "func" for symbol in graph.symbols)


def test_ts_js_parser_best_effort_output() -> None:
    parser = TreeSitterTsJsParser(enabled_languages={"typescript", "javascript"})
    source = """
import { helper } from "./util";
export class Runner extends Base {
  run() { helper(); }
}
"""
    graph = parser.parse(file_path="src/app.ts", source_text=source)

    unavailable = [
        item.message
        for item in graph.diagnostics
        if "not installed" in item.message.lower() or "unavailable" in item.message.lower()
    ]
    assert not unavailable, f"ts/js parser unavailable: {unavailable}"

    assert any(edge.edge_type == "imports" for edge in graph.edges)
    assert any(edge.edge_type == "exports" for edge in graph.edges)
    assert any(symbol.subject_type == "class" for symbol in graph.symbols)
