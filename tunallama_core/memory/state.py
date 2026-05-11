"""Phase 6-1 - project-scoped state.md auto-load.

각 프로젝트마다 ``~/.tunallama/projects/<project_hash>/state.md`` 1개.
project_hash = git root absolute path 의 SHA256 → 12 hex. git 아니면 CWD path.

state.md 는 4 섹션:
- Conventions
- Active Decisions
- Constraints
- Anti-patterns observed

각 entry 는 source tag (auto / manual / verified) + 출현 횟수 + last_seen.
size cap 시 Active Decisions → Anti-patterns 순으로 truncate. Conventions /
Constraints 는 never truncate (highest-value).
"""

from __future__ import annotations

import hashlib
import os
import re
import subprocess
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Literal

def _default_state_base() -> Path:
    """``TUNA_STATE_BASE`` env override 또는 ``~/.tunallama/projects``."""
    override = os.environ.get("TUNA_STATE_BASE")
    if override:
        return Path(override).expanduser()
    return Path.home() / ".tunallama" / "projects"


DEFAULT_STATE_BASE = _default_state_base()
DEFAULT_MAX_BYTES = 2048

SECTION_CONVENTIONS = "Conventions"
SECTION_DECISIONS = "Active Decisions"
SECTION_CONSTRAINTS = "Constraints"
SECTION_ANTIPATTERNS = "Anti-patterns observed"

_VALID_SECTIONS = (
    SECTION_CONVENTIONS,
    SECTION_DECISIONS,
    SECTION_CONSTRAINTS,
    SECTION_ANTIPATTERNS,
)

# 절대 truncate 안 하는 섹션
_NEVER_TRUNCATE = {SECTION_CONVENTIONS, SECTION_CONSTRAINTS}

EntrySource = Literal["auto", "manual", "verified"]


@dataclass
class StateEntry:
    section: str
    text: str
    source: EntrySource = "auto"
    occurrences: int = 1
    last_seen: str = ""

    def __post_init__(self) -> None:
        if self.section not in _VALID_SECTIONS:
            raise ValueError(f"unknown section: {self.section}")
        if not self.last_seen:
            self.last_seen = _now_iso()


@dataclass
class StateFile:
    project_hash: str
    project_root: str
    last_updated: str
    entries: list[StateEntry] = field(default_factory=list)
    path: Path = field(default_factory=Path)

    @property
    def by_section(self) -> dict[str, list[StateEntry]]:
        out: dict[str, list[StateEntry]] = {s: [] for s in _VALID_SECTIONS}
        for e in self.entries:
            out.setdefault(e.section, []).append(e)
        return out


def _now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def get_project_hash(project_root: str | os.PathLike | None = None) -> tuple[str, str]:
    """``(project_hash, resolved_root)`` 반환.

    ``project_root`` 가 git repo 면 git root absolute path 의 SHA256 12 hex.
    아니면 ``project_root`` (혹은 CWD) 의 absolute path 의 SHA256 12 hex.
    """
    base = Path(project_root) if project_root else Path.cwd()
    base = base.resolve()

    # git root 시도
    try:
        result = subprocess.run(
            ["git", "-C", str(base), "rev-parse", "--show-toplevel"],
            capture_output=True, text=True, timeout=2,
        )
        if result.returncode == 0:
            git_root = Path(result.stdout.strip()).resolve()
            digest = hashlib.sha256(
                str(git_root).encode("utf-8")
            ).hexdigest()[:12]
            return digest, str(git_root)
    except (FileNotFoundError, subprocess.TimeoutExpired):
        pass

    digest = hashlib.sha256(str(base).encode("utf-8")).hexdigest()[:12]
    return digest, str(base)


def state_path_for(project_hash: str, *, base: Path | None = None) -> Path:
    return (base or DEFAULT_STATE_BASE) / project_hash / "state.md"


# ---------------- parser ----------------

_SECTION_RE = re.compile(r"^## (.+?)\s*$", re.MULTILINE)
_LAST_UPDATED_RE = re.compile(
    r"<!--\s*Last updated:\s*(\S+)\s*-->", re.IGNORECASE
)

# - (tag) text  /  - (auto, N occurrences) text
_ENTRY_RE = re.compile(
    r"^-\s+"
    r"\((?P<tag>auto|manual|verified)"
    r"(?:,\s*(?P<occ>\d+)\s+occurrences?)?\)\s+"
    r"(?P<text>.+?)\s*$"
)


