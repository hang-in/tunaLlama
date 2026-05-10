"""코드/텍스트 직접을 받는 7개 도구. 파일 IO 없음.

모든 도구는 ``recall_prefix`` (옵션) 를 받는다 — 호출자(plugin layer 등) 가
auto_recall 결과를 LLM prompt 위에 prepend 하고 싶을 때 사용.
"""

from __future__ import annotations

from ..llm.base import LLMClient
from ..memory.store import MemoryStore
from . import _prompts
from ._runner import DelegationResult, run_delegation


def _delegate(
    *,
    client: LLMClient,
    tool_name: str,
    system_prompt: str,
    user_prompt: str,
    inputs_for_log: dict,
    store: MemoryStore | None,
    project_root: str | None,
    session_id: str | None,
    recall_prefix: str | None,
) -> DelegationResult:
    return run_delegation(
        client=client,
        tool_name=tool_name,
        system_prompt=system_prompt,
        user_prompt=user_prompt,
        inputs_for_log=inputs_for_log,
        store=store,
        project_root=project_root,
        session_id=session_id,
        recall_prefix=recall_prefix,
    )


def generate_code(
    requirements: str,
    *,
    language: str | None = None,
    client: LLMClient,
    store: MemoryStore | None = None,
    project_root: str | None = None,
    session_id: str | None = None,
    recall_prefix: str | None = None,
) -> DelegationResult:
    user = f"Language: {language}\n\n{requirements}" if language else requirements
    return _delegate(
        client=client,
        tool_name="generate_code",
        system_prompt=_prompts.GENERATE_CODE,
        user_prompt=user,
        inputs_for_log={"requirements": requirements, "language": language},
        store=store,
        project_root=project_root,
        session_id=session_id,
        recall_prefix=recall_prefix,
    )


def review_code(
    code: str,
    *,
    focus: str | None = None,
    client: LLMClient,
    store: MemoryStore | None = None,
    project_root: str | None = None,
    session_id: str | None = None,
    recall_prefix: str | None = None,
) -> DelegationResult:
    # 작은 모델(gemma4:31b 등) 이 system prompt 첫 줄 명령을 종종 무시 —
    # user prompt 끝에도 한 줄 reminder 를 둠. dogfooding round 1-3 으로 관측.
    reminder = (
        "\n\nREMINDER: Your reply MUST start with `VERDICT: PASS` or "
        "`VERDICT: FAIL` on its own line — no markdown, no header before it."
    )
    base = f"Focus: {focus}\n\n```\n{code}\n```" if focus else f"```\n{code}\n```"
    user = base + reminder
    return _delegate(
        client=client,
        tool_name="review_code",
        system_prompt=_prompts.REVIEW_CODE,
        user_prompt=user,
        inputs_for_log={"code": code, "focus": focus},
        store=store,
        project_root=project_root,
        session_id=session_id,
        recall_prefix=recall_prefix,
    )


def explain_code(
    code: str,
    *,
    audience: str | None = None,
    client: LLMClient,
    store: MemoryStore | None = None,
    project_root: str | None = None,
    session_id: str | None = None,
    recall_prefix: str | None = None,
) -> DelegationResult:
    user = (
        f"Audience: {audience}\n\n```\n{code}\n```"
        if audience
        else f"```\n{code}\n```"
    )
    return _delegate(
        client=client,
        tool_name="explain_code",
        system_prompt=_prompts.EXPLAIN_CODE,
        user_prompt=user,
        inputs_for_log={"code": code, "audience": audience},
        store=store,
        project_root=project_root,
        session_id=session_id,
        recall_prefix=recall_prefix,
    )


def refactor_code(
    code: str,
    goal: str,
    *,
    client: LLMClient,
    store: MemoryStore | None = None,
    project_root: str | None = None,
    session_id: str | None = None,
    recall_prefix: str | None = None,
) -> DelegationResult:
    user = f"Goal: {goal}\n\n```\n{code}\n```"
    return _delegate(
        client=client,
        tool_name="refactor_code",
        system_prompt=_prompts.REFACTOR_CODE,
        user_prompt=user,
        inputs_for_log={"code": code, "goal": goal},
        store=store,
        project_root=project_root,
        session_id=session_id,
        recall_prefix=recall_prefix,
    )


def fix_code(
    code: str,
    error: str,
    *,
    client: LLMClient,
    store: MemoryStore | None = None,
    project_root: str | None = None,
    session_id: str | None = None,
    recall_prefix: str | None = None,
) -> DelegationResult:
    user = f"Error: {error}\n\n```\n{code}\n```"
    return _delegate(
        client=client,
        tool_name="fix_code",
        system_prompt=_prompts.FIX_CODE,
        user_prompt=user,
        inputs_for_log={"code": code, "error": error},
        store=store,
        project_root=project_root,
        session_id=session_id,
        recall_prefix=recall_prefix,
    )


def write_tests(
    code: str,
    *,
    framework: str | None = None,
    client: LLMClient,
    store: MemoryStore | None = None,
    project_root: str | None = None,
    session_id: str | None = None,
    recall_prefix: str | None = None,
) -> DelegationResult:
    user = (
        f"Framework: {framework}\n\n```\n{code}\n```"
        if framework
        else f"```\n{code}\n```"
    )
    return _delegate(
        client=client,
        tool_name="write_tests",
        system_prompt=_prompts.WRITE_TESTS,
        user_prompt=user,
        inputs_for_log={"code": code, "framework": framework},
        store=store,
        project_root=project_root,
        session_id=session_id,
        recall_prefix=recall_prefix,
    )


def general_task(
    task: str,
    *,
    context: str | None = None,
    client: LLMClient,
    store: MemoryStore | None = None,
    project_root: str | None = None,
    session_id: str | None = None,
    recall_prefix: str | None = None,
) -> DelegationResult:
    user = f"Task: {task}\n\nContext:\n{context}" if context else task
    return _delegate(
        client=client,
        tool_name="general_task",
        system_prompt=_prompts.GENERAL_TASK,
        user_prompt=user,
        inputs_for_log={"task": task, "context": context},
        store=store,
        project_root=project_root,
        session_id=session_id,
        recall_prefix=recall_prefix,
    )
