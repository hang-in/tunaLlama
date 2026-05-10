"""Phase 7-1 - MCP 도구 system prompt 크기 측정.

Anthropic API 직접 호출 불가 환경 (사용자 정액제) 이므로 실 토큰 측정 X.
대신 도구 description + parameter schema 직렬화 길이를 character 기준으로
추정. 토큰 환산은 단순 휴리스틱 (영문 4 char ≈ 1 token).
"""

from __future__ import annotations

import json
from dataclasses import dataclass

# Anthropic Claude tokenizer 비공개 - 영문 평균 4 char ≈ 1 token.
# JSON / 코드 토큰은 더 짧음 (3 char/token) - 보수 추정.
_CHARS_PER_TOKEN = 3.5


@dataclass(frozen=True)
class ToolSize:
    name: str
    description_chars: int
    schema_chars: int
    total_chars: int
    estimated_tokens: int


def measure_tools(mcp_app) -> list[ToolSize]:
    """FastMCP app 의 등록된 도구들 size 측정.

    ``mcp_app.list_tools()`` (async) 대신 internal _tool_manager 사용 -
    sync, 의존성 없음.
    """
    sizes: list[ToolSize] = []
    manager = getattr(mcp_app, "_tool_manager", None)
    if manager is None:
        return sizes

    tools = getattr(manager, "_tools", {})
    for name, tool in tools.items():
        desc = getattr(tool, "description", "") or ""
        params = getattr(tool, "parameters", None) or {}
        schema_json = json.dumps(params, ensure_ascii=False, sort_keys=True)
        desc_chars = len(desc)
        schema_chars = len(schema_json)
        total = desc_chars + schema_chars + len(name) + 10  # 약간의 overhead
        sizes.append(ToolSize(
            name=name,
            description_chars=desc_chars,
            schema_chars=schema_chars,
            total_chars=total,
            estimated_tokens=int(total / _CHARS_PER_TOKEN),
        ))
    sizes.sort(key=lambda s: s.total_chars, reverse=True)
    return sizes


def total_estimated_tokens(sizes: list[ToolSize]) -> int:
    return sum(s.estimated_tokens for s in sizes)


def format_size_table(sizes: list[ToolSize]) -> str:
    """디버깅 / 보고서용 표 출력."""
    lines = [
        f"{'tool':<35}{'desc':>8}{'schema':>8}{'total':>8}{'~tok':>8}",
        "-" * 67,
    ]
    for s in sizes:
        lines.append(
            f"{s.name:<35}{s.description_chars:>8}{s.schema_chars:>8}"
            f"{s.total_chars:>8}{s.estimated_tokens:>8}"
        )
    total_chars = sum(s.total_chars for s in sizes)
    total_tok = total_estimated_tokens(sizes)
    lines.append("-" * 67)
    lines.append(
        f"{'TOTAL (' + str(len(sizes)) + ' tools)':<35}"
        f"{'':>8}{'':>8}{total_chars:>8}{total_tok:>8}"
    )
    return "\n".join(lines)
