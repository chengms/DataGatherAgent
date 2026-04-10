# API

## Overview

DataGatherAgent provides a small FastAPI backend for keyword-driven article discovery, fetch, and ranking workflows.

Base URL:

- `http://127.0.0.1:8000`

Interactive docs:

- Swagger UI: `http://127.0.0.1:8000/docs`

## Endpoints

### `GET /health`

Returns a simple health payload:

```json
{"status": "ok"}
```

### `GET /api/discovery/sources`

Lists the registered discovery and fetch adapters.

### `POST /api/workflows/preview`

Runs the workflow end to end for the given keywords.

Example request:

```json
{
  "keywords": ["AI Agent", "Semiconductor"],
  "platforms": ["wechat", "xiaohongshu", "weibo"],
  "limit": 3,
  "top_k": 2,
  "fallback_to_mock": true
}
```

Key request fields:

- `keywords`: one or more search keywords
- `platforms`: one or more platforms to run in one request (defaults to `["wechat"]`)
- `platform`: legacy single-platform field; use `platforms` for new calls
- `limit`: candidates per keyword
- `top_k`: number of ranked hot articles returned
- `time_window_days`: ranking freshness window
- `fallback_to_mock`: whether to fall back to mock adapters when live adapters fail
- `discovery_source` / `fetch_source`: optional manual override for single-platform requests

Current platform values:

- `wechat`
- `xiaohongshu`
- `weibo`
- `douyin`
- `bilibili`

Source selection behavior:

- If `platforms` has multiple values, backend uses built-in platform strategies automatically
- If a single platform is selected and both `discovery_source` and `fetch_source` are provided, backend uses the provided pair

### `GET /api/workflows/jobs`

Returns saved workflow job summaries.

### `GET /api/workflows/jobs/{job_id}`

Returns a saved workflow job and its ranked hot articles.

### `GET /api/external/v1/articles`

Standard export API for external systems that need to read locally stored crawl results.

Query parameters:

- `keyword`: fuzzy match against title, content, account name, keyword, and source URL
- `platforms`: comma-separated platform list such as `wechat,xiaohongshu`
- `content_kind`: optional content type filter such as `article`, `note`, or `video`
- `published_from`: publish-time lower bound, accepts `YYYY-MM-DD` or ISO 8601 datetime
- `published_to`: publish-time upper bound, accepts `YYYY-MM-DD` or ISO 8601 datetime
- `page`: 1-based page index
- `page_size`: page size between 1 and 100

Each returned item includes:

- `data_url`: JSON detail link
- `preview_url`: directly openable HTML preview link
- article metadata such as title, platform, publish time, source URL, and excerpt

### `GET /api/external/v1/articles/{article_id}`

Returns the full local article payload including:

- `content_text`
- `content_html`
- `comments`
- `data_url` and `preview_url`

### `GET /api/external/v1/articles/{article_id}/preview`

Returns a rendered HTML preview page for the locally stored article body and comments.

## Error Shape

Application exceptions are normalized to this shape:

```json
{
  "error": {
    "code": "ERROR_CODE",
    "message": "Human readable message",
    "details": {}
  },
  "request_id": "unknown"
}
```

Typical error codes:

- `INVALID_REQUEST`
- `NOT_FOUND`
- `ADAPTER_NOT_FOUND`
- `DISCOVERY_ERROR`
- `FETCH_ERROR`
- `RANKING_ERROR`
- `INTERNAL_ERROR`

## Notes

- The frontend page is served from `/`
- Static assets are served from `/assets/*`
- Workflow preview responses include `platforms` to reflect the selected platform set
- Current automated tests cover health checks, adapter listing, workflow preview, job queries, adapter registry behavior, and ranking behavior
- External export API details are documented in `docs/EXTERNAL_EXPORT_API.md`
