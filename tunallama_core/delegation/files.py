"""파일 경로를 받는 3개 도구.

핵심 보안 원칙:
1. **project_root 내만 허용** — 절대경로/상위경로로 비밀파일에 접근하는 것을 차단.
2. **비밀 파일 이름/디렉토리 패턴 거부** — `.env`, `id_rsa`, `*.pem`, `.ssh/*` 등.
3. **최대 파일 크기 제한** — 1MB.
4. **binary 거부** — UTF-8 디코드 실패 시 거부.
5. **inputs_for_log 에는 경로만** — 파일 내용은 LLM 에는 가지만 메모리 로그에는 안 들어감
   (Claude 컨텍스트로 다시 흘러가지 않게). 핸드오프 §7.4 시나리오 B.
"""

from __future__ import annotations

import re
from pathlib import Path

from ..errors import FileScopeError
from ..llm.base import LLMClient
from ..memory.store import MemoryStore
from . import _prompts
from ._runner import DelegationResult, run_delegation

_MAX_FILE_BYTES = 1_000_000  # 1 MB

# 비밀 파일 이름 패턴 — 정확히 매칭되거나 흔한 변종 포함.
_SECRET_NAME_RE = re.compile(
    r"^(\.env(\..+)?"
    r"|id_(rsa|ed25519|ecdsa|dsa)(\.pub)?"
    r"|.*\.pem"
    r"|.*\.key"
    r"|.*credentials.*"
    r"|.*secret.*"
    r"|.*token.*"
    r"|\.netrc)$",
    re.IGNORECASE,
)

# 비밀 디렉토리 — 경로 어디서든 해당 세그먼트가 나타나면 거부.
_SECRET_DIR_PARTS = frozenset(
    {".ssh", ".aws", ".gnupg", ".kube", ".azure", ".gcloud"}
)


def _reject_secret_paths(p: Path) -> None:
    if _SECRET_NAME_RE.match(p.name):
        raise FileScopeError(f"비밀 파일 이름 패턴 거부: {p}")
    if _SECRET_DIR_PARTS & set(part.lower() for part in p.parts):
        raise FileScopeError(f"비밀 디렉토리 경로 거부: {p}")


def _read(path: str, *, project_root: str | None) -> str:
    if not project_root:
        raise FileScopeError(
            "project_root 가 비어있습니다 — 파일 접근 범위를 결정할 수 없음."
        )
    p = Path(path).expanduser().resolve()
    root = Path(project_root).expanduser().resolve()

    try:
        p.relative_to(root)
    except ValueError as e:
        raise FileScopeError(
            f"파일이 project_root 밖에 있습니다: {p} (root: {root})"
        ) from e

    _reject_secret_paths(p)

    if not p.is_file():
        raise FileNotFoundError(f"파일이 없거나 일반 파일이 아닙니다: {path}")
    size = p.stat().st_size
    if size > _MAX_FILE_BYTES:
        raise FileScopeError(
            f"파일이 너무 큼 ({size:,} > {_MAX_FILE_BYTES:,} bytes): {p}"
        )
    try:
        return p.read_text(encoding="utf-8")
    except UnicodeDecodeError as e:
        raise FileScopeError(f"binary 또는 비-UTF-8 파일 거부: {p}") from e


def review_file(
    file_path: str,
    *,
    focus: str | None = None,
    client: LLMClient,
    store: MemoryStore | None = None,
    project_root: str | None = None,
    session_id: str | None = None,
    recall_prefix: str | None = None,
) -> DelegationResult:
    content = _read(file_path, project_root=project_root)
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
        recall_prefix=recall_prefix,
    )


def explain_file(
    file_path: str,
    *,
    audience: str | None = None,
    client: LLMClient,
    store: MemoryStore | None = None,
    project_root: str | None = None,
    session_id: str | None = None,
    recall_prefix: str | None = None,
) -> DelegationResult:
    content = _read(file_path, project_root=project_root)
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
        recall_prefix=recall_prefix,
    )


def analyze_files(
    file_paths: list[str],
    question: str,
    *,
    client: LLMClient,
    store: MemoryStore | None = None,
    project_root: str | None = None,
    session_id: str | None = None,
    recall_prefix: str | None = None,
) -> DelegationResult:
    if not file_paths:
        raise ValueError("file_paths 가 비어있습니다.")
    blocks = [
        f"=== {p} ===\n{_read(p, project_root=project_root)}" for p in file_paths
    ]
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
        recall_prefix=recall_prefix,
    )
