"""Lưu trữ SQLite. Mọi bảng dùng khóa tự nhiên hoặc khóa băm, nên chạy lại hay gộp từ nhiều máy không sinh bản trùng."""

from __future__ import annotations

import sqlite3
from pathlib import Path

SCHEMA_VERSION = 1

SCHEMA = """
CREATE TABLE IF NOT EXISTS meta (
  key TEXT PRIMARY KEY,
  value TEXT
);

CREATE TABLE IF NOT EXISTS runs (
  run_id TEXT PRIMARY KEY,
  flow TEXT,
  step_index INTEGER,
  stage TEXT NOT NULL,
  params_json TEXT NOT NULL,
  config_hash TEXT NOT NULL,
  host TEXT,
  code_version TEXT,
  started_at TEXT NOT NULL,
  finished_at TEXT,
  status TEXT,
  summary_json TEXT
);

CREATE TABLE IF NOT EXISTS prompts (
  prompt_id TEXT PRIMARY KEY,          -- sha256(text)
  text TEXT NOT NULL,
  source TEXT NOT NULL,
  source_ref TEXT,
  language TEXT NOT NULL DEFAULT 'python',
  created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS prompt_tags (
  prompt_id TEXT NOT NULL,
  tag TEXT NOT NULL,
  PRIMARY KEY (prompt_id, tag)
);
CREATE INDEX IF NOT EXISTS idx_prompt_tags_tag ON prompt_tags(tag);

CREATE TABLE IF NOT EXISTS generations (
  gen_id TEXT PRIMARY KEY,             -- sha256(prompt_id|parent|model_key|task|params_hash|sample_idx)
  prompt_id TEXT NOT NULL,
  parent_gen_id TEXT,
  task_id TEXT NOT NULL,
  model_key TEXT NOT NULL,
  backend TEXT NOT NULL,
  model_name TEXT NOT NULL,
  params_json TEXT NOT NULL,
  params_hash TEXT NOT NULL,
  sample_idx INTEGER NOT NULL,
  seed INTEGER,
  response_text TEXT,
  reasoning_text TEXT,
  finish_reason TEXT,
  tokens_in INTEGER,
  tokens_out INTEGER,
  latency_ms INTEGER,
  error TEXT,
  attempts INTEGER NOT NULL DEFAULT 1,
  host TEXT,
  run_id TEXT,
  created_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_gen_prompt ON generations(prompt_id);
CREATE INDEX IF NOT EXISTS idx_gen_model_task ON generations(model_key, task_id);
CREATE INDEX IF NOT EXISTS idx_gen_parent ON generations(parent_gen_id);

CREATE TABLE IF NOT EXISTS extract_done (
  gen_id TEXT NOT NULL,
  extractor_version TEXT NOT NULL,
  n_mentions INTEGER NOT NULL,
  run_id TEXT,
  PRIMARY KEY (gen_id, extractor_version)
);

CREATE TABLE IF NOT EXISTS mentions (
  gen_id TEXT NOT NULL,
  extractor_version TEXT NOT NULL,
  method TEXT NOT NULL,                -- pip_install | llm_list | import | requirements
  norm_name TEXT NOT NULL,             -- normalize_pep426_name của PyPI
  raw TEXT NOT NULL,
  module TEXT,                         -- tên module (chỉ với method = import)
  ultra_name TEXT NOT NULL,            -- ultranormalize_name của PyPI
  valid_name INTEGER NOT NULL,         -- khớp PROJECT_NAME_RE
  PRIMARY KEY (gen_id, extractor_version, method, norm_name)
);
CREATE INDEX IF NOT EXISTS idx_mentions_name ON mentions(norm_name);

CREATE TABLE IF NOT EXISTS pypi_snapshots (
  snapshot_id TEXT PRIMARY KEY,
  fetched_at TEXT NOT NULL,
  source TEXT NOT NULL,
  api_version TEXT,
  last_serial INTEGER,
  n_projects INTEGER NOT NULL
);

CREATE TABLE IF NOT EXISTS pypi_index (
  snapshot_id TEXT NOT NULL,
  norm_name TEXT NOT NULL,
  name TEXT NOT NULL,
  ultra_name TEXT NOT NULL,
  PRIMARY KEY (snapshot_id, norm_name)
);
CREATE INDEX IF NOT EXISTS idx_pypi_index_ultra ON pypi_index(snapshot_id, ultra_name);

CREATE TABLE IF NOT EXISTS package_status (
  norm_name TEXT NOT NULL,
  snapshot_id TEXT NOT NULL,
  exists_on_pypi INTEGER NOT NULL,
  registrable INTEGER NOT NULL,
  reason TEXT,                         -- invalid | stdlib | existing | similar
  similar_to TEXT,
  rules_version TEXT NOT NULL,
  checked_at TEXT NOT NULL,
  PRIMARY KEY (norm_name, snapshot_id)
);

CREATE TABLE IF NOT EXISTS metadata_raw (
  norm_name TEXT NOT NULL,
  source TEXT NOT NULL,                -- pypi_json | pypi_provenance | pypistats | github
  fetched_at TEXT NOT NULL,
  http_status INTEGER,
  raw_json TEXT,
  error TEXT,
  PRIMARY KEY (norm_name, source)
);

CREATE TABLE IF NOT EXISTS package_features (
  norm_name TEXT PRIMARY KEY,
  computed_at TEXT NOT NULL,
  pypi_name TEXT,
  summary TEXT,
  description_len INTEGER,
  first_release_at TEXT,
  last_release_at TEXT,
  n_releases INTEGER,
  n_files INTEGER,
  all_yanked INTEGER,
  n_owners INTEGER,
  has_organization INTEGER,
  has_project_urls INTEGER,
  github_repo TEXT,
  provenance_kind TEXT,
  provenance_repo TEXT,
  source_repo_verified INTEGER,
  downloads_last_month INTEGER,
  github_stars INTEGER,
  github_created_at TEXT,
  github_archived INTEGER
);

CREATE TABLE IF NOT EXISTS known_lists (
  list_id TEXT NOT NULL,
  norm_name TEXT NOT NULL,
  raw_name TEXT NOT NULL,
  extra_json TEXT,
  fetched_at TEXT NOT NULL,
  PRIMARY KEY (list_id, norm_name)
);

CREATE TABLE IF NOT EXISTS labels (
  norm_name TEXT NOT NULL,
  labeler_version TEXT NOT NULL,
  label TEXT NOT NULL,
  rule TEXT NOT NULL,
  needs_review INTEGER NOT NULL,
  evidence_json TEXT,
  run_id TEXT,
  labeled_at TEXT NOT NULL,
  PRIMARY KEY (norm_name, labeler_version)
);

CREATE TABLE IF NOT EXISTS selections (
  selection_id TEXT NOT NULL,
  norm_name TEXT NOT NULL,
  model_key TEXT NOT NULL,
  prompt_id TEXT NOT NULL,
  label TEXT,
  run_id TEXT,
  PRIMARY KEY (selection_id, norm_name, model_key, prompt_id)
);
"""

