"""Organic dogfooding metric 수집.

매 delegation 후 자동으로:
- standalone_toy_rate (LLM 출력의 mock/fake 비율)
- convention_adherence_rate (state.md 의 conventions honor 비율)

가 계산되어 SQLite ``metrics`` 테이블에 적재. ``tunallama metrics show`` 로
조회. Phase 6-4 의 ``MetricSample`` 와 schema 일치 + source="organic" 태그.

비활성: ``TUNA_ORGANIC_METRICS=0`` env.
"""

from __future__ import annotations

import logging
import os
import sqlite3
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from ..memory.state import load_state
from .ast_smell import analyze_ast
from .memory_metrics import convention_adherence_rate, standalone_toy_rate

_logger = logging.getLogger("tunallama.metrics")
_DEFAULT_DB = Path.home() / ".tunallama" / "metrics.db"


def _resolve_db_path() -> Path:
    """env override 또는 default."""
    override = os.environ.get("TUNA_METRICS_DB")
    return Path(override).expanduser() if override else _DEFAULT_DB


_SCHEMA = """
CREATE TABLE IF NOT EXISTS metrics (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp TEXT NOT NULL,
    metric TEXT NOT NULL,
    value REAL NOT NULL,
    source TEXT NOT NULL,
    tool_name TEXT,
    project_root TEXT,
    n_sample INTEGER NOT NULL DEFAULT 1
);
CREATE INDEX IF NOT EXISTS idx_metrics_metric ON metrics(metric);
CREATE INDEX IF NOT EXISTS idx_metrics_timestamp ON metrics(timestamp);
CREATE INDEX IF NOT EXISTS idx_metrics_source ON metrics(source);
"""


def _connect() -> sqlite3.Connection:
    p = _resolve_db_path()
    p.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(p))
    conn.row_factory = sqlite3.Row
    conn.executescript(_SCHEMA)
    return conn


@dataclass(frozen=True)
class RecordedMetric:
    metric: str
    value: float
    source: str  # "organic" | "spec_dogfooding" | "synthetic"
    timestamp: str
    tool_name: str | None = None
    project_root: str | None = None
    n_sample: int = 1


def record_metric(
    metric: str, value: float, *,
    source: str = "organic",
    tool_name: str | None = None,
    project_root: str | None = None,
    n_sample: int = 1,
) -> None:
    """metric 1 개 적재. 실패 silent (logger.warning)."""
    try:
        ts = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        with _connect() as conn:
            conn.execute(
                "INSERT INTO metrics (timestamp, metric, value, source, "
                "tool_name, project_root, n_sample) VALUES (?, ?, ?, ?, ?, ?, ?)",
                (ts, metric, value, source, tool_name, project_root, n_sample),
            )
            conn.commit()
    except Exception as exc:  # noqa: BLE001
        _logger.warning("metric record failed: %s", exc)


def collect_organic_after_delegation(
    output: str, *, tool_name: str, project_root: str | None,
) -> None:
    """delegation 결과 1 건 에 대해 자동 metric 계산 + 저장.

    ``TUNA_ORGANIC_METRICS=0`` 이면 skip. 실패해도 silent
    (delegation 흐름 영향 없음).
    """
    if os.environ.get("TUNA_ORGANIC_METRICS", "1") == "0":
        return
    try:
        # standalone_toy_rate - 단일 output 기준 0.0 또는 1.0.
        toy = standalone_toy_rate([output])
        record_metric(
            "standalone_toy_rate", toy, source="organic",
            tool_name=tool_name, project_root=project_root,
        )

        # convention_adherence_rate - state.md 의 conventions 1 개 이상 시.
        state = load_state(project_root)
        if state.entries:
            adh = convention_adherence_rate(state, [output])
            for res in adh:
                # 각 convention 별 hit rate (0.0 or 1.0 - single output).
                # convention text 자체는 길어 metric name 에 넣지 않고,
                # 평균만 적재.
                pass
            if adh:
                avg = sum(r.rate for r in adh) / len(adh)
                record_metric(
                    "convention_adherence_rate", avg, source="organic",
                    tool_name=tool_name, project_root=project_root,
                    n_sample=len(adh),
                )

        # AST excess_score - LLM 출력 코드의 정적 분석 종합 점수.
        smell = analyze_ast(output)
        record_metric(
            "ast_excess_score", float(smell.excess_score), source="organic",
            tool_name=tool_name, project_root=project_root,
        )
        record_metric(
            "syntactically_valid", 1.0 if smell.syntactically_valid else 0.0,
            source="organic",
            tool_name=tool_name, project_root=project_root,
        )
    except Exception as exc:  # noqa: BLE001
        _logger.warning("organic metric collect failed: %s", exc)


def list_metrics(
    metric: str | None = None,
    *,
    source: str | None = None,
    limit: int = 100,
) -> list[RecordedMetric]:
    """기록된 metric 조회. metric / source 로 필터."""
    where = []
    params: list = []
    if metric:
        where.append("metric = ?")
        params.append(metric)
    if source:
        where.append("source = ?")
        params.append(source)
    sql = "SELECT * FROM metrics"
    if where:
        sql += " WHERE " + " AND ".join(where)
    sql += " ORDER BY timestamp DESC LIMIT ?"
    params.append(limit)
    try:
        with _connect() as conn:
            rows = conn.execute(sql, params).fetchall()
        return [
            RecordedMetric(
                metric=r["metric"],
                value=float(r["value"]),
                source=r["source"],
                timestamp=r["timestamp"],
                tool_name=r["tool_name"],
                project_root=r["project_root"],
                n_sample=int(r["n_sample"]),
            )
            for r in rows
        ]
    except Exception as exc:  # noqa: BLE001
        _logger.warning("metric list failed: %s", exc)
        return []


def summarize_metrics(
    *,
    source: str | None = None,
    since: str | None = None,
) -> dict[str, dict]:
    """metric 별 평균 + 갯수. source 필터.

    return: ``{metric_name: {"avg": ..., "count": ..., "min": ..., "max": ...}}``
    """
    where = []
    params: list = []
    if source:
        where.append("source = ?")
        params.append(source)
    if since:
        where.append("timestamp >= ?")
        params.append(since)
    sql = (
        "SELECT metric, AVG(value) avg_v, COUNT(*) cnt, "
        "MIN(value) min_v, MAX(value) max_v FROM metrics"
    )
    if where:
        sql += " WHERE " + " AND ".join(where)
    sql += " GROUP BY metric ORDER BY metric"
    try:
        with _connect() as conn:
            rows = conn.execute(sql, params).fetchall()
        return {
            r["metric"]: {
                "avg": float(r["avg_v"]) if r["avg_v"] is not None else 0.0,
                "count": int(r["cnt"]),
                "min": float(r["min_v"]) if r["min_v"] is not None else 0.0,
                "max": float(r["max_v"]) if r["max_v"] is not None else 0.0,
            }
            for r in rows
        }
    except Exception as exc:  # noqa: BLE001
        _logger.warning("metric summarize failed: %s", exc)
        return {}


def clear_metrics(*, source: str | None = None) -> int:
    """metric 삭제. source 필터. return: 삭제 행 수."""
    try:
        with _connect() as conn:
            if source:
                cur = conn.execute("DELETE FROM metrics WHERE source = ?", (source,))
            else:
                cur = conn.execute("DELETE FROM metrics")
            conn.commit()
            return cur.rowcount
    except Exception as exc:  # noqa: BLE001
        _logger.warning("metric clear failed: %s", exc)
        return 0
