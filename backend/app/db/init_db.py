from app.db.database import db_cursor


SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS workflow_job (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    platform TEXT NOT NULL,
    discovery_source TEXT NOT NULL,
    fetch_source TEXT NOT NULL DEFAULT 'mock_wechat_fetch',
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
    source_engine TEXT NOT NULL DEFAULT '',
    content_kind TEXT NOT NULL DEFAULT 'article',
    title TEXT NOT NULL,
    source_url TEXT NOT NULL,
    account_name TEXT NOT NULL,
    publish_time TEXT NOT NULL,
    read_count INTEGER NOT NULL,
    comment_count INTEGER NOT NULL,
    content_text TEXT NOT NULL,
    content_html TEXT NOT NULL DEFAULT '',
    source_id TEXT NOT NULL,
    comments_json TEXT NOT NULL DEFAULT '[]',
    FOREIGN KEY(job_id) REFERENCES workflow_job(id)
);

CREATE TABLE IF NOT EXISTS ranked_article (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    job_id INTEGER NOT NULL,
    keyword TEXT NOT NULL,
    platform TEXT NOT NULL DEFAULT '',
    source_engine TEXT NOT NULL DEFAULT '',
    content_kind TEXT NOT NULL DEFAULT 'article',
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
        workflow_columns = {row[1] for row in cursor.execute("PRAGMA table_info(workflow_job)").fetchall()}
        if "fetch_source" not in workflow_columns:
            cursor.execute(
                "ALTER TABLE workflow_job ADD COLUMN fetch_source TEXT NOT NULL DEFAULT 'mock_wechat_fetch'"
            )
        fetched_columns = {row[1] for row in cursor.execute("PRAGMA table_info(fetched_article)").fetchall()}
        if "source_engine" not in fetched_columns:
            cursor.execute("ALTER TABLE fetched_article ADD COLUMN source_engine TEXT NOT NULL DEFAULT ''")
        if "content_kind" not in fetched_columns:
            cursor.execute("ALTER TABLE fetched_article ADD COLUMN content_kind TEXT NOT NULL DEFAULT 'article'")
        if "comments_json" not in fetched_columns:
            cursor.execute("ALTER TABLE fetched_article ADD COLUMN comments_json TEXT NOT NULL DEFAULT '[]'")
        if "content_html" not in fetched_columns:
            cursor.execute("ALTER TABLE fetched_article ADD COLUMN content_html TEXT NOT NULL DEFAULT ''")
        ranked_columns = {row[1] for row in cursor.execute("PRAGMA table_info(ranked_article)").fetchall()}
        if "platform" not in ranked_columns:
            cursor.execute("ALTER TABLE ranked_article ADD COLUMN platform TEXT NOT NULL DEFAULT ''")
        if "source_engine" not in ranked_columns:
            cursor.execute("ALTER TABLE ranked_article ADD COLUMN source_engine TEXT NOT NULL DEFAULT ''")
        if "content_kind" not in ranked_columns:
            cursor.execute("ALTER TABLE ranked_article ADD COLUMN content_kind TEXT NOT NULL DEFAULT 'article'")
        job_ids = [row[0] for row in cursor.execute("SELECT id FROM workflow_job").fetchall()]
        for job_id in job_ids:
            discovery_row = cursor.execute(
                """
                SELECT GROUP_CONCAT(DISTINCT source_engine)
                FROM discovered_candidate
                WHERE job_id = ? AND source_engine <> ''
                """,
                (job_id,),
            ).fetchone()
            fetch_row = cursor.execute(
                """
                SELECT GROUP_CONCAT(DISTINCT source_engine)
                FROM fetched_article
                WHERE job_id = ? AND source_engine <> ''
                """,
                (job_id,),
            ).fetchone()
            discovery_source = discovery_row[0] if discovery_row and discovery_row[0] else None
            fetch_source = fetch_row[0] if fetch_row and fetch_row[0] else None
            if discovery_source or fetch_source:
                cursor.execute(
                    """
                    UPDATE workflow_job
                    SET discovery_source = COALESCE(?, discovery_source),
                        fetch_source = COALESCE(?, fetch_source)
                    WHERE id = ?
                    """,
                    (discovery_source, fetch_source, job_id),
                )
        mock_job_ids = [
            row[0]
            for row in cursor.execute(
                """
                SELECT DISTINCT id
                FROM workflow_job
                WHERE discovery_source LIKE '%mock_%'
                   OR fetch_source LIKE '%mock_%'
                UNION
                SELECT DISTINCT job_id
                FROM discovered_candidate
                WHERE source_engine LIKE 'mock_%'
                UNION
                SELECT DISTINCT job_id
                FROM fetched_article
                WHERE source_engine LIKE 'mock_%'
                UNION
                SELECT DISTINCT job_id
                FROM ranked_article
                WHERE source_engine LIKE 'mock_%'
                """
            ).fetchall()
        ]
        if mock_job_ids:
            placeholders = ",".join("?" for _ in mock_job_ids)
            cursor.execute(f"DELETE FROM ranked_article WHERE job_id IN ({placeholders})", tuple(mock_job_ids))
            cursor.execute(f"DELETE FROM fetched_article WHERE job_id IN ({placeholders})", tuple(mock_job_ids))
            cursor.execute(f"DELETE FROM discovered_candidate WHERE job_id IN ({placeholders})", tuple(mock_job_ids))
            cursor.execute(f"DELETE FROM workflow_job WHERE id IN ({placeholders})", tuple(mock_job_ids))


_initialized = False


def ensure_db_initialized() -> None:
    global _initialized
    if _initialized:
        return
    init_db()
    _initialized = True
