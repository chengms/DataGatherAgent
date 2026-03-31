from app.db.database import db_cursor


SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS workflow_job (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    platform TEXT NOT NULL,
    discovery_source TEXT NOT NULL,
    keywords_json TEXT NOT NULL,
    limit_count INTEGER NOT NULL,
    top_k INTEGER NOT NULL,
    time_window_days INTEGER NOT NULL,
    status TEXT NOT NULL,
    created_at TEXT NOT NULL,
    finished_at TEXT,
    discovered_count INTEGER NOT NULL DEFAULT 0,
    fetched_count INTEGER NOT NULL DEFAULT 0,
    ranked_count INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS discovered_candidate (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    job_id INTEGER NOT NULL,
    keyword TEXT NOT NULL,
    source_engine TEXT NOT NULL,
    title TEXT NOT NULL,
    snippet TEXT NOT NULL,
    source_url TEXT NOT NULL,
    account_name TEXT NOT NULL,
    discovered_at TEXT NOT NULL,
    FOREIGN KEY(job_id) REFERENCES workflow_job(id)
);

CREATE TABLE IF NOT EXISTS fetched_article (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    job_id INTEGER NOT NULL,
    keyword TEXT NOT NULL,
    platform TEXT NOT NULL,
    title TEXT NOT NULL,
    source_url TEXT NOT NULL,
    account_name TEXT NOT NULL,
    publish_time TEXT NOT NULL,
    read_count INTEGER NOT NULL,
    comment_count INTEGER NOT NULL,
    content_text TEXT NOT NULL,
    source_id TEXT NOT NULL,
    FOREIGN KEY(job_id) REFERENCES workflow_job(id)
);

CREATE TABLE IF NOT EXISTS ranked_article (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    job_id INTEGER NOT NULL,
    keyword TEXT NOT NULL,
    title TEXT NOT NULL,
    source_url TEXT NOT NULL,
    account_name TEXT NOT NULL,
    publish_time TEXT NOT NULL,
    read_count INTEGER NOT NULL,
    comment_count INTEGER NOT NULL,
    relevance_score REAL NOT NULL,
    popularity_score REAL NOT NULL,
    freshness_score REAL NOT NULL,
    total_score REAL NOT NULL,
    score_reason TEXT NOT NULL,
    rank_position INTEGER NOT NULL,
    FOREIGN KEY(job_id) REFERENCES workflow_job(id)
);
"""


def init_db() -> None:
    with db_cursor() as (_, cursor):
        cursor.executescript(SCHEMA_SQL)


_initialized = False


def ensure_db_initialized() -> None:
    global _initialized
    if _initialized:
        return
    init_db()
    _initialized = True