VIEWS = """
DROP VIEW IF EXISTS v_mentions;
CREATE VIEW v_mentions AS
SELECT m.gen_id, m.extractor_version, m.method, m.norm_name, m.raw, m.module, m.ultra_name, m.valid_name,
       g.prompt_id, g.model_key, g.task_id, g.parent_gen_id,
       COALESCE(p.sample_idx, g.sample_idx) AS root_sample_idx
FROM mentions m
JOIN generations g ON g.gen_id = m.gen_id
LEFT JOIN generations p ON p.gen_id = g.parent_gen_id;

DROP VIEW IF EXISTS v_latest_snapshot;
CREATE VIEW v_latest_snapshot AS
SELECT snapshot_id FROM pypi_snapshots ORDER BY fetched_at DESC, snapshot_id DESC LIMIT 1;
"""

# Thứ tự gộp; generations xử lý riêng (ưu tiên bản thành công).
MERGE_TABLES = (
    "runs",
    "prompts",
    "prompt_tags",
    "extract_done",
    "mentions",
    "pypi_snapshots",
    "pypi_index",
    "package_status",
    "metadata_raw",
    "package_features",
    "known_lists",
    "labels",
    "selections",
)


def connect(path: Path | str) -> sqlite3.Connection:
    p = Path(path)
    if str(p) != ":memory:":
        p.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(p), timeout=60)
    conn.row_factory = sqlite3.Row
    # Chế độ journal mặc định (DELETE): chỉ một file .sqlite, dễ mang giữa các máy.
    # synchronous = FULL: mất điện / tắt cứng máy giữa lúc ghi cũng không hỏng file
    # (NORMAL ở chế độ DELETE còn một xác suất nhỏ hỏng file). Ghi ~15 giây một lần nên không chậm đáng kể.
    conn.execute("PRAGMA synchronous = FULL")
    conn.executescript(SCHEMA)
    conn.executescript(VIEWS)
    cur = conn.execute("SELECT value FROM meta WHERE key = 'schema_version'")
    row = cur.fetchone()
    if row is None:
        conn.execute("INSERT INTO meta(key, value) VALUES ('schema_version', ?)", (str(SCHEMA_VERSION),))
    elif int(row[0]) != SCHEMA_VERSION:
        raise RuntimeError(f"{path}: schema_version {row[0]} khác bản code ({SCHEMA_VERSION})")
    conn.commit()
    return conn


