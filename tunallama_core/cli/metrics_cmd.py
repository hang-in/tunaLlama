"""``tunallama metrics`` - organic dogfooding metric 조회 / 정리.

서브액션:
- ``show``: metric 별 평균 / count / min / max
- ``list``: 최근 100 entry list
- ``clear``: 전부 삭제 (source=organic 만 또는 전체)
"""

from __future__ import annotations

from ..measurement.organic import (
    _resolve_db_path,
    clear_metrics,
    list_metrics,
    summarize_metrics,
)


def run_metrics(*, action: str, source: str | None = None) -> int:
    db_path = _resolve_db_path()

    if action == "path":
        print(db_path)
        return 0

    if action == "show":
        if not db_path.exists():
            print(f"(metrics db 없음: {db_path})")
            return 0
        summary = summarize_metrics(source=source)
        if not summary:
            print(f"(metric 없음, source={source or 'all'})")
            return 0
        src_label = source or "all sources"
        print(f"\n=== tunaLlama organic metrics ({src_label}) ===")
        print(f"{'metric':<28}{'avg':>8}{'count':>8}{'min':>8}{'max':>8}")
        print("-" * 60)
        for m, stats in summary.items():
            print(
                f"{m:<28}{stats['avg']:>8.2f}{stats['count']:>8}"
                f"{stats['min']:>8.2f}{stats['max']:>8.2f}"
            )
        print()
        return 0

    if action == "list":
        if not db_path.exists():
            print(f"(metrics db 없음: {db_path})")
            return 0
        rows = list_metrics(source=source, limit=50)
        if not rows:
            print(f"(metric 없음, source={source or 'all'})")
            return 0
        print(
            f"\n{'timestamp':<22}{'metric':<26}{'value':>8}"
            f"{'tool':<22}{'src':<10}"
        )
        print("-" * 90)
        for r in rows:
            print(
                f"{r.timestamp:<22}{r.metric:<26}{r.value:>8.2f}"
                f"{(r.tool_name or '-'):<22}{r.source:<10}"
            )
        print()
        return 0

    if action == "clear":
        removed = clear_metrics(source=source)
        src_label = f"source={source}" if source else "all"
        print(f"[OK] {removed} metric 삭제 ({src_label})")
        return 0

    print(f"[오류] 알 수 없는 액션: {action}")
    return 1
