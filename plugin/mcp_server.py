"""tunaLlama MCP 서버 — Claude Code 플러그인 진입점.

backend(``tunallama_core``) 의 도구 10종 + ``tuna_recall`` 을 MCP tool 로 노출.
docstring 은 Claude 가 도구 선택에 사용하므로 의도를 명확히 적는다.

실행:
    python -m plugin.mcp_server
"""

from __future__ import annotations

from pathlib import Path

from mcp.server.fastmcp import FastMCP

from tunallama_core import (
    analyze_files as core_analyze_files,
    explain_code as core_explain_code,
    explain_file as core_explain_file,
    fix_code as core_fix_code,
    general_task as core_general_task,
    generate_code as core_generate_code,
    recall as core_recall,
    refactor_code as core_refactor_code,
    review_code as core_review_code,
    review_file as core_review_file,
    write_tests as core_write_tests,
)

from . import _state
from ._format import format_recall

mcp = FastMCP("tunaLlama")


def _project_root() -> str:
    return str(Path.cwd())


@mcp.tool()
def tuna_generate_code(requirements: str, language: str = "") -> str:
    """Generate code via local LLM. Use this instead of generating long code yourself
    when requirements are clear and the output would consume many tokens."""
    cfg, client, store = _state._ensure()
    r = core_generate_code(
        requirements,
        language=language or None,
        client=client,
        store=store,
        project_root=_project_root(),
    )
    return r.text


@mcp.tool()
def tuna_review_code(code: str, focus: str = "") -> str:
    """Review code via local LLM. ``focus`` can be 'security', 'performance', etc."""
    cfg, client, store = _state._ensure()
    r = core_review_code(
        code, focus=focus or None, client=client, store=store, project_root=_project_root()
    )
    return r.text


@mcp.tool()
def tuna_explain_code(code: str, audience: str = "") -> str:
    """Explain what code does. ``audience`` like 'beginner' / 'expert' adjusts depth."""
    cfg, client, store = _state._ensure()
    r = core_explain_code(
        code, audience=audience or None, client=client, store=store, project_root=_project_root()
    )
    return r.text


@mcp.tool()
def tuna_refactor_code(code: str, goal: str) -> str:
    """Refactor code toward the stated goal while preserving behavior."""
    cfg, client, store = _state._ensure()
    r = core_refactor_code(
        code, goal, client=client, store=store, project_root=_project_root()
    )
    return r.text


@mcp.tool()
def tuna_fix_code(code: str, error: str) -> str:
    """Fix code given the observed error message."""
    cfg, client, store = _state._ensure()
    r = core_fix_code(
        code, error, client=client, store=store, project_root=_project_root()
    )
    return r.text


@mcp.tool()
def tuna_write_tests(code: str, framework: str = "") -> str:
    """Write tests for code. Default framework: pytest."""
    cfg, client, store = _state._ensure()
    r = core_write_tests(
        code,
        framework=framework or None,
        client=client,
        store=store,
        project_root=_project_root(),
    )
    return r.text


@mcp.tool()
def tuna_general_task(task: str, context: str = "") -> str:
    """Catch-all delegation for tasks not covered by other tools."""
    cfg, client, store = _state._ensure()
    r = core_general_task(
        task,
        context=context or None,
        client=client,
        store=store,
        project_root=_project_root(),
    )
    return r.text


@mcp.tool()
def tuna_review_file(file_path: str, focus: str = "") -> str:
    """Review a file by **path**. Backend reads the file — its contents do NOT enter
    Claude's context. Major token saver vs reading the file first then asking review."""
    cfg, client, store = _state._ensure()
    r = core_review_file(
        file_path,
        focus=focus or None,
        client=client,
        store=store,
        project_root=_project_root(),
    )
    return r.text


@mcp.tool()
def tuna_explain_file(file_path: str, audience: str = "") -> str:
    """Explain a file by path. File content stays out of Claude's context."""
    cfg, client, store = _state._ensure()
    r = core_explain_file(
        file_path,
        audience=audience or None,
        client=client,
        store=store,
        project_root=_project_root(),
    )
    return r.text


@mcp.tool()
def tuna_analyze_files(file_paths: list[str], question: str) -> str:
    """Analyze relationships across multiple files (by path) to answer a question.
    File contents stay out of Claude's context."""
    cfg, client, store = _state._ensure()
    r = core_analyze_files(
        file_paths,
        question,
        client=client,
        store=store,
        project_root=_project_root(),
    )
    return r.text


@mcp.tool()
def tuna_recall(query: str, limit: int = 5) -> str:
    """Search past LLM delegations for similar work. Returns ranked summaries.
    Useful before starting on a familiar codebase to surface prior decisions."""
    cfg, _, store = _state._ensure()
    if store is None or not cfg.memory.enable_recall:
        return "리콜이 비활성화되어 있습니다 — config.toml 의 [memory] 확인."
    res = core_recall(store, query, limit=limit, project_root=_project_root())
    return format_recall(res)


def main() -> None:
    mcp.run()


if __name__ == "__main__":
    main()
