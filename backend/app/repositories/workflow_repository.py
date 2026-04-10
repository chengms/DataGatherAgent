import json
from datetime import UTC, datetime

from app.db.database import db_cursor
from app.schemas.workflow import DiscoveryCandidate, FetchedArticle, RankedArticle, WorkflowPreviewRequest


class WorkflowRepository:
    def _dump_comments_json(self, article: FetchedArticle) -> str:
        return json.dumps([item.model_dump() for item in article.comments], ensure_ascii=False)

    def _load_comments_json(self, raw: str | None) -> list[dict]:
        if not raw:
            return []
        try:
            payload = json.loads(raw)
        except json.JSONDecodeError:
            return []
        if isinstance(payload, list):
            normalized: list[dict] = []
            for item in payload:
                if not isinstance(item, dict):
                    continue
                content = item.get("content")
                if not isinstance(content, str) or not content.strip():
                    continue
                normalized.append(item)
            return normalized
        return []

    def create_job(self, payload: WorkflowPreviewRequest) -> int:
        created_at = datetime.now(UTC).isoformat()
        selected_platforms = payload.selected_platforms()
        discovery_source = payload.discovery_source or "auto"
        fetch_source = payload.fetch_source or "auto"
        with db_cursor() as (_, cursor):
            cursor.execute(
                """
                INSERT INTO workflow_job (
                    platform,
                    discovery_source,
                    fetch_source,
                    keywords_json,
                    limit_count,
                    top_k,
                    time_window_days,
                    status,
                    created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    ",".join(selected_platforms),
                    discovery_source,
                    fetch_source,
                    json.dumps(payload.keywords, ensure_ascii=False),
                    payload.limit,
                    payload.top_k,
                    payload.time_window_days,
                    "running",
                    created_at,
                ),
            )
            return int(cursor.lastrowid)

    def complete_job(
        self,
        job_id: int,
        discovered_count: int,
        fetched_count: int,
        ranked_count: int,
        status: str = "success",
    ) -> None:
        finished_at = datetime.now(UTC).isoformat()
        with db_cursor() as (_, cursor):
            cursor.execute(
                """
                UPDATE workflow_job
                SET status = ?, finished_at = ?, discovered_count = ?, fetched_count = ?, ranked_count = ?
                WHERE id = ?
                """,
                (status, finished_at, discovered_count, fetched_count, ranked_count, job_id),
            )

    def update_job_sources(self, job_id: int, discovery_source: str, fetch_source: str) -> None:
        with db_cursor() as (_, cursor):
            cursor.execute(
                """
                UPDATE workflow_job
                SET discovery_source = ?, fetch_source = ?
                WHERE id = ?
                """,
                (discovery_source, fetch_source, job_id),
            )

    def save_discovery_candidates(self, job_id: int, candidates: list[DiscoveryCandidate]) -> None:
        with db_cursor() as (_, cursor):
            cursor.executemany(
                """
                INSERT INTO discovered_candidate (
                    job_id, keyword, source_engine, title, snippet, source_url, account_name, discovered_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                [
                    (
                        job_id,
                        item.keyword,
                        item.source_engine,
                        item.title,
                        item.snippet,
                        item.source_url,
                        item.account_name,
                        item.discovered_at.isoformat(),
                    )
                    for item in candidates
                ],
            )

    def save_fetched_articles(self, job_id: int, articles: list[FetchedArticle]) -> None:
        with db_cursor() as (_, cursor):
            cursor.executemany(
                """
                INSERT INTO fetched_article (
                    job_id, keyword, platform, source_engine, content_kind, title, source_url, account_name, publish_time,
                    read_count, comment_count, content_text, content_html, source_id, comments_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                [
                    (
                        job_id,
                        item.keyword,
                        item.platform,
                        item.source_engine,
                        item.content_kind,
                        item.title,
                        item.source_url,
                        item.account_name,
                        item.publish_time.isoformat(),
                        item.read_count,
                        item.comment_count,
                        item.content_text,
                        item.content_html,
                        item.source_id,
                        self._dump_comments_json(item),
                    )
                    for item in articles
                ],
            )

    def save_ranked_articles(self, job_id: int, articles: list[RankedArticle]) -> None:
        with db_cursor() as (_, cursor):
            cursor.executemany(
                """
                INSERT INTO ranked_article (
                    job_id, keyword, platform, source_engine, content_kind, title, source_url, account_name, publish_time,
                    read_count, comment_count, relevance_score, popularity_score,
                    freshness_score, total_score, score_reason, rank_position
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                [
                    (
                        job_id,
                        item.keyword,
                        item.platform,
                        item.source_engine,
                        item.content_kind,
                        item.title,
                        item.source_url,
                        item.account_name,
                        item.publish_time.isoformat(),
                        item.read_count,
                        item.comment_count,
                        item.relevance_score,
                        item.popularity_score,
                        item.freshness_score,
                        item.total_score,
                        item.score_reason,
                        index + 1,
                    )
                    for index, item in enumerate(articles)
                ],
            )

    def list_jobs(self) -> list[dict]:
        with db_cursor() as (_, cursor):
            rows = cursor.execute(
                """
                SELECT id, platform, discovery_source, fetch_source, keywords_json, status, created_at, finished_at,
                       discovered_count, fetched_count, ranked_count
                FROM workflow_job
                ORDER BY id DESC
                """
            ).fetchall()
        return [dict(row) for row in rows]

    def get_job_ranked_articles(self, job_id: int) -> list[dict]:
        with db_cursor() as (_, cursor):
            rows = cursor.execute(
                """
                SELECT keyword, title, source_url, account_name, publish_time, read_count, comment_count,
                       platform, source_engine, content_kind,
                       relevance_score, popularity_score, freshness_score, total_score, score_reason, rank_position
                FROM ranked_article
                WHERE job_id = ?
                ORDER BY rank_position ASC
                """,
                (job_id,),
            ).fetchall()
        return [dict(row) for row in rows]

    def search_fetched_articles(
        self,
        *,
        keyword: str | None = None,
        platform: str | None = None,
        platforms: list[str] | None = None,
        content_kind: str | None = None,
        job_id: int | None = None,
        published_from: str | None = None,
        published_to: str | None = None,
        offset: int = 0,
        limit: int = 20,
    ) -> tuple[int, list[dict]]:
        where_clauses: list[str] = []
        params: list[object] = []
        if keyword:
            where_clauses.append(
                "(title LIKE ? OR content_text LIKE ? OR account_name LIKE ? OR keyword LIKE ? OR source_url LIKE ?)"
            )
            needle = f"%{keyword}%"
            params.extend([needle, needle, needle, needle, needle])
        if platform:
            where_clauses.append("platform = ?")
            params.append(platform)
        elif platforms:
            placeholders = ", ".join("?" for _ in platforms)
            where_clauses.append(f"platform IN ({placeholders})")
            params.extend(platforms)
        if content_kind:
            where_clauses.append("content_kind = ?")
            params.append(content_kind)
        if job_id is not None:
            where_clauses.append("job_id = ?")
            params.append(job_id)
        if published_from:
            where_clauses.append("publish_time >= ?")
            params.append(published_from)
        if published_to:
            where_clauses.append("publish_time <= ?")
            params.append(published_to)
        where_sql = f"WHERE {' AND '.join(where_clauses)}" if where_clauses else ""
        with db_cursor() as (_, cursor):
            total = cursor.execute(
                f"SELECT COUNT(1) AS c FROM fetched_article {where_sql}",
                tuple(params),
            ).fetchone()["c"]
            rows = cursor.execute(
                f"""
                SELECT id, job_id, keyword, platform, source_engine, content_kind, title, source_url, account_name,
                       publish_time, read_count, comment_count, content_text, content_html, source_id, comments_json
                FROM fetched_article
                {where_sql}
                ORDER BY id DESC
                LIMIT ? OFFSET ?
                """,
                (*params, limit, offset),
            ).fetchall()
        items = [dict(row) for row in rows]
        for item in items:
            item["comments"] = self._load_comments_json(item.pop("comments_json", "[]"))
        return int(total), items

    def get_fetched_article(self, article_id: int) -> dict | None:
        with db_cursor() as (_, cursor):
            row = cursor.execute(
                """
                SELECT id, job_id, keyword, platform, source_engine, content_kind, title, source_url, account_name,
                       publish_time, read_count, comment_count, content_text, content_html, source_id, comments_json
                FROM fetched_article
                WHERE id = ?
                """,
                (article_id,),
            ).fetchone()
        if row is None:
            return None
        item = dict(row)
        item["comments"] = self._load_comments_json(item.pop("comments_json", "[]"))
        return item

    def delete_fetched_article(self, article_id: int) -> dict | None:
        with db_cursor() as (_, cursor):
            row = cursor.execute(
                """
                SELECT id, job_id, title, source_url
                FROM fetched_article
                WHERE id = ?
                """,
                (article_id,),
            ).fetchone()
            if row is None:
                return None
            item = dict(row)
            cursor.execute("DELETE FROM fetched_article WHERE id = ?", (article_id,))
            cursor.execute(
                """
                DELETE FROM ranked_article
                WHERE job_id = ? AND source_url = ?
                """,
                (item["job_id"], item["source_url"]),
            )
            fetched_count = cursor.execute(
                "SELECT COUNT(1) AS c FROM fetched_article WHERE job_id = ?",
                (item["job_id"],),
            ).fetchone()["c"]
            ranked_count = cursor.execute(
                "SELECT COUNT(1) AS c FROM ranked_article WHERE job_id = ?",
                (item["job_id"],),
            ).fetchone()["c"]
            cursor.execute(
                """
                UPDATE workflow_job
                SET fetched_count = ?, ranked_count = ?
                WHERE id = ?
                """,
                (fetched_count, ranked_count, item["job_id"]),
            )
        return item


workflow_repository = WorkflowRepository()
