"""recall 결과를 한 응답 문자열로 직렬화."""

from __future__ import annotations

from tunallama_core import RecallResult


def format_recall(r: RecallResult) -> str:
    if r.total_matches == 0:
        return f"'{r.query}' 매칭 없음."
    head = f"'{r.query}' 매칭 {r.total_matches}건 (상위 {len(r.snippets)}):"
    lines = [head]
    for s in r.snippets:
        lines.append(f"- [{s.full_id}] {s.timestamp} · {s.tool_name}")
        lines.append(f"  in:  {s.inputs_summary}")
        lines.append(f"  out: {s.output_excerpt}")
    return "\n".join(lines)
