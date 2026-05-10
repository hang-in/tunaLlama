-- tunaLlama 메모리 저장소 스키마.
--
-- FTS5 트리거를 의도적으로 두지 않는다. 한국어 형태소 사전 토큰화는
-- application 레이어(`tokenize.py`)에서만 수행하므로, write 시점에 두 테이블에
-- 명시적으로 INSERT 하는 게 더 단순하고 가시적이다.

CREATE TABLE IF NOT EXISTS calls (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp TEXT NOT NULL,           -- ISO 8601 (UTC)
    tool_name TEXT NOT NULL,           -- 'generate_code', 'review_file' 등
    inputs_json TEXT NOT NULL,         -- 입력 직렬화
    output TEXT NOT NULL,              -- 모델 raw 응답
    model TEXT NOT NULL,
    duration_ms INTEGER NOT NULL,
    tokens_estimated INTEGER,
    project_root TEXT,                 -- 호출 시점 CWD 절대 경로
    session_id TEXT,
    tags TEXT NOT NULL DEFAULT '[]',   -- JSON 배열
    embedding BLOB                     -- Phase 2: float32 × 1024 (BGE-M3). NULL 허용.
);

CREATE INDEX IF NOT EXISTS idx_calls_timestamp ON calls(timestamp);
CREATE INDEX IF NOT EXISTS idx_calls_project_root ON calls(project_root);
CREATE INDEX IF NOT EXISTS idx_calls_tool_name ON calls(tool_name);

-- FTS5 standalone (external content X). rowid 를 calls.id 와 1:1 로 맞춘다.
CREATE VIRTUAL TABLE IF NOT EXISTS calls_fts USING fts5(
    inputs_text,
    output_text,
    tokenize='unicode61 remove_diacritics 2'
);

-- Phase 2-3: rule-based 그래프 엣지. ``source_id < target_id`` 로 정규화.
CREATE TABLE IF NOT EXISTS graph_edges (
    source_id INTEGER NOT NULL,
    target_id INTEGER NOT NULL,
    relation TEXT NOT NULL,
    created_at TEXT NOT NULL,
    PRIMARY KEY (source_id, target_id, relation)
);
CREATE INDEX IF NOT EXISTS idx_graph_edges_source ON graph_edges(source_id);
CREATE INDEX IF NOT EXISTS idx_graph_edges_target ON graph_edges(target_id);
