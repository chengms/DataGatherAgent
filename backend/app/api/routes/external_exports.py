from __future__ import annotations

from html import escape

from fastapi import APIRouter, Query, Request
from fastapi.responses import HTMLResponse

from app.adapters.html_utils import sanitize_html_fragment, text_to_html_fragment
from app.schemas.workflow import (
    ExternalArticleDetailResponse,
    ExternalArticleListResponse,
    ExternalArticleQueryEcho,
    ExternalArticleSummary,
    FetchedArticleRecord,
)
from app.services.workflow import workflow_service


router = APIRouter()


def parse_platform_filters(raw: str | None) -> list[str]:
    return [item.strip() for item in str(raw or "").split(",") if item.strip()]


def summarize_text(value: str, limit: int = 180) -> str:
    text = " ".join(str(value or "").split())
    if len(text) <= limit:
        return text
    return f"{text[:limit]}..."


def build_article_urls(request: Request, article_id: int) -> tuple[str, str]:
    data_url = str(request.url_for("external_get_article", article_id=str(article_id)))
    preview_url = str(request.url_for("external_preview_article", article_id=str(article_id)))
    return data_url, preview_url


def build_external_article_summary(request: Request, article: FetchedArticleRecord) -> ExternalArticleSummary:
    data_url, preview_url = build_article_urls(request, article.id)
    return ExternalArticleSummary(
        article_id=article.id,
        job_id=article.job_id,
        keyword=article.keyword,
        platform=article.platform,
        content_kind=article.content_kind,
        source_engine=article.source_engine,
        title=article.title,
        source_url=article.source_url,
        account_name=article.account_name,
        publish_time=article.publish_time,
        read_count=article.read_count,
        comment_count=article.comment_count,
        excerpt=summarize_text(article.content_text),
        has_html=bool((article.content_html or "").strip()),
        data_url=data_url,
        preview_url=preview_url,
    )


def build_external_article_detail(request: Request, article: FetchedArticleRecord) -> ExternalArticleDetailResponse:
    summary = build_external_article_summary(request, article)
    return ExternalArticleDetailResponse(
        **summary.model_dump(),
        content_text=article.content_text,
        content_html=article.content_html,
        source_id=article.source_id,
        comments=article.comments,
    )


