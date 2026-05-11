"""SQLite 기반 호출 기록 저장소.

단일 스레드 사용 가정. ``with MemoryStore(path) as store:`` 패턴 권장.
"""

from __future__ import annotations

import json
import sqlite3
import threading
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from ..errors import MemoryStoreError
from .tokenize import tokenize_for_index
from .vector import VectorHit, decode_blob, encode_blob

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
        self,
        db_path: Path | str,
        *,
        korean_tokenizer: str = "kiwi",
        enable_embeddings: bool = True,
    ) -> None:
        self._path = Path(db_path) if db_path != ":memory:" else None
        self._raw_path = str(db_path)
        self._tokenizer = korean_tokenizer
        self._enable_embeddings = enable_embeddings
        self._conn: sqlite3.Connection | None = None
        # FastMCP 가 도구를 별도 스레드에서 호출할 수 있어 ``check_same_thread=False`` +
        # 단일 lock 으로 write 직렬화. SQLite WAL/journal 만으로는 sqlite3 의 thread
        # 검사를 우회 못 함.
        self._lock = threading.Lock()

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
        self._conn = sqlite3.connect(self._raw_path, check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        # WAL — read 와 write 가 동시 진행 가능. 파일 DB 만 의미.
        if self._path is not None:
            try:
                self._conn.execute("PRAGMA journal_mode=WAL")
            except sqlite3.OperationalError:
                pass  # :memory: 등 WAL 미지원이면 무시
        self._conn.executescript(_SCHEMA_PATH.read_text(encoding="utf-8"))
        self._migrate_embedding_column()
        self._migrate_target_file_path_column()
        return self

    def _migrate_embedding_column(self) -> None:
        """Phase 2: 옛 db 에 ``embedding`` 컬럼이 없으면 ALTER 로 추가.

        SQLite 의 ``ALTER TABLE ADD COLUMN IF NOT EXISTS`` 가 없어 try/except 로 처리.
        새 db 는 schema.sql 이 이미 컬럼을 포함하므로 OperationalError 가 나며 그대로 통과.
        """
        try:
            self.conn.execute("ALTER TABLE calls ADD COLUMN embedding BLOB")
            self.conn.commit()
        except sqlite3.OperationalError:
            pass  # 이미 있으면 OK

    def _migrate_target_file_path_column(self) -> None:
        """Phase 6-3: ``calls.target_file_path`` 컬럼 - delegation 결과가 쓰인
        파일 경로. diff-based learning 의 anchor.
        """
        try:
            self.conn.execute(
                "ALTER TABLE calls ADD COLUMN target_file_path TEXT"
            )
            self.conn.commit()
        except sqlite3.OperationalError:
            pass

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
        target_file_path: str | None = None,
    ) -> int:
        ts = datetime.now(timezone.utc).isoformat()
        inputs_json = json.dumps(inputs, ensure_ascii=False)
        tags_json = json.dumps(list(tags) if tags else [], ensure_ascii=False)
        embedding_blob = self._compute_embedding_blob(inputs_json, output)
        c = self.conn
        with self._lock:
            cur = c.execute(
                """
                INSERT INTO calls (
                    timestamp, tool_name, inputs_json, output, model,
                    duration_ms, tokens_estimated, project_root, session_id, tags,
                    embedding, target_file_path
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    ts, tool_name, inputs_json, output, model,
                    duration_ms, tokens_estimated, project_root, session_id, tags_json,
                    embedding_blob, target_file_path,
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

    def set_target_file_path(self, call_id: int, path: str) -> None:
        """기존 call 의 target_file_path 사후 설정 - delegation 후 사용자/Claude
        가 결과를 파일에 쓴 시점에 link.
        """
        with self._lock:
            self.conn.execute(
                "UPDATE calls SET target_file_path = ? WHERE id = ?",
                (path, call_id),
            )
            self.conn.commit()

    def get_target_file_path(self, call_id: int) -> str | None:
        row = self.conn.execute(
            "SELECT target_file_path FROM calls WHERE id = ?", (call_id,)
        ).fetchone()
        return row["target_file_path"] if row else None

    def _compute_embedding_blob(self, inputs_json: str, output: str) -> bytes | None:
        """임베딩 계산 시도. ``enable_embeddings=False`` 거나 실패 시 ``None``.

        ``enable_embeddings=False`` 면 BGE-M3 모델 자체 로드 안 함 (GPU 메모리 0).
        모델 import / 다운로드 / 추론 실패 어느 쪽이든 BM25 흐름은 영향 없게.
        """
        if not self._enable_embeddings:
            return None
        try:
            from .vector import embed
        except ImportError:
            return None
        try:
            vec = embed(f"{inputs_json} {output}")
            return encode_blob(vec)
        except Exception:  # noqa: BLE001 - 모델 호출 실패는 옵션 기능 정지로 흡수
            return None

    def search_vectors(
        self,
        query: str,
        *,
        limit: int = 5,
        project_root: str | None = None,
    ) -> list[VectorHit]:
        """Phase 2 — cosine 유사도 기반 의미 검색.

        ``embedding IS NOT NULL`` 인 record 만 대상. brute-force (numpy dot
        product). 1 만 record 까지는 충분히 빠름.
        임베딩 모델 로드/호출이 실패하면 빈 리스트 반환 — BM25 fallback 은 호출자 몫.
        """
        if limit <= 0 or not self._enable_embeddings:
            return []
        try:
            from .vector import embed
            query_vec = embed(query)
        except Exception:  # noqa: BLE001
            return []

        where = "embedding IS NOT NULL"
        params: list = []
        if project_root:
            where += " AND project_root = ?"
            params.append(project_root)

        sql = (
            "SELECT id, embedding, inputs_json, output, tool_name, timestamp "
            f"FROM calls WHERE {where}"
        )
        rows = self.conn.execute(sql, params).fetchall()

        hits: list[VectorHit] = []
        for row in rows:
            vec = decode_blob(row["embedding"])
            if vec is None:
                continue
            score = float(query_vec @ vec)  # cosine — 양쪽 모두 L2 정규화됨
            inputs = row["inputs_json"]
            output = row["output"]
            hits.append(
                VectorHit(
                    id=row["id"],
                    score=score,
                    inputs_summary=(inputs or "")[:100],
                    output_excerpt=(output or "")[:200],
                    tool_name=row["tool_name"],
                    timestamp=row["timestamp"],
                )
            )
        hits.sort(key=lambda h: h.score, reverse=True)
        return hits[:limit]

    def get(self, call_id: int) -> CallRecord | None:
        row = self.conn.execute(
            "SELECT * FROM calls WHERE id = ?", (call_id,)
        ).fetchone()
        return _row_to_record(row) if row else None

    def get_embeddings_for_ids(self, ids):
        """주어진 id list 의 embedding 벡터 dict 로 반환. 없는 id 는 누락.

        MMR / 다양성 reranking 용. ``ids`` 빈 list 면 빈 dict.
        """
        if not ids:
            return {}
        placeholders = ",".join("?" * len(ids))
        sql = f"SELECT id, embedding FROM calls WHERE id IN ({placeholders})"
        out: dict = {}  # values are numpy.ndarray (BGE-M3 1024 float32)
        for row in self.conn.execute(sql, list(ids)).fetchall():
            vec = decode_blob(row["embedding"])
            if vec is not None:
                out[row["id"]] = vec
        return out

    def embed_query(self, query: str):
        """query 를 BGE-M3 로 임베딩. embedding 비활성/실패 시 None."""
        if not self._enable_embeddings:
            return None
        try:
            from .vector import embed
            return embed(query)
        except Exception:  # noqa: BLE001
            return None

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
