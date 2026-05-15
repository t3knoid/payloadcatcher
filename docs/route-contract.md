# PayloadCatcher Minimal Route Contract

## 1. Routes

### 1.1 GET /

Purpose: Provision or return the active callback URL for this visitor context.

Response 200 shape:

```json
{
  "clsid": "550e8400-e29b-41d4-a716-446655440000",
  "hook_url": "https://payloadcat.ch/hook/550e8400-e29b-41d4-a716-446655440000",
  "viewer_url": "https://payloadcat.ch/inbox/550e8400-e29b-41d4-a716-446655440000",
  "expires_at": "2026-05-16T12:00:00Z"
}
```

Notes:

- `clsid` is lowercase UUIDv4.
- If an existing mapping is still valid (24h), return it.
- If expired, issue and return a new mapping.

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
- `selected_event_id` (optional, event id for payload detail panel)
- `cursor` (optional, opaque pagination cursor)
- `limit` (optional, page size; default 50, max 100)

Response 200 shape:

```json
{
  "clsid": "550e8400-e29b-41d4-a716-446655440000",
  "hook_url": "https://payloadcat.ch/hook/550e8400-e29b-41d4-a716-446655440000",
  "expires_at": "2026-05-16T12:00:00Z",
  "next_cursor": "eyJsYXN0X3JlY2VpdmVkX2F0IjoiMjAyNi0wNS0xNVQxMjowMzowMloifQ",
  "request_summaries": [
    {
      "event_id": "01jv4d6zy8k4h0wn4wdrq7x9md",
      "received_at": "2026-05-15T12:03:02Z",
      "content_type": "application/json",
      "method": "POST",
      "source_ip_masked": "203.0.113.0/24",
      "payload_preview": "foo: bar"
    }
  ],
  "selected_event": {
    "event_id": "01jv4d6zy8k4h0wn4wdrq7x9md",
    "received_at": "2026-05-15T12:03:02Z",
    "content_type": "application/json",
    "payload_yaml": "foo: bar\ncount: 2\n"
  }
}
```

Notes:

- `request_summaries` powers the narrow left column list.
- `selected_event` powers the wide right payload panel.
- If `selected_event_id` is omitted, return the newest event as selected.
- Sort order is stable by `received_at DESC, event_id DESC`.
- `limit` values above maximum return 400 with safe error envelope.

Errors:

- 404 unknown/expired inbox
- 429 rate limited

Retry behavior:

- 429 and 503 responses include `Retry-After` header and `error.details.retry_after_seconds`.

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
- `browser_type` TEXT NULL
- `device_type` TEXT NULL
- `language` TEXT NULL
- `timezone` TEXT NULL
- `locality` TEXT NULL
- `headers_json` JSONB/TEXT NOT NULL
- `gps_lat` NUMERIC NULL
- `gps_lng` NUMERIC NULL
- `gps_consent` BOOLEAN NOT NULL DEFAULT FALSE

Indexes:

- index on `inbox_id`
- index on `visited_at`

### 3.3 webhook_events

- `id` UUID PK
- `inbox_id` UUID FK -> inboxes.id
- `request_id` TEXT UNIQUE NOT NULL
- `received_at` TIMESTAMP WITH TIME ZONE NOT NULL
- `method` TEXT NOT NULL
- `content_type` TEXT NULL
- `headers_json` JSONB/TEXT NOT NULL
- `payload_raw` JSONB/TEXT NOT NULL
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
