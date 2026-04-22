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

_SIMPLE_IDENTIFIER_NODE_TYPES = {
    "identifier",
    "property_identifier",
    "private_property_identifier",
    "type_identifier",
    "this",
    "super",
}
_UNWRAP_EXPRESSION_NODE_TYPES = {
    "parenthesized_expression",
    "non_null_expression",
    "await_expression",
    "as_expression",
    "satisfies_expression",
    "type_assertion",
}


class TreeSitterTsJsParser:
    """Best-effort TS/JS parser powered by Tree-sitter grammars."""

    def __init__(self, *, enabled_languages: set[str]) -> None:
        self._enabled_languages = enabled_languages
        self._parsers: dict[str, Any] = {}
        self._init_errors: dict[str, str] = {}

        if get_parser is None:
            self._init_errors["typescript"] = "tree_sitter_language_pack is not installed"
            self._init_errors["javascript"] = "tree_sitter_language_pack is not installed"
            logger.warning("TS/JS parser unavailable: %s", self._init_errors)
            return

        for lang in ["typescript", "javascript"]:
            if lang not in self._enabled_languages:
                continue
            try:
                self._parsers[lang] = get_parser(lang)
                logger.info("TS/JS parser initialized language=%s", lang)
            except Exception as exc:  # pragma: no cover - env-specific
                self._init_errors[lang] = f"failed to initialize {lang} parser: {exc}"
                logger.warning("TS/JS parser unavailable language=%s error=%s", lang, exc)

    def parse(self, *, file_path: str, source_text: str) -> ParsedFileGraph:
        language = "typescript" if file_path.endswith((".ts", ".tsx")) else "javascript"
        graph = ParsedFileGraph()
        parser = self._parsers.get(language)
        if not parser:
            graph.diagnostics.append(
                ParseDiagnostic(message=self._init_errors.get(language, f"{language} parser unavailable"))
            )
            logger.warning(
                "TS/JS parser parse fallback file=%s language=%s reason=%s",
                file_path,
                language,
                self._init_errors.get(language, f"{language} parser unavailable"),
            )
            return graph

        source_bytes = source_text.encode("utf-8", errors="ignore")
        tree = parser.parse(source_bytes)
        root = tree.root_node

        def node_text(node: Any) -> str:
            return source_bytes[node.start_byte : node.end_byte].decode("utf-8", errors="ignore")

        def walk(node: Any):
            yield node
            for child in node.children:
                yield from walk(child)

        def find_first_identifier(node: Any) -> str | None:
            for child in node.children:
                if child.type in {"identifier", "property_identifier", "type_identifier"}:
                    return node_text(child).strip()
            return None

        def unwrap_expression(node: Any) -> Any:
            current = node
            for _ in range(8):
                if current is None or current.type not in _UNWRAP_EXPRESSION_NODE_TYPES:
                    return current
                inner = current.child_by_field_name("expression")
                if inner is None:
                    named_children = [child for child in current.children if getattr(child, "is_named", False)]
                    inner = named_children[0] if named_children else None
                if inner is None or inner is current:
                    return current
                current = inner
            return current

        def extract_identifier_like(node: Any) -> str | None:
            unwrapped = unwrap_expression(node)
            if unwrapped is None:
                return None
            if unwrapped.type in _SIMPLE_IDENTIFIER_NODE_TYPES:
                value = node_text(unwrapped).strip()
                return value or None
            return None

        def extract_reference_like(node: Any, *, depth: int = 0) -> str | None:
            if node is None or depth > 8:
                return None
            unwrapped = unwrap_expression(node)
            if unwrapped is None:
                return None
            if unwrapped.type in _SIMPLE_IDENTIFIER_NODE_TYPES:
                value = node_text(unwrapped).strip()
                return value or None
            if unwrapped.type in {"member_expression", "optional_member_expression"}:
                object_node = unwrapped.child_by_field_name("object")
                property_node = unwrapped.child_by_field_name("property")
                property_ref = extract_identifier_like(property_node)
                if not property_ref:
                    return None
                object_ref = extract_reference_like(object_node, depth=depth + 1)
                return f"{object_ref}.{property_ref}" if object_ref else property_ref
            return None

        def extract_call_target_refs(function_node: Any) -> tuple[str | None, str | None]:
            callee_ref = extract_reference_like(function_node)
            if not callee_ref:
                return None, None
            callee_name = callee_ref.split(".")[-1].strip()
            return callee_ref, (callee_name or None)

        def collect_imports_exports() -> None:
            for node in walk(root):
                if node.type == "import_statement":
                    text = node_text(node)
                    source = None
                    for child in node.children:
                        if child.type == "string":
                            source = node_text(child).strip('"\'')
                            break
                    if source:
                        graph.edges.append(
                            ParsedEdge(
                                edge_type="imports",
                                from_symbol_ref=None,
                                to_symbol_ref=None,
                                from_file=file_path,
                                to_file_or_external=source,
                                line=node.start_point[0] + 1,
                                column=node.start_point[1] + 1,
                                evidence=text.strip(),
                            )
                        )
                        graph.external_refs.append(ExternalRef(ref=source, ref_type="module"))
                if node.type == "export_statement":
                    text = node_text(node)
                    graph.edges.append(
                        ParsedEdge(
                            edge_type="exports",
                            from_symbol_ref=None,
                            to_symbol_ref=None,
                            from_file=file_path,
                            to_file_or_external=file_path,
                            line=node.start_point[0] + 1,
                            column=node.start_point[1] + 1,
                            evidence=text.strip(),
                        )
                    )

        def visit(node: Any, scope_stack: list[str]) -> None:
            current_scope = ".".join(scope_stack) if scope_stack else None
            ntype = node.type

            if ntype in {"function_declaration", "method_definition", "generator_function_declaration"}:
                name = find_first_identifier(node)
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
                            evidence=f"function {name}",
                        )
                    )
                    scope_stack = [*scope_stack, name]
                    current_scope = qual

            if ntype in {"class_declaration", "class"}:
                name = find_first_identifier(node)
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
                    class_text = node_text(node)
                    if "extends" in class_text:
                        extends_part = class_text.split("extends", 1)[1].split("{", 1)[0].strip()
                        if extends_part:
                            base_name = extends_part.split("<", 1)[0].strip().split(" ", 1)[0]
                            graph.edges.append(
                                ParsedEdge(
                                    edge_type="inherits",
                                    from_symbol_ref=qual,
                                    to_symbol_ref=base_name,
                                    from_file=file_path,
                                    to_file_or_external=base_name,
                                    line=node.start_point[0] + 1,
                                    column=node.start_point[1] + 1,
                                    evidence=extends_part,
                                )
                            )
                            graph.external_refs.append(ExternalRef(ref=base_name, ref_type="symbol"))
                    scope_stack = [*scope_stack, name]
                    current_scope = qual

            if ntype == "call_expression":
                function_node = node.child_by_field_name("function")
                if function_node is not None:
                    callee_ref, callee_name = extract_call_target_refs(function_node)
                    if callee_name:
                        graph.edges.append(
                            ParsedEdge(
                                edge_type="calls",
                                from_symbol_ref=current_scope,
                                to_symbol_ref=callee_name,
                                from_file=file_path,
                                to_file_or_external=callee_ref,
                                line=node.start_point[0] + 1,
                                column=node.start_point[1] + 1,
                                evidence=callee_ref,
                            )
                        )
                        graph.external_refs.append(ExternalRef(ref=callee_name, ref_type="symbol"))

            if ntype in {"identifier", "property_identifier"}:
                ref = node_text(node).strip()
                if ref and ref not in {"export", "import", "from", "class", "function", "extends"}:
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

            for child in node.children:
                visit(child, scope_stack)

        try:
            collect_imports_exports()
            visit(root, [])
        except Exception as exc:
            graph.diagnostics.append(ParseDiagnostic(message=f"ts/js parse traversal failed: {exc}"))
            logger.warning("TS/JS parser traversal warning file=%s language=%s error=%s", file_path, language, exc)

        logger.debug(
            "TS/JS parser parsed file=%s language=%s symbols=%s edges=%s diagnostics=%s",
            file_path,
            language,
            len(graph.symbols),
            len(graph.edges),
            len(graph.diagnostics),
        )
        return graph
