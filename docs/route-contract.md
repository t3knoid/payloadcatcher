# PayloadCatcher Minimal Route Contract

## 1. Routes

### 1.1 GET /

Purpose: Provision or return the active callback URL for this visitor context.

Query params:

- `timezone` (optional, browser timezone hint for visit metadata capture)
- `gps_consent` (optional, explicit opt-in flag for precise GPS collection)
- `gps_lat` (optional, latitude captured only when `gps_consent=true`)
- `gps_lng` (optional, longitude captured only when `gps_consent=true`)

Response 200 shape:

```json
{
  "clsid": "550e8400-e29b-41d4-a716-446655440000",
  "callback_url": "https://payloadcat.ch/hook/550e8400-e29b-41d4-a716-446655440000",
  "viewer_url": "https://payloadcat.ch/inbox/550e8400-e29b-41d4-a716-446655440000",
  "expires_at": "2026-05-16T12:00:00Z",
  "new_session": true
}
```

Notes:

- `clsid` is lowercase UUIDv4.
- If an existing mapping is still valid (24h), return it.
- If expired, issue and return a new mapping.
- `callback_url` always uses the canonical hook endpoint shape.
- The response sets a cookie-bound session with secure defaults: `HttpOnly`, `Secure`, and `SameSite=Lax`.
- Visit metadata capture includes source IP, user-agent, browser and device hints, referer, primary language, the optional timezone hint, best-effort trusted-proxy locality, and GPS only after explicit opt-in.
- Requests are rate limited per source IP using `RATE_LIMIT_PER_MINUTE`.
- If source IP changes while the session cookie remains valid, the callback URL stays stable and the source-IP change is treated as a risk signal for logging and abuse analysis.
- Locality capture uses the configured `LOCALITY_HEADER_NAME` only when the request comes through a trusted proxy.
- GPS coordinates must not be stored unless the caller explicitly sets `gps_consent=true`.

Errors:

- 429 rate limited, with `Retry-After` and `error.details.retry_after_seconds`

### 1.2 POST /hook/{clsid}

Purpose: Receive webhook payloads for an inbox.

Path params:

- `clsid` (required, lowercase UUIDv4)

Request:

- Content-Type: any (`application/json`, `application/x-www-form-urlencoded`, `text/plain`, or other valid media types)
- Body: raw request payload as sent by caller

Optional auth headers (mode-dependent):

- `Authorization: Bearer <token>` for `shared_token` mode
- `X-PC-Key-Id: <key_id>` for `signature` mode
- `X-PC-Timestamp: <unix_seconds_or_iso8601>` for `signature` mode
- `X-PC-Signature: <algorithm>=<digest>` for `signature` mode

Response:

- 200 OK returned quickly

Response 200 shape:

```json
{
  "status": "accepted",
  "request_id": "01jv4d3h7l0q4y9m9m4a0y2b3k"
}
```

Notes:

- Persist and enrich asynchronously after ack.
- Invalid/expired `clsid` returns 404 with safe error envelope.
- Callback authentication behavior is mode-driven per inbox (see Section 4).
- Abuse rejections for rate limits, malformed `Content-Type`, and oversized payloads emit warning logs.

Errors:

- 400 malformed request
- 401 missing/invalid callback credentials
- 403 callback not allowed for inbox policy
- 404 unknown/expired inbox
- 413 payload too large
- 415 unsupported media type when endpoint policy rejects media type
- 422 validation/verification failure
- 429 rate limited

### 1.3 GET /inbox/{clsid}

Purpose: Return viewer data for an inbox.

Path params:

- `clsid` (required, lowercase UUIDv4)

Query params:

- `q` (optional, search text against request metadata and payload preview)
- `cursor` (optional, opaque pagination cursor)
- `limit` (optional, page size; default 50, max 100)

Response 200 shape:

```json
{
  "hook_url": "https://payloadcat.ch/hook/550e8400-e29b-41d4-a716-446655440000",
  "events": [
    {
      "request_id": "339adb08249348f089a1fdd27bf0743a",
      "received_at": "2026-05-15T12:03:02Z",
      "method": "POST",
      "content_type": "application/json",
      "source_ip_masked": "203.0.113.0/24",
      "payload_yaml": "foo: bar\ncount: 2\n"
    }
  ],
  "next_token": "eyJyZWNlaXZlZF9hdCI6IjIwMjYtMDUtMTVUMTI6MDM6MDIrMDA6MDAiLCJyZXF1ZXN0X2lkIjoiMzM5YWRiMDgyNDkzNDhmMDg5YTFmZGQyN2JmMDc0M2EifQ",
  "metadata": {
    "inbox_issued_at": "2026-05-15T12:00:00Z",
    "expires_at": "2026-05-16T12:00:00Z",
    "capture_count": 12
  }
}
```

Notes:

- `events` powers the viewer list and supplies preview content for the request list and first-pass selection UI.
- `next_token` is an opaque cursor derived from the last event in the current page.
- Search matches request ID, method, stored source IP, and the visible payload preview text returned by the endpoint.
- Sort order is stable by `received_at DESC, request_id DESC`.
- Viewer-facing network identifiers remain masked by default.
- Public preview text is truncated to the `VIEWER_PAYLOAD_PREVIEW_CHARS` limit, which must be at least `4`.
- `limit` values above maximum return 400 with safe error envelope.

Errors:

- 400 invalid clsid, cursor, or limit
- 404 unknown/expired inbox
- 429 rate limited

Retry behavior:

- 429 and 503 responses include `Retry-After` header and `error.details.retry_after_seconds`.

### 1.4 GET /inbox/{clsid}/events/{request_id}

Purpose: Return the full payload view and selected request metadata for one inbox event.