def build_preview_document(article: FetchedArticleRecord) -> str:
    content_html = sanitize_html_fragment(article.content_html or "")
    if not content_html:
        content_html = text_to_html_fragment(article.content_text or "")
    comments_html = "".join(
        f"""
<article class="comment-card">
  <p class="comment-head">
    <strong>{escape(comment.nickname or '匿名用户')}</strong>
    <span>{escape(comment.publish_time or '-')}</span>
    <span>赞 {comment.like_count} · 回复 {comment.sub_comment_count}</span>
  </p>
  <p>{escape(comment.content)}</p>
</article>
"""
        for comment in article.comments
    )
    if not comments_html:
        comments_html = '<p class="empty-state">暂无评论。</p>'
    return f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>{escape(article.title)}</title>
  <style>
    :root {{
      --ink: #1f2430;
      --muted: #667085;
      --accent: #0f766e;
      --line: rgba(31, 36, 48, 0.12);
      --paper: #f9f5ee;
    }}
    body {{
      margin: 0;
      font-family: "PingFang SC", "Microsoft YaHei", sans-serif;
      color: var(--ink);
      background: linear-gradient(180deg, #fbf7ef 0%, #efe6d8 100%);
    }}
    main {{
      max-width: 980px;
      margin: 0 auto;
      padding: 32px 18px 48px;
    }}
    .panel {{
      background: rgba(255, 255, 255, 0.9);
      border: 1px solid var(--line);
      border-radius: 24px;
      padding: 24px;
      box-shadow: 0 18px 40px rgba(15, 23, 42, 0.08);
    }}
    h1 {{
      margin: 0 0 14px;
      font-size: 34px;
      line-height: 1.15;
    }}
    .meta {{
      color: var(--muted);
      line-height: 1.8;
      margin-bottom: 22px;
    }}
    .meta strong {{
      color: var(--ink);
    }}
    .content {{
      background: #fff;
      border: 1px solid var(--line);
      border-radius: 18px;
      padding: 22px;
      line-height: 1.85;
      word-break: break-word;
    }}
    .content img, .content video {{
      max-width: 100%;
      height: auto;
      border-radius: 14px;
    }}
    .content a {{
      color: var(--accent);
    }}
    .content blockquote {{
      margin: 1em 0;
      padding: 0.8em 1em;
      border-left: 4px solid rgba(15, 118, 110, 0.28);
      background: rgba(15, 118, 110, 0.06);
      border-radius: 12px;
    }}
    .comments {{
      margin-top: 24px;
      display: grid;
      gap: 14px;
    }}
    .comment-card {{
      background: #fff;
      border: 1px solid var(--line);
      border-radius: 16px;
      padding: 16px 18px;
    }}
    .comment-head {{
      display: flex;
      flex-wrap: wrap;
      gap: 10px;
      color: var(--muted);
      margin: 0 0 10px;
    }}
    .empty-state {{
      color: var(--muted);
    }}
  </style>
</head>
<body>
  <main>
    <section class="panel">
      <h1>{escape(article.title)}</h1>
      <div class="meta">
        <div><strong>平台</strong> {escape(article.platform)} · <strong>类型</strong> {escape(article.content_kind)} · <strong>来源</strong> {escape(article.source_engine)}</div>
        <div><strong>账号</strong> {escape(article.account_name)} · <strong>关键词</strong> {escape(article.keyword)}</div>
        <div><strong>发布时间</strong> {escape(article.publish_time)} · <strong>阅读</strong> {article.read_count} · <strong>评论</strong> {article.comment_count}</div>
        <div><strong>原文链接</strong> <a href="{escape(article.source_url)}" target="_blank" rel="noreferrer noopener">{escape(article.source_url)}</a></div>
      </div>
      <article class="content">{content_html or '<p class="empty-state">暂无正文内容。</p>'}</article>
      <section class="comments">
        <h2>评论区</h2>
        {comments_html}
      </section>
    </section>
  </main>
</body>
</html>"""


@router.get("/articles", response_model=ExternalArticleListResponse)
def list_external_articles(
    request: Request,
    keyword: str | None = Query(default=None, description="按标题、正文、账号、关键词或原文链接模糊搜索"),
    platforms: str | None = Query(default=None, description="平台筛选，多个值使用逗号分隔，例如 wechat,xiaohongshu"),
    content_kind: str | None = Query(default=None, description="内容类型，例如 article、note、video"),
    published_from: str | None = Query(default=None, description="发布时间起点，支持 YYYY-MM-DD 或 ISO 8601"),
    published_to: str | None = Query(default=None, description="发布时间终点，支持 YYYY-MM-DD 或 ISO 8601"),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
) -> ExternalArticleListResponse:
    platform_filters = parse_platform_filters(platforms)
    payload = workflow_service.search_fetched_articles(
        keyword=keyword,
        platforms=platform_filters,
        content_kind=content_kind,
        published_from=published_from,
        published_to=published_to,
        page=page,
        page_size=page_size,
    )
    return ExternalArticleListResponse(
        query=ExternalArticleQueryEcho(
            keyword=(keyword or "").strip() or None,
            platforms=platform_filters,
            content_kind=(content_kind or "").strip() or None,
            published_from=(published_from or "").strip() or None,
            published_to=(published_to or "").strip() or None,
            page=page,
            page_size=page_size,
        ),
        total=payload.total,
        items=[build_external_article_summary(request, item) for item in payload.items],
    )


@router.get("/articles/{article_id}", response_model=ExternalArticleDetailResponse, name="external_get_article")
def get_external_article(request: Request, article_id: int) -> ExternalArticleDetailResponse:
    article = workflow_service.get_fetched_article(article_id)
    return build_external_article_detail(request, article)


@router.get(
    "/articles/{article_id}/preview",
    response_class=HTMLResponse,
    include_in_schema=False,
    name="external_preview_article",
)
def preview_external_article(article_id: int) -> HTMLResponse:
    article = workflow_service.get_fetched_article(article_id)
    return HTMLResponse(build_preview_document(article))
