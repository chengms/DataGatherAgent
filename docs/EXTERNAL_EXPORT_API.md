# External Export API

## Purpose

This API exposes locally stored crawl results to external systems in a stable REST form.

Base URL:

- `http://127.0.0.1:8000`

Versioned prefix:

- `http://127.0.0.1:8000/api/external/v1`

Interactive OpenAPI docs:

- `http://127.0.0.1:8000/docs`

## Endpoints

### `GET /api/external/v1/articles`

Search local crawl results and return data links, preview links, and article metadata.

Supported query parameters:

- `keyword`
  - Fuzzy matches title, content, account name, original keyword, and source URL.
- `platforms`
  - Comma-separated platform list, for example `wechat,xiaohongshu`.
- `content_kind`
  - Optional content type such as `article`, `note`, or `video`.
- `published_from`
  - Start of publish-time range.
  - Supports `YYYY-MM-DD` or ISO 8601 datetime.
- `published_to`
  - End of publish-time range.
  - Supports `YYYY-MM-DD` or ISO 8601 datetime.
- `page`
  - 1-based page number.
- `page_size`
  - Number of results per page, `1-100`.

Example request:

```http
GET /api/external/v1/articles?keyword=AI&platforms=wechat&published_from=2026-04-01&published_to=2026-04-09&page=1&page_size=20
```

Example response:

```json
{
  "query": {
    "keyword": "AI",
    "platforms": ["wechat"],
    "content_kind": null,
    "published_from": "2026-04-01",
    "published_to": "2026-04-09",
    "page": 1,
    "page_size": 20
  },
  "total": 2,
  "items": [
    {
      "article_id": 101,
      "job_id": 36,
      "keyword": "AI",
      "platform": "wechat",
      "content_kind": "article",
      "source_engine": "wechat_exporter_fetch",
      "title": "示例文章",
      "source_url": "https://mp.weixin.qq.com/s/demo",
      "account_name": "示例账号",
      "publish_time": "2026-04-09T07:07:24+00:00",
      "read_count": 1234,
      "comment_count": 12,
      "excerpt": "这是本地存储的文章摘要片段。",
      "has_html": true,
      "data_url": "http://127.0.0.1:8000/api/external/v1/articles/101",
      "preview_url": "http://127.0.0.1:8000/api/external/v1/articles/101/preview"
    }
  ]
}
```

### `GET /api/external/v1/articles/{article_id}`

Return the full locally stored article record.

Main fields:

- `content_text`
- `content_html`
- `comments`
- `data_url`
- `preview_url`

This endpoint is suitable for external systems that need the raw text, stored HTML, and comment payload.

### `GET /api/external/v1/articles/{article_id}/preview`

Return a ready-to-open HTML preview page.

Use this when an external system wants a human-friendly preview link instead of rendering HTML itself.

## Integration Notes

- `data_url` is the canonical JSON detail link for programmatic reads.
- `preview_url` is the canonical browser preview link for operators.
- Time filtering is applied against the local `publish_time` field in UTC.
- If stored `content_html` is empty, preview output falls back to the stored plain text body.
- Only local stored data is returned. This API does not trigger new crawling tasks by itself.

## Recommended Call Pattern

1. Call `GET /api/external/v1/articles` with keyword, time range, and platform filters.
2. Read `data_url` for structured detail ingestion.
3. Use `preview_url` for manual QA or operator review.