Path params:

- `clsid` (required, lowercase UUIDv4)
- `request_id` (required, server-generated request identifier for an event belonging to the inbox)

Response 200 shape:

```json
{
  "request_id": "339adb08249348f089a1fdd27bf0743a",
  "received_at": "2026-05-15T12:03:02Z",
  "method": "POST",
  "content_type": "application/json",
  "headers": {
    "content-type": "application/json",
    "x-trace-id": "trace-123"
  },
  "payload_yaml": "foo: bar\ncount: 2\n",
  "source_ip_masked": "203.0.113.0/24",
  "payload_size_bytes": 20
}
```

Notes:

- Returns the full stored `payload_yaml` value without preview truncation.
- Returns sanitized captured headers for the selected event.
- Viewer-facing network identifiers remain masked by default.
- The viewer must treat `payload_yaml` as inert text and never execute payload content.
- Detail requests use an independent viewer-detail rate-limit budget from the list route so the default list-plus-detail flow does not double-charge one viewer bucket.

Errors:

- 400 invalid clsid
- 404 unknown/expired inbox or event not found for inbox
- 429 rate limited

## 2. Standard Error Envelope

Non-2xx responses use this shape:

```json
{
  "error": {
    "code": "rate_limited",
    "message": "Too many requests",
    "details": {
      "retry_after_seconds": 30
    }
  },
  "request_id": "01jv4d3h7l0q4y9m9m4a0y2b3k"
}
```

Required fields:

- `error.code`
- `error.message`
- `request_id`

## 3. Minimal Table Schema

### 3.1 inboxes

- `id` UUID PK
- `clsid` VARCHAR(36) UNIQUE NOT NULL
- `source_ip` INET/TEXT NOT NULL
- `issued_at` TIMESTAMP WITH TIME ZONE NOT NULL
- `expires_at` TIMESTAMP WITH TIME ZONE NOT NULL
- `created_at` TIMESTAMP WITH TIME ZONE NOT NULL
- `updated_at` TIMESTAMP WITH TIME ZONE NOT NULL

Indexes:

- unique index on `clsid`
- index on `expires_at`

### 3.2 visit_metadata

- `id` UUID PK
- `inbox_id` UUID FK -> inboxes.id
- `visited_at` TIMESTAMP WITH TIME ZONE NOT NULL
- `source_ip` INET/TEXT NOT NULL
- `referer_url` TEXT NULL
- `user_agent` TEXT NULL
- `browser` TEXT NULL
- `device` TEXT NULL
- `lang` TEXT NULL
- `tz` TEXT NULL
- `locality` TEXT NULL
- `headers_json` JSONB/TEXT NOT NULL
- `gps_lat` NUMERIC NULL
- `gps_lng` NUMERIC NULL
- `consent` BOOLEAN NOT NULL DEFAULT FALSE

Indexes:

- index on `inbox_id, visited_at`

### 3.3 webhook_events

- `id` UUID PK
- `inbox_id` UUID FK -> inboxes.id
- `request_id` TEXT UNIQUE NOT NULL
- `received_at` TIMESTAMP WITH TIME ZONE NOT NULL
- `method` TEXT NOT NULL
- `content_type` TEXT NULL
- `headers_json` JSONB/TEXT NOT NULL
- `payload_raw` BYTEA/BLOB NOT NULL
- `payload_size_bytes` BIGINT NOT NULL
- `payload_encoding` TEXT NULL
- `payload_yaml` TEXT NOT NULL
- `source_ip` INET/TEXT NOT NULL
- `dedup_key` TEXT NULL
- `is_duplicate` BOOLEAN NOT NULL DEFAULT FALSE

Indexes:

- index on `inbox_id, received_at DESC`
- index on `received_at`
- index on `inbox_id, dedup_key`

## 4. Authenticated Callback Mini-Contract

Callback auth policy is configured per inbox with `auth_mode`:

- Mode: `none`.
- Requirement: No callback credential required.
- Mode: `shared_token`.
- Requirement: `Authorization: Bearer <token>` is required.
- Requirement: Token compare is constant-time against stored secret material.
- Mode: `signature`.
- Requirement: `X-PC-Key-Id`, `X-PC-Timestamp`, and `X-PC-Signature` are required.
- Requirement: Signature is computed from canonical request components and verified against key material.
- Requirement: Timestamps outside configured skew window are rejected.
- Requirement: Replayed signatures/nonces within replay window are rejected.

Normative signature rules:

- Signature algorithm whitelist: `hmac-sha256` only for v1.
- Key lookup: `X-PC-Key-Id` maps to active secret record for inbox.
- Canonical string-to-sign format:
  `METHOD + "\n" + PATH + "\n" + X-PC-Timestamp + "\n" + SHA256_HEX(raw_body_bytes)`
- Digest comparison is constant-time.
- Default allowed clock skew: +/- 300 seconds.
- Replay cache key: `key_id + ":" + signature + ":" + timestamp`, TTL 10 minutes.

Verification outcomes:

- Success: continue normal ingest flow and return 200 quickly.
- Missing or invalid credentials: return 401 safe error envelope.
- Policy mismatch (forbidden mode): return 403 safe error envelope.
- Malformed signature headers: return 422 safe error envelope.

## 5. Idempotency and Dedup Contract

1. Deduplication is optional and deterministic when enabled.
2. Dedup uses a configured key strategy (for example hash of normalized body + selected metadata).
3. Duplicate deliveries do not overwrite canonical first-capture data.
4. Duplicate events are marked (`is_duplicate=true`) and linked by dedup key.

## 6. Cleanup Contract

1. A daily cleanup job deletes expired inboxes and dependent metadata/events.
2. Job execution is idempotent and safe to re-run.
