"""SQLite 기반 호출 기록 저장소.

단일 스레드 사용 가정. ``with MemoryStore(path) as store:`` 패턴 권장.
"""

from __future__ import annotations

import json
import sqlite3
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from ..errors import MemoryStoreError
from .tokenize import tokenize_for_index

_SCHEMA_PATH = Path(__file__).parent / "schema.sql"


@dataclass(frozen=True)
class CallRecord:
    id: int
    timestamp: str
    tool_name: str
    inputs_json: str
    output: str
    model: str
    duration_ms: int
    tokens_estimated: int | None
    project_root: str | None
    session_id: str | None
    tags: tuple[str, ...]


class MemoryStore:
    def __init__(
        self, db_path: Path | str, *, korean_tokenizer: str = "kiwi"
    ) -> None:
        self._path = Path(db_path) if db_path != ":memory:" else None
        self._raw_path = str(db_path)
        self._tokenizer = korean_tokenizer
        self._conn: sqlite3.Connection | None = None

    @property
    def conn(self) -> sqlite3.Connection:
        if self._conn is None:
            raise MemoryStoreError("MemoryStore 가 열려있지 않습니다.")
        return self._conn

    @property
    def tokenizer(self) -> str:
        return self._tokenizer

    def open(self) -> "MemoryStore":
        if self._path is not None:
            self._path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(self._raw_path)
        self._conn.row_factory = sqlite3.Row
        self._conn.executescript(_SCHEMA_PATH.read_text(encoding="utf-8"))
        return self

    def close(self) -> None:
        if self._conn is not None:
            self._conn.close()
            self._conn = None

    def __enter__(self) -> "MemoryStore":
        return self.open()

    def __exit__(self, *exc) -> None:
        self.close()

    def record_call(
        self,
        *,
        tool_name: str,
        inputs: dict,
        output: str,
        model: str,
        duration_ms: int,
        tokens_estimated: int | None = None,
        project_root: str | None = None,
        session_id: str | None = None,
        tags: Iterable[str] | None = None,
    ) -> int:
        ts = datetime.now(timezone.utc).isoformat()
        inputs_json = json.dumps(inputs, ensure_ascii=False)
        tags_json = json.dumps(list(tags) if tags else [], ensure_ascii=False)
        c = self.conn
        cur = c.execute(
            """
            INSERT INTO calls (
                timestamp, tool_name, inputs_json, output, model,
                duration_ms, tokens_estimated, project_root, session_id, tags
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                ts, tool_name, inputs_json, output, model,
                duration_ms, tokens_estimated, project_root, session_id, tags_json,
            ),
        )
        rid = cur.lastrowid
        assert rid is not None  # AUTOINCREMENT INSERT 성공 시 보장
        c.execute(
            "INSERT INTO calls_fts (rowid, inputs_text, output_text) VALUES (?, ?, ?)",
            (
                rid,
                tokenize_for_index(inputs_json, self._tokenizer),
                tokenize_for_index(output, self._tokenizer),
            ),
        )
        c.commit()
        return rid

    def get(self, call_id: int) -> CallRecord | None:
        row = self.conn.execute(
            "SELECT * FROM calls WHERE id = ?", (call_id,)
        ).fetchone()
        return _row_to_record(row) if row else None

    def count(self) -> int:
        return self.conn.execute("SELECT COUNT(*) FROM calls").fetchone()[0]


def _row_to_record(row: sqlite3.Row) -> CallRecord:
    raw_tags = row["tags"]
    try:
        tags = tuple(json.loads(raw_tags) if raw_tags else [])
    except (json.JSONDecodeError, TypeError):
        tags = ()
    return CallRecord(
        id=row["id"],
        timestamp=row["timestamp"],
        tool_name=row["tool_name"],
        inputs_json=row["inputs_json"],
        output=row["output"],
        model=row["model"],
        duration_ms=row["duration_ms"],
        tokens_estimated=row["tokens_estimated"],
        project_root=row["project_root"],
        session_id=row["session_id"],
        tags=tags,
    )
