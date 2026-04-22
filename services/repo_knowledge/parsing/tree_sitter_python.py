from __future__ import annotations

import logging
from typing import Any

from services.repo_knowledge.parsing.types import (
    ExternalRef,
    ParseDiagnostic,
    ParsedEdge,
    ParsedFileGraph,
    ParsedSymbol,
)

try:
    from tree_sitter_language_pack import get_parser  # type: ignore
except Exception:  # pragma: no cover - optional dependency
    get_parser = None

logger = logging.getLogger(__name__)


class TreeSitterPythonParser:
    """Best-effort Python parser powered by Tree-sitter."""

    def __init__(self) -> None:
        self._parser = None
        self._init_error: str | None = None
        if get_parser is None:
            self._init_error = "tree_sitter_language_pack is not installed"
            logger.warning("Python parser unavailable: %s", self._init_error)
            return
        try:
            self._parser = get_parser("python")
            logger.info("Python tree-sitter parser initialized")
        except Exception as exc:  # pragma: no cover - env-specific
            self._init_error = f"failed to initialize python parser: {exc}"
            logger.warning("Python parser unavailable: %s", self._init_error)

    def parse(self, *, file_path: str, source_text: str) -> ParsedFileGraph:
        graph = ParsedFileGraph()
        if not self._parser:
            graph.diagnostics.append(ParseDiagnostic(message=self._init_error or "python parser unavailable"))
            logger.warning("Python parser parse fallback file=%s reason=%s", file_path, self._init_error)
            return graph

        source_bytes = source_text.encode("utf-8", errors="ignore")
        tree = self._parser.parse(source_bytes)
        root = tree.root_node

        import_aliases: set[str] = set()

        def node_text(node: Any) -> str:
            return source_bytes[node.start_byte : node.end_byte].decode("utf-8", errors="ignore")

        def walk(node: Any):
            yield node
            for child in node.children:
                yield from walk(child)

        def find_identifier_text(node: Any) -> str | None:
            for child in node.children:
                if child.type == "identifier":
                    return node_text(child).strip()
            return None

        def parse_import_nodes() -> None:
            for node in walk(root):
                if node.type not in {"import_statement", "import_from_statement"}:
                    continue
                text = node_text(node).strip()
                line = node.start_point[0] + 1
                col = node.start_point[1] + 1
                if node.type == "import_statement":
                    raw = text.removeprefix("import ").strip()
                    modules = [part.strip() for part in raw.split(",") if part.strip()]
                    for module in modules:
                        alias = module.split(" as ")[-1].strip()
                        import_aliases.add(alias.split(".")[-1])
                        graph.edges.append(
                            ParsedEdge(
                                edge_type="imports",
                                from_symbol_ref=None,
                                to_symbol_ref=None,
                                from_file=file_path,
                                to_file_or_external=module,
                                line=line,
                                column=col,
                                evidence=text,
                            )
                        )
                        graph.external_refs.append(ExternalRef(ref=module, ref_type="module"))
                else:
                    from_part = text.removeprefix("from ")
                    module_name = from_part.split(" import ", 1)[0].strip()
                    imported_raw = from_part.split(" import ", 1)[1] if " import " in from_part else ""
                    imported_items = [item.strip() for item in imported_raw.replace("(", "").replace(")", "").split(",") if item.strip()]
                    if not imported_items:
                        imported_items = ["*"]
                    for item in imported_items:
                        alias = item.split(" as ")[-1].strip()
                        if alias != "*":
                            import_aliases.add(alias)
                        ref = f"{module_name}.{item}" if item != "*" else module_name
                        graph.edges.append(
                            ParsedEdge(
                                edge_type="imports",
                                from_symbol_ref=None,
                                to_symbol_ref=None,
                                from_file=file_path,
                                to_file_or_external=ref,
                                line=line,
                                column=col,
                                evidence=text,
                            )
                        )
                        graph.external_refs.append(ExternalRef(ref=ref, ref_type="module_symbol"))

        def visit(node: Any, scope_stack: list[str]) -> None:
            ntype = node.type
            current_scope = ".".join(scope_stack) if scope_stack else None

            if ntype == "class_definition":
                name = find_identifier_text(node)
                if name:
                    qual = ".".join([*scope_stack, name]) if scope_stack else name
                    graph.symbols.append(
                        ParsedSymbol(
                            subject_type="class",
                            symbol_name=name,
                            symbol_qualname=qual,
                            line=node.start_point[0] + 1,
                            column=node.start_point[1] + 1,
                        )
                    )
                    graph.edges.append(
                        ParsedEdge(
                            edge_type="defines",
                            from_symbol_ref=None,
                            to_symbol_ref=qual,
                            from_file=file_path,
                            to_file_or_external=file_path,
                            line=node.start_point[0] + 1,
                            column=node.start_point[1] + 1,
                            evidence=f"class {name}",
                        )
                    )
                    # inheritance
                    for child in node.children:
                        if child.type == "argument_list":
                            for arg in child.children:
                                if arg.type in {"identifier", "attribute"}:
                                    base_name = node_text(arg).strip()
                                    if not base_name:
                                        continue
                                    graph.edges.append(
                                        ParsedEdge(
                                            edge_type="inherits",
                                            from_symbol_ref=qual,
                                            to_symbol_ref=base_name,
                                            from_file=file_path,
                                            to_file_or_external=base_name,
                                            line=arg.start_point[0] + 1,
                                            column=arg.start_point[1] + 1,
                                            evidence=base_name,
                                        )
                                    )
                                    graph.external_refs.append(ExternalRef(ref=base_name, ref_type="symbol"))
                    scope_stack = [*scope_stack, name]

            if ntype == "function_definition":
                name = find_identifier_text(node)
                if name:
                    qual = ".".join([*scope_stack, name]) if scope_stack else name
                    graph.symbols.append(
                        ParsedSymbol(
                            subject_type="func",
                            symbol_name=name,
                            symbol_qualname=qual,
                            line=node.start_point[0] + 1,
                            column=node.start_point[1] + 1,
                        )
                    )
                    graph.edges.append(
                        ParsedEdge(
                            edge_type="defines",
                            from_symbol_ref=None,
                            to_symbol_ref=qual,
                            from_file=file_path,
                            to_file_or_external=file_path,
                            line=node.start_point[0] + 1,
                            column=node.start_point[1] + 1,
                            evidence=f"def {name}",
                        )
                    )
                    scope_stack = [*scope_stack, name]
                    current_scope = qual

            if ntype == "call":
                func_node = node.child_by_field_name("function")
                if func_node is not None:
                    callee = node_text(func_node).strip()
                    callee_name = callee.split(".")[-1]
                    graph.edges.append(
                        ParsedEdge(
                            edge_type="calls",
                            from_symbol_ref=current_scope,
                            to_symbol_ref=callee_name,
                            from_file=file_path,
                            to_file_or_external=callee,
                            line=node.start_point[0] + 1,
                            column=node.start_point[1] + 1,
                            evidence=callee,
                        )
                    )
                    graph.external_refs.append(ExternalRef(ref=callee_name, ref_type="symbol"))

            if ntype == "identifier":
                ref = node_text(node).strip()
                if ref and ref in import_aliases:
                    graph.edges.append(
                        ParsedEdge(
                            edge_type="references",
                            from_symbol_ref=current_scope,
                            to_symbol_ref=ref,
                            from_file=file_path,
                            to_file_or_external=ref,
                            line=node.start_point[0] + 1,
                            column=node.start_point[1] + 1,
                            evidence=ref,
                        )
                    )
                    graph.external_refs.append(ExternalRef(ref=ref, ref_type="symbol"))

            for child in node.children:
                visit(child, scope_stack)

        try:
            parse_import_nodes()
            visit(root, [])
        except Exception as exc:
            graph.diagnostics.append(ParseDiagnostic(message=f"python parse traversal failed: {exc}"))
            logger.warning("Python parser traversal warning file=%s error=%s", file_path, exc)

        logger.debug(
            "Python parser parsed file=%s symbols=%s edges=%s diagnostics=%s",
            file_path,
            len(graph.symbols),
            len(graph.edges),
            len(graph.diagnostics),
        )
        return graph
