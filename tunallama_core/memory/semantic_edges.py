"""Phase 3-2 — LLM-derived 페어 관계 (`semantic_related`).

binary 분류 (`RELATED` / `UNRELATED`). small-prompt + single-token 패턴 —
Phase 1.5 의 stage-2 classifier 와 같은 검증된 형태. 모든 모델이 학습된 분포에
정합한 한 단어 출력.

비용 방어:
- ``max_pairs`` 한도 (기본 100).
- ``project_root`` 좁힘 — 같은 project 안 record 페어만 분류.
- 이미 ``semantic_related`` 로 등록된 페어 skip (idempotent).
"""

from __future__ import annotations

import re
from collections import defaultdict
from datetime import datetime, timezone

from ..llm.base import LLMClient
from .store import CallRecord, MemoryStore

_SEMANTIC_RELATION = "semantic_related"

_CLASSIFIER_SYS = "You output one token: RELATED or UNRELATED. Nothing else."
_CLASSIFIER_USER_TMPL = (
    "Record A:\n{a_inputs}\n→ {a_output}\n\n"
    "Record B:\n{b_inputs}\n→ {b_output}\n\n"
    "Do these two records cover the same task, or does one fix/extend the other? "
    "Output RELATED or UNRELATED."
)
_VERDICT_RE = re.compile(r"\b(RELATED|UNRELATED)\b", re.IGNORECASE)

_TRUNCATE = 300


def classify_pair(
    client: LLMClient, a: CallRecord, b: CallRecord
) -> bool | None:
    """``True`` (related) / ``False`` (unrelated) / ``None`` (파싱 실패)."""
    user = _CLASSIFIER_USER_TMPL.format(
        a_inputs=a.inputs_json[:_TRUNCATE],
        a_output=a.output[:_TRUNCATE],
        b_inputs=b.inputs_json[:_TRUNCATE],
        b_output=b.output[:_TRUNCATE],
    )
    try:
        resp = client.chat(system=_CLASSIFIER_SYS, prompt=user)
    except Exception:  # noqa: BLE001 — LLM 호출 실패는 None 으로 흡수
        return None
    m = _VERDICT_RE.search(resp.text or "")
    if not m:
        return None
    return m.group(1).upper() == "RELATED"


def _load_records_grouped(
    store: MemoryStore, *, project_root: str | None
) -> dict[str, list[CallRecord]]:
    where = ""
    params: tuple = ()
    if project_root:
        where = "WHERE project_root = ?"
        params = (project_root,)
    rows = store.conn.execute(
        f"SELECT * FROM calls {where} ORDER BY id", params
    ).fetchall()
    groups: dict[str, list[CallRecord]] = defaultdict(list)
    for row in rows:
        rec = _row_to_record(row)
        # project_root 가 NULL 인 record 는 그룹화 대상 X (cross-project 페어 거름).
        if rec.project_root is not None:
            groups[rec.project_root].append(rec)
    return groups


def _row_to_record(row) -> CallRecord:
    import json
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


def build_semantic_edges(
    store: MemoryStore,
    client: LLMClient,
    *,
    max_pairs: int = 100,
    project_root: str | None = None,
) -> int:
    """같은 ``project_root`` record 페어를 LLM 으로 분류 → ``semantic_related`` 엣지.

    분류된 페어 카운트(엣지 추가/skip 무관) 는 ``max_pairs`` 까지. 이미
    ``semantic_related`` 로 등록된 (id_a, id_b) 페어는 LLM 호출 자체 skip.
    반환: 새로 추가된 엣지 수.
    """
    groups = _load_records_grouped(store, project_root=project_root)
    now = datetime.now(timezone.utc).isoformat()

    classified = 0
    inserted = 0
    conn = store.conn

    # 이미 등록된 semantic_related (a,b) 쌍 미리 fetch.
    existing = {
        (row["source_id"], row["target_id"])
        for row in conn.execute(
            "SELECT source_id, target_id FROM graph_edges WHERE relation = ?",
            (_SEMANTIC_RELATION,),
        ).fetchall()
    }

    for _root, recs in groups.items():
        for i in range(len(recs)):
            for j in range(i + 1, len(recs)):
                if classified >= max_pairs:
                    return inserted
                a, b = recs[i], recs[j]
                src_id = min(a.id, b.id)
                tgt_id = max(a.id, b.id)
                if (src_id, tgt_id) in existing:
                    continue
                rec_a, rec_b = (a, b) if a.id < b.id else (b, a)
                verdict = classify_pair(client, rec_a, rec_b)
                classified += 1
                if verdict is True:
                    with store._lock:  # noqa: SLF001
                        conn.execute(
                            """
                            INSERT OR IGNORE INTO graph_edges
                                (source_id, target_id, relation, created_at)
                            VALUES (?, ?, ?, ?)
                            """,
                            (src_id, tgt_id, _SEMANTIC_RELATION, now),
                        )
                        conn.commit()
                    inserted += 1
                    existing.add((src_id, tgt_id))
    return inserted
