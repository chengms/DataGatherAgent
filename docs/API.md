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
  "discovery_source": "mock_wechat_search",
  "fetch_source": "mock_wechat_fetch",
  "limit": 3,
  "top_k": 2,
  "fallback_to_mock": true
}
```

Key request fields:

- `keywords`: one or more search keywords
- `platform`: defaults to `wechat`
- `discovery_source`: discovery adapter name
- `fetch_source`: fetch adapter name
- `limit`: candidates per keyword
- `top_k`: number of ranked hot articles returned
- `time_window_days`: ranking freshness window
- `fallback_to_mock`: whether to fall back to mock adapters when live adapters fail

### `GET /api/workflows/jobs`

Returns saved workflow job summaries.

### `GET /api/workflows/jobs/{job_id}`

Returns a saved workflow job and its ranked hot articles.

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
- Current automated tests cover health checks, adapter listing, workflow preview, job queries, adapter registry behavior, and ranking behavior
