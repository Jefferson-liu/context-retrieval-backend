from services.repo_knowledge.parsing.parser_registry import ParserRegistry


def test_detect_language() -> None:
    assert ParserRegistry.detect_language("a.py") == "python"
    assert ParserRegistry.detect_language("a.ts") == "typescript"
    assert ParserRegistry.detect_language("a.js") == "javascript"
    assert ParserRegistry.detect_language("README.md") is None


def test_registry_returns_parser_selection() -> None:
    registry = ParserRegistry(enabled_languages={"python", "typescript", "javascript"})

    py = registry.get_parser(file_path="pkg/module.py")
    ts = registry.get_parser(file_path="app/service.ts")
    md = registry.get_parser(file_path="README.md")

    assert py.language == "python"
    assert ts.language == "typescript"
    assert md.language == "unknown"
