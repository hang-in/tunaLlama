"""tunaLlama MCP 서버 — Claude Code 플러그인 진입점.

backend(``tunallama_core``) 의 도구 10종 + dev_review 2종 + recall + log_limitation
을 MCP tool 로 노출. docstring 은 Claude 가 도구 선택에 사용하므로 의도를 명확히 적는다.

실행:
    python -m plugin.mcp_server
"""

from __future__ import annotations

from mcp.server.fastmcp import FastMCP

from tunallama_core import (
    analyze_files as core_analyze_files,
    dev_review_from_spec as core_dev_review_from_spec,
    dev_review_loop as core_dev_review_loop,
    explain_code as core_explain_code,
    explain_file as core_explain_file,
    fix_code as core_fix_code,
    general_task as core_general_task,
    generate_code as core_generate_code,
    log_limitation as core_log_limitation,
    recall as core_recall,
    refactor_code as core_refactor_code,
    review_code as core_review_code,
    review_file as core_review_file,
    write_tests as core_write_tests,
)

from . import _state
from ._adapters import (
    call_delegation,
    call_dev_review,
    empty_to_none,
    project_root,
)
from ._format import format_recall

mcp = FastMCP("tunaLlama")


@mcp.tool()
def tuna_generate_code(requirements: str, language: str = "") -> str:
    """Generate code via local LLM. Use this instead of generating long code yourself
    when requirements are clear and the output would consume many tokens."""
    return call_delegation(
        core_generate_code,
        recall_query=requirements,
        requirements=requirements,
        language=empty_to_none(language),
    )


@mcp.tool()
def tuna_review_code(code: str, focus: str = "") -> str:
    """Review code via local LLM. ``focus`` can be 'security', 'performance', etc."""
    return call_delegation(
        core_review_code,
        recall_query=focus or None,
        code=code,
        focus=empty_to_none(focus),
    )


@mcp.tool()
def tuna_explain_code(code: str, audience: str = "") -> str:
    """Explain what code does. ``audience`` like 'beginner' / 'expert' adjusts depth."""
    return call_delegation(
        core_explain_code,
        recall_query=None,  # explanation 은 recall 별 도움 X
        code=code,
        audience=empty_to_none(audience),
    )


@mcp.tool()
def tuna_refactor_code(code: str, goal: str) -> str:
    """Refactor code toward the stated goal while preserving behavior."""
    return call_delegation(
        core_refactor_code,
        recall_query=goal,
        code=code,
        goal=goal,
    )


@mcp.tool()
def tuna_fix_code(code: str, error: str) -> str:
    """Fix code given the observed error message."""
    return call_delegation(
        core_fix_code,
        recall_query=error,
        code=code,
        error=error,
    )


@mcp.tool()
def tuna_write_tests(code: str, framework: str = "") -> str:
    """Write tests for code. Default framework: pytest."""
    return call_delegation(
        core_write_tests,
        recall_query=None,
        code=code,
        framework=empty_to_none(framework),
    )


@mcp.tool()
def tuna_general_task(task: str, context: str = "") -> str:
    """Catch-all delegation for tasks not covered by other tools."""
    return call_delegation(
        core_general_task,
        recall_query=task,
        task=task,
        context=empty_to_none(context),
    )


@mcp.tool()
def tuna_review_file(file_path: str, focus: str = "") -> str:
    """Review a file by **path**. Backend reads the file — its contents do NOT enter
    Claude's context. Major token saver vs reading the file first then asking review."""
    return call_delegation(
        core_review_file,
        recall_query=file_path,
        file_path=file_path,
        focus=empty_to_none(focus),
    )


@mcp.tool()
def tuna_explain_file(file_path: str, audience: str = "") -> str:
    """Explain a file by path. File content stays out of Claude's context."""
    return call_delegation(
        core_explain_file,
        recall_query=file_path,
        file_path=file_path,
        audience=empty_to_none(audience),
    )


@mcp.tool()
def tuna_analyze_files(file_paths: list[str], question: str) -> str:
    """Analyze relationships across multiple files (by path) to answer a question.
    File contents stay out of Claude's context."""
    return call_delegation(
        core_analyze_files,
        recall_query=question,
        file_paths=file_paths,
        question=question,
    )


@mcp.tool()
def tuna_dev_review(
    requirements: str, language: str = "", max_iterations: int = 2
) -> str:
    """Run a generate→review→fix→review loop on the local LLM and return the
    final code plus the per-iteration review log. Use this when you want the
    local model to self-correct before handing the result to you for final review.
    Known limitations from `~/.tunallama/limitations.md` are auto-prepended.
    auto_recall context is also auto-prepended per the routing config."""
    return call_dev_review(
        core_dev_review_loop,
        requirements=requirements,
        language=empty_to_none(language),
        max_iterations=max_iterations,
    )


@mcp.tool()
def tuna_dev_review_from_spec(spec_path: str, max_iterations: int = 2) -> str:
    """Read a markdown task spec from `spec_path` and run the dev_review loop.
    Spec headers (optional): `# Task: ...`, `## Phase` (DESIGN/IMPLEMENT/VERIFY),
    `## Focus`, `## Requirements`, `## Constraints` (hard rules), `## Acceptance`."""
    return call_dev_review(
        core_dev_review_from_spec,
        spec_path=spec_path,
        max_iterations=max_iterations,
    )


@mcp.tool()
def tuna_log_limitation(description: str) -> str:
    """Record a newly observed weakness of the local LLM. Future dev_review
    calls will include this note in their prompt so the model avoids the
    same mistake. Stored in ~/.tunallama/limitations.md."""
    p = core_log_limitation(description)
    return f"[OK] limitation 기록 완료: {p}"


@mcp.tool()
def tuna_recall(query: str, limit: int = 5) -> str:
    """Search past LLM delegations for similar work. Returns ranked summaries.
    Useful before starting on a familiar codebase to surface prior decisions."""
    cfg, _, store = _state._ensure()
    if store is None or not cfg.memory.enable_recall:
        return "리콜이 비활성화되어 있습니다 — config.toml 의 [memory] 확인."
    res = core_recall(store, query, limit=limit, project_root=project_root())
    return format_recall(res)


# Phase 6-1 - state.md auto-load
# Try 1 (preferred): MCP resource. Claude Code 가 attach 하면 자동 도달.
# Try 2 (fallback): tuna_load_memory tool 명시 호출. SKILL.md 에서 안내.

@mcp.resource("tunallama://memory/state")
def _memory_state_resource() -> str:
    """Project-scoped state.md (conventions, decisions, constraints, anti-patterns).

    Auto-loaded by Claude Code when attached. Captures recurring decisions
    and anti-patterns observed in this project. Manual edits in
    ~/.tunallama/projects/<hash>/state.md are preserved.
    """
    from tunallama_core.memory.state import load_state, render
    state = load_state(project_root())
    return render(state)


@mcp.tool()
def tuna_load_memory() -> str:
    """Load this project's tunaLlama memory (conventions, decisions, constraints,
    anti-patterns). Call this once at session start if MCP resources are not
    auto-attached. Path: ~/.tunallama/projects/<hash>/state.md."""
    from tunallama_core.memory.state import load_state, render
    state = load_state(project_root())
    if not state.entries:
        return (
            "(아직 기록된 state 가 없습니다. delegation 후 자동 추출되거나 "
            f"수동으로 {state.path} 편집 가능)"
        )
    return render(state)


def main() -> None:
    mcp.run()


if __name__ == "__main__":
    main()
