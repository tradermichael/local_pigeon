"""Architecture guard tests for dependency-injection boundaries."""

from __future__ import annotations

import ast
from pathlib import Path


def test_agent_does_not_import_concrete_tools_modules() -> None:
    """`core/agent.py` must depend on abstractions, not concrete tool modules."""
    agent_path = Path(__file__).resolve().parents[1] / "src" / "local_pigeon" / "core" / "agent.py"
    source = agent_path.read_text(encoding="utf-8")
    tree = ast.parse(source, filename=str(agent_path))

    violations: list[str] = []

    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module:
            if node.module.startswith("local_pigeon.tools") and node.module != "local_pigeon.tools.registry":
                violations.append(node.module)

    assert not violations, (
        "Dependency-injection guard failed: agent imports concrete tool modules directly. "
        "Move concrete tool imports into a ToolProvider implementation. "
        f"Found: {sorted(set(violations))}"
    )
