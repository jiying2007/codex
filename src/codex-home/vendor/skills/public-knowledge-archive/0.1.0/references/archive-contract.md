# Archive contract

## Source and permission model

| Field | Required rule |
|---|---|
| Source URL | Must be explicitly supplied by the user for the current run. |
| Allowlist | Must be explicit, narrow, and checked before every fetch and after redirects. |
| Public status | Archive only content reachable without login or verification. |
| Robots | `robots.txt` must allow the archive user agent; unavailable means fail closed. |
| Credentials | Never use, request, read, import, serialize, or persist credentials/cookies. |
| Source writes | Forbidden: no comments, likes, edits, uploads, or account actions. |

## Limits and discovery

- Default page limit: 20.
- Hard page limit: 100.
- Default depth: 1.
- Hard depth: 2.
- Discovery follows only HTML anchors to allowed domains and stops when the page limit is reached.
- Discovery is not a crawler for arbitrary public sites. New sources or domains require explicit user input.

## Provenance record

Each `index.jsonl` record contains canonical/final URL, retrieval time, SHA-256 of extracted visible text, title, category, depth, archive status, and a local path when the page was stored.

Status values:

- `archived`: a new or refreshed public body was stored.
- `unchanged`: the current text hash equals the prior hash; no duplicate body was written.
- `access-gated`: login or verification page detected; no body stored.
- `dynamic-shell`: public HTTP returned an insufficient JavaScript shell; no body stored.
- `blocked-robots`: robots policy unavailable or disallowed.
- `blocked-domain`: source is outside allowlist.
- `blocked-redirect`: final redirect target is outside allowlist.
- `unsupported-content`: non-HTML content.
- `fetch-error`: public fetch failed.

## Content boundary

- Archive pages as public reference material with provenance, not as source-of-truth product claims.
- Preserve source URL and content hash with every body.
- Do not store authentication state, signed redirect URLs, raw browser sessions, hidden HTML, or private attachments.
- Classify any downstream conclusion as source reference, VOSEN hypothesis, or target-sample evidence.