def table_columns(conn: sqlite3.Connection, table: str, schema: str = "main") -> list[str]:
    return [r[1] for r in conn.execute(f"PRAGMA {schema}.table_info({table})")]


def latest_snapshot(conn: sqlite3.Connection) -> str | None:
    row = conn.execute("SELECT snapshot_id FROM v_latest_snapshot").fetchone()
    return row[0] if row else None


def merge_from(conn: sqlite3.Connection, other: Path | str) -> dict[str, int]:
    """Gộp dữ liệu từ một file SQLite khác vào CSDL hiện tại. Trả về số dòng mới mỗi bảng."""
    other = Path(other)
    if not other.exists():
        raise FileNotFoundError(other)
    # Kiểm tra phiên bản schema của file nguồn trước khi gộp.
    src = sqlite3.connect(f"file:{other}?mode=ro", uri=True)
    try:
        row = src.execute("SELECT value FROM meta WHERE key = 'schema_version'").fetchone()
    finally:
        src.close()
    if row is None or int(row[0]) != SCHEMA_VERSION:
        raise RuntimeError(f"{other}: schema_version {row[0] if row else None} khác bản code ({SCHEMA_VERSION})")

    conn.commit()
    conn.execute("ATTACH DATABASE ? AS src", (f"file:{other}?mode=ro",))
    added: dict[str, int] = {}
    try:
        with conn:
            # generations: thêm mới; nếu đã có bản lỗi mà nguồn có bản thành công thì thay.
            cols = table_columns(conn, "generations")
            col_list = ", ".join(cols)
            before = conn.total_changes
            updates = ", ".join(f"{c} = excluded.{c}" for c in cols if c != "gen_id")
            conn.execute(
                f"INSERT INTO main.generations ({col_list}) SELECT {col_list} FROM src.generations WHERE true "
                f"ON CONFLICT(gen_id) DO UPDATE SET {updates} "
                f"WHERE main.generations.error IS NOT NULL AND excluded.error IS NULL"
            )
            added["generations"] = conn.total_changes - before
            for t in MERGE_TABLES:
                cols = [c for c in table_columns(conn, t) if c in set(table_columns(conn, t, "src"))]
                col_list = ", ".join(cols)
                before = conn.total_changes
                conn.execute(f"INSERT OR IGNORE INTO main.{t} ({col_list}) SELECT {col_list} FROM src.{t}")
                added[t] = conn.total_changes - before
    finally:
        conn.execute("DETACH DATABASE src")
    return added
