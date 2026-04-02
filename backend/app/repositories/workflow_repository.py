import json
from datetime import UTC, datetime

from app.db.database import db_cursor
from app.schemas.workflow import DiscoveryCandidate, FetchedArticle, RankedArticle, WorkflowPreviewRequest


class WorkflowRepository:
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
                    job_id, keyword, platform, title, source_url, account_name, publish_time,
                    read_count, comment_count, content_text, source_id
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                [
                    (
                        job_id,
                        item.keyword,
                        item.platform,
                        item.title,
                        item.source_url,
                        item.account_name,
                        item.publish_time.isoformat(),
                        item.read_count,
                        item.comment_count,
                        item.content_text,
                        item.source_id,
                    )
                    for item in articles
                ],
            )

    def save_ranked_articles(self, job_id: int, articles: list[RankedArticle]) -> None:
        with db_cursor() as (_, cursor):
            cursor.executemany(
                """
                INSERT INTO ranked_article (
                    job_id, keyword, title, source_url, account_name, publish_time,
                    read_count, comment_count, relevance_score, popularity_score,
                    freshness_score, total_score, score_reason, rank_position
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                [
                    (
                        job_id,
                        item.keyword,
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
                       relevance_score, popularity_score, freshness_score, total_score, score_reason, rank_position
                FROM ranked_article
                WHERE job_id = ?
                ORDER BY rank_position ASC
                """,
                (job_id,),
            ).fetchall()
        return [dict(row) for row in rows]


workflow_repository = WorkflowRepository()