def _parse_state_text(content: str) -> tuple[str, list[StateEntry]]:
    """state.md 텍스트 → (last_updated, entries)."""
    last_updated_match = _LAST_UPDATED_RE.search(content)
    last_updated = last_updated_match.group(1) if last_updated_match else ""

    entries: list[StateEntry] = []
    # 섹션 별로 자르기
    parts = _SECTION_RE.split(content)
    # split 결과: [pre, sec1_name, sec1_body, sec2_name, sec2_body, ...]
    if len(parts) <= 1:
        return last_updated, entries
    for i in range(1, len(parts), 2):
        section = parts[i].strip()
        body = parts[i + 1] if i + 1 < len(parts) else ""
        if section not in _VALID_SECTIONS:
            continue
        for line in body.splitlines():
            m = _ENTRY_RE.match(line.strip())
            if not m:
                continue
            tag = m.group("tag")
            occ_raw = m.group("occ")
            text = m.group("text").strip()
            if not text:
                continue
            try:
                entries.append(StateEntry(
                    section=section,
                    text=text,
                    source=tag,  # type: ignore[arg-type]
                    occurrences=int(occ_raw) if occ_raw else 1,
                    last_seen=last_updated or _now_iso(),
                ))
            except ValueError:
                continue
    return last_updated, entries


def load_state(
    project_root: str | os.PathLike | None = None,
    *,
    base: Path | None = None,
) -> StateFile:
    """프로젝트의 state.md 로드. 없으면 빈 StateFile."""
    project_hash, resolved_root = get_project_hash(project_root)
    path = state_path_for(project_hash, base=base)

    if not path.exists():
        return StateFile(
            project_hash=project_hash,
            project_root=resolved_root,
            last_updated=_now_iso(),
            entries=[],
            path=path,
        )
    content = path.read_text(encoding="utf-8")
    last_updated, entries = _parse_state_text(content)
    return StateFile(
        project_hash=project_hash,
        project_root=resolved_root,
        last_updated=last_updated or _now_iso(),
        entries=entries,
        path=path,
    )


def append_entry(
    state: StateFile,
    entry: StateEntry,
    *,
    match_text_lower: bool = True,
) -> StateEntry:
    """state 에 entry 추가. 같은 section + 동일 text 면 occurrences 증가만.

    return: 실제 저장된 entry (기존이면 increment 된 것, 신규면 새 entry).
    """
    if entry.section not in _VALID_SECTIONS:
        raise ValueError(f"unknown section: {entry.section}")
    needle = entry.text.lower() if match_text_lower else entry.text
    for existing in state.entries:
        if existing.section != entry.section:
            continue
        haystack = existing.text.lower() if match_text_lower else existing.text
        if haystack == needle:
            # 기존 entry 보존, 빈도/last_seen 만 update.
            existing.occurrences += entry.occurrences
            existing.last_seen = entry.last_seen or _now_iso()
            # manual / verified 가 auto 보다 우선 - downgrade 금지
            if entry.source in ("manual", "verified") and existing.source == "auto":
                existing.source = entry.source
            return existing
    state.entries.append(entry)
    return entry


def render(state: StateFile) -> str:
    """StateFile → state.md text."""
    lines: list[str] = [
        "# tunaLlama Project Memory",
        "<!-- auto-generated, auto-loaded. Manual edits preserved. -->",
        f"<!-- Last updated: {state.last_updated} -->",
        "",
    ]
    by_section = state.by_section
    for section in _VALID_SECTIONS:
        lines.append(f"## {section}")
        rows = by_section.get(section, [])
        if not rows:
            lines.append("(none)")
            lines.append("")
            continue
        for e in rows:
            tag = e.source
            if e.source == "auto" and e.occurrences > 1:
                tag = f"auto, {e.occurrences} occurrences"
            lines.append(f"- ({tag}) {e.text}")
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def _truncate_to_budget(
    state: StateFile, *, max_bytes: int
) -> tuple[StateFile, int]:
    """size cap 초과 시 truncate. Active Decisions → Anti-patterns 순으로 오래된
    entry 부터 제거. Conventions / Constraints 는 never.

    return: (state, n_removed).
    """
    text = render(state)
    n_removed = 0
    if len(text.encode("utf-8")) <= max_bytes:
        return state, 0

    truncate_order = (SECTION_DECISIONS, SECTION_ANTIPATTERNS)
    for section in truncate_order:
        while len(render(state).encode("utf-8")) > max_bytes:
            # 해당 섹션의 가장 오래된 entry 찾기 (last_seen 기준).
            candidates = [
                (i, e) for i, e in enumerate(state.entries)
                if e.section == section
            ]
            if not candidates:
                break
            # last_seen ascending → 가장 오래된 게 첫 번째.
            candidates.sort(key=lambda pair: pair[1].last_seen)
            idx, _ = candidates[0]
            del state.entries[idx]
            n_removed += 1
        if len(render(state).encode("utf-8")) <= max_bytes:
            break
    return state, n_removed


def save_state(
    state: StateFile,
    *,
    max_bytes: int = DEFAULT_MAX_BYTES,
) -> int:
    """state.md 저장 + size cap. return: truncate 된 entry 수."""
    state.last_updated = _now_iso()
    state, removed = _truncate_to_budget(state, max_bytes=max_bytes)
    state.path.parent.mkdir(parents=True, exist_ok=True)
    state.path.write_text(render(state), encoding="utf-8")
    return removed
