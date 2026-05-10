"""파일 경로를 받는 3개 도구.

핵심: 파일 내용은 LLM 프롬프트에는 들어가지만 ``inputs_for_log`` 에는
**경로만** 기록한다 (Claude 컨텍스트로 다시 흘러가지 않게). 핸드오프 §7.4 시나리오 B.
"""

from __future__ import annotations

from pathlib import Path

from ..llm.base import LLMClient
from ..memory.store import MemoryStore
from . import _prompts
from ._runner import DelegationResult, run_delegation


def _read(path: str) -> str:
    p = Path(path)
    if not p.is_file():
        raise FileNotFoundError(f"파일이 없거나 일반 파일이 아닙니다: {path}")
    return p.read_text(encoding="utf-8")


def review_file(
    file_path: str,
    *,
    focus: str | None = None,
    client: LLMClient,
    store: MemoryStore | None = None,
    project_root: str | None = None,
    session_id: str | None = None,
) -> DelegationResult:
    content = _read(file_path)
    user = (
        f"Focus: {focus}\n\n```\n{content}\n```"
        if focus
        else f"```\n{content}\n```"
    )
    return run_delegation(
        client=client,
        tool_name="review_file",
        system_prompt=_prompts.REVIEW_FILE.format(path=file_path),
        user_prompt=user,
        inputs_for_log={"file_path": file_path, "focus": focus},
        store=store,
        project_root=project_root,
        session_id=session_id,
    )


def explain_file(
    file_path: str,
    *,
    audience: str | None = None,
    client: LLMClient,
    store: MemoryStore | None = None,
    project_root: str | None = None,
    session_id: str | None = None,
) -> DelegationResult:
    content = _read(file_path)
    user = (
        f"Audience: {audience}\n\n```\n{content}\n```"
        if audience
        else f"```\n{content}\n```"
    )
    return run_delegation(
        client=client,
        tool_name="explain_file",
        system_prompt=_prompts.EXPLAIN_FILE.format(path=file_path),
        user_prompt=user,
        inputs_for_log={"file_path": file_path, "audience": audience},
        store=store,
        project_root=project_root,
        session_id=session_id,
    )


def analyze_files(
    file_paths: list[str],
    question: str,
    *,
    client: LLMClient,
    store: MemoryStore | None = None,
    project_root: str | None = None,
    session_id: str | None = None,
) -> DelegationResult:
    if not file_paths:
        raise ValueError("file_paths 가 비어있습니다.")
    blocks = [f"=== {p} ===\n{_read(p)}" for p in file_paths]
    user = f"Question: {question}\n\n" + "\n\n".join(blocks)
    return run_delegation(
        client=client,
        tool_name="analyze_files",
        system_prompt=_prompts.ANALYZE_FILES,
        user_prompt=user,
        inputs_for_log={"file_paths": list(file_paths), "question": question},
        store=store,
        project_root=project_root,
        session_id=session_id,
    )
