# Technical Documentation

This document explains how the Fingerprint Access Control system was built,
how it works, and how to operate it. It follows the nine build steps from the
original specification, then provides a full technical reference.

---

## Contents

1. [System overview](#1-system-overview)
2. [Edge-matching architecture](#2-edge-matching-architecture)
3. [Build log: Step 1 → Step 9](#3-build-log-step-1--step-9)
4. [Data model](#4-data-model)
5. [API reference](#5-api-reference)
6. [WebSocket contract](#6-websocket-contract)
7. [Email notifications](#7-email-notifications)
8. [Frontend architecture](#8-frontend-architecture)
9. [Security model](#9-security-model)
10. [Management commands](#10-management-commands)
11. [Configuration reference](#11-configuration-reference)
12. [Verification checklist](#12-verification-checklist)
13. [Troubleshooting](#13-troubleshooting)
14. [Production checklist](#14-production-checklist)

---

## 1. System overview

The system answers one question: **who passed through a door, and when?**

A fingerprint terminal does the biometric work locally. It holds a copy of the
registered templates, matches a scan against them, and sends only the outcome to
this server. The server is the master source of truth for people, templates and
history; it never performs matching and never sees a fingerprint image.

### Components

| Layer | Technology | Responsibility |
| --- | --- | --- |
| API | Django 6.1 + DRF 3.18 | Validation, persistence, permissions |
| Database | PostgreSQL 17 | Members, devices, encrypted templates, logs |
| Real time | Django Channels 4 + Daphne | Broadcast `entry_event` frames |
| Auth | SimpleJWT | Dashboard access/refresh tokens |
| Device auth | Shared API key | `X-Device-API-Key` header |
| Email | Django SMTP backend | Three HTML alert templates |
| UI | React 19 + Vite 6 | Live dashboard, CRUD, history, devices |
| Charts | Recharts | Trend, hourly traffic, status donut |

### Identity categories

| Status | UI colour | Personal data shown | Email subject |
| --- | --- | --- | --- |
| `MEMBER` | Green | Photo, name, phone, email | `✅ Entry Granted: {name} at {location}` |
| `VISITOR` | Blue | Photo, name, phone, email | `🔵 Visitor Arrived: {name} at {location}` |
| `UNKNOWN` | Red | **None** — location and time only | `🚨 SECURITY ALERT: Unknown person at {location}` |

The red category is deliberately privacy-preserving: an unknown person has no
profile, so no name, contact details or image can be shown or emailed.

---

## 2. Edge-matching architecture

```
Device boot
  └─ GET /api/device/templates/sync/?device_id=FP-FRONT-01
       └─ decrypt templates in memory → base64 → device stores locally
       └─ server marks templates SYNCED

Person scans finger
  └─ device matches locally against its template store
       ├─ match MEMBER   → status=MEMBER,  member_id=<id>
       ├─ match VISITOR  → status=VISITOR, member_id=<id>
       └─ no match       → status=UNKNOWN, member_id=null
  └─ POST /api/device/event/
       └─ validate key, device, member/role, timestamp
       └─ INSERT EntryLog
       └─ mark device online
       └─ on_commit: WebSocket broadcast + owner email
```

**Why edge matching?**

- **Latency:** a local match is immediate; no round trip per scan.
- **Privacy:** raw prints and images never leave the terminal.
- **Resilience:** the door still works if the network is down. Events are
  buffered and replayed later; anything older than two minutes is stored with
  `synced_from_device = true`.

**Server-side responsibilities**

- Own the canonical member list and encrypted template archive.
- Serve template deltas to devices (`?since=`).
- Enforce role/status consistency and reject invalid events.
- Record an immutable access history and drive alerts.
- Never match fingerprints.

---

## 3. Build log: Step 1 → Step 9

### Step 1 — Backend scaffold, PostgreSQL, models, migrations

**Created**

```
backend/
├── manage.py
├── requirements.txt
├── .env / .env.example
├── config/{settings,urls,asgi,wsgi,pagination,exceptions}.py
├── accounts/      # custom User + app config
├── members/       # Member, FingerprintTemplate, crypto.py
├── devices/       # Device
├── logs/          # EntryLog
└── notifications/ # app shell + template folder
```

**Key decisions**

- `AUTH_USER_MODEL = "accounts.User"` — a custom user with a unique email,
  separate from the `Member` domain model. Owners log into the dashboard;
  members are people who walk through the door.
- **PostgreSQL only.** `DATABASES` hard-codes the PostgreSQL engine; there is no
  SQLite fallback.
- Every deployment secret is read from `backend/.env` via `python-dotenv`.
  Missing `DEVICE_API_KEY` or `TEMPLATE_ENCRYPTION_KEY` raises
  `ImproperlyConfigured` at startup.
- Fingerprint templates are encrypted with **Fernet** before they reach the
  database (`members/crypto.py`). The key is cached with `lru_cache`.
- `Member.photo` uploads to `media/members/<username>/<uuid>.<ext>` so file names
  cannot collide or leak personal data.
- `EntryLog` has a database `CheckConstraint`:
  `MEMBER`/`VISITOR` ⇒ member is not null; `UNKNOWN` ⇒ member is null.
- Indexes cover the query patterns: status + timestamp, device + timestamp,
  member + timestamp, sync status, online status.

**Verified**

```powershell
python manage.py check
python manage.py makemigrations
python manage.py migrate
```

Result: all five apps migrated into `fingerprint_db`.

---

### Step 2 — JWT auth, serializers, member CRUD

**Created**

- `accounts/serializers.py`, `views.py`, `urls.py`
- `members/serializers.py`, `views.py`, `urls.py`

**Auth endpoints**

- `POST /api/auth/login/` → access + refresh + owner profile.
- `POST /api/auth/refresh/` → rotated access token.
- `GET /api/auth/me/` → current owner profile.

JWT settings: access 60 minutes, refresh 7 days, rotation enabled, Argon2id
password hashing first.

**Member API**

- `MemberViewSet` supports list, retrieve, create, update, partial update and
  delete.
- Multipart parsing is enabled for photo uploads.
- Write and read serializers are separated: `MemberWriteSerializer` validates
  input; `MemberSerializer` returns nested fingerprint summaries and absolute
  `photo_url`.
- `is_active` defaults to `true` for multipart requests (HTML forms omit
  unchecked booleans, which DRF would otherwise read as `false`).
- `POST /api/members/{id}/enroll/` accepts optional base64 `template_data`,
  encrypts it, stores it as `PENDING`, or queues existing templates for sync.
- `GET /api/members/{id}/fingerprints/` returns counts only — never bytes.

**Validation rules**

| Field | Rule |
| --- | --- |
| `username` | ≥ 3 chars; letters, digits, `.`, `_`, `-`; case-insensitive unique |
| `full_name` | ≥ 2 chars; whitespace collapsed; control characters rejected |
| `phone_number` | 7–32 chars from digits, `+`, space, `(`, `)`, `-` |
| `email` | validated, lower-cased |
| `photo` | required; JPEG/PNG/WEBP; Pillow-verified; ≤ 5 MB |
| `role` | `MEMBER` or `VISITOR` |

**Verified**

Login, `/me`, member create with photo, update, delete, duplicate username
rejection, invalid image rejection, and enroll.

---

### Step 3 — Device endpoints and EntryLog creation

**Created**

- `devices/authentication.py` — `DeviceAPIKeyAuthentication`,
  `DevicePrincipal`, `IsDeviceAuthenticated`.
- `devices/serializers.py` — event, heartbeat, template-sync validation.
- `devices/views.py` — three device views + read-only device list.
- `devices/device_urls.py` — mounted under `/api/device/`.
- `logs/services.py` — `record_entry()`.
- `devices/management/commands/create_device.py`
- `devices/management/commands/mark_devices_offline.py`

**Device authentication**

The terminal sends `X-Device-API-Key`. The key is compared with
`secrets.compare_digest` to avoid timing leaks. Devices are not Django users;
`DevicePrincipal` satisfies DRF's permission layer.

**Event validation**

1. API key must be valid.
2. `device_id` must exist.
3. `UNKNOWN` must have `member_id = null`.
4. `MEMBER`/`VISITOR` must reference an existing, **active** member whose role
   equals the status.
5. Timestamp may not be more than 5 minutes in the future.
6. Events older than 2 minutes are automatically flagged as buffered syncs.

**Write path**

```python
with transaction.atomic():
    log = EntryLog.objects.create(...)
    Device.objects.filter(pk=device.pk).update(is_online=True, last_seen_at=now)

transaction.on_commit(lambda: _dispatch(log.pk))
```

`_dispatch` broadcasts the WebSocket frame and sends the email inside separate
`try/except` blocks. A failed email or dead channel layer can never roll back
the access record.

**Template sync**

- Only active members' templates are returned.
- Optional `since` returns deltas by `updated_at`.
- Templates are decrypted in memory, base64-encoded and returned; failures are
  counted and logged, never exposed.
- Returned templates are marked `SYNCED` with `last_synced_at`.
- The device is marked online.

**Verified**

Heartbeat, MEMBER event, UNKNOWN event, template sync, wrong API key (401),
unknown device (400), mismatched role (400), future timestamp (400).

---

### Step 4 — Django Channels and the WebSocket feed

**Created**

- `config/asgi.py` — `ProtocolTypeRouter` for HTTP + WebSocket.
- `logs/consumers.py` — `DashboardConsumer`.
- `logs/middleware.py` — `JWTAuthMiddleware`.
- `logs/routing.py` — `ws/dashboard/`.
- `logs/realtime.py` — payload builder + group broadcast.

**Connection flow**

1. Browser opens `ws://host/ws/dashboard/?token=<access-token>`.
2. `AllowedHostsOriginValidator` rejects foreign origins.
3. `JWTAuthMiddleware` validates the access token and loads the active user.
4. `DashboardConsumer.connect` rejects anonymous users with close code `4401`.
5. The socket joins the `dashboard` group and receives
   `connection_established`.
6. Application-level `{"type": "ping"}` frames are answered with `pong`.

**Channel layer**

- Development default: `InMemoryChannelLayer` (single process).
- Set `REDIS_URL` to use `channels_redis` for multi-worker deployments.

**Verified**

Two browser sessions received live green/blue/red cards without refresh;
invalid tokens were rejected with 4401.

---

### Step 5 — HTML email notifications

**Created**

- `notifications/emails.py`
- `notifications/templates/notifications/email_member.html`
- `notifications/templates/notifications/email_visitor.html`
- `notifications/templates/notifications/email_unknown.html`
- `notifications/management/commands/send_test_email.py`

**Behaviour**

- Every `EntryLog` dispatches exactly one email to `OWNER_EMAIL`.
- The profile photo is attached inline with `Content-ID: <entry-photo>` so it
  renders in mail clients. If the photo is missing, the template falls back to
  initials.
- Unknown events contain **no** member data and link to
  `FRONTEND_URL/dashboard`.
- Each message has a plain-text alternative for clients that block HTML.
- The console backend is the development default; SMTP is a `.env` change.

**Verified**

`python manage.py send_test_email` and real MEMBER/VISITOR/UNKNOWN events
produced the expected subjects and bodies in the console.

---

### Step 6 — React scaffold, authentication, API client

**Created**

```
frontend/
├── index.html
├── vite.config.js
├── .env / .env.example
└── src/
    ├── main.jsx
    ├── App.jsx
    ├── api/client.js
    ├── context/AuthContext.jsx
    ├── context/ToastContext.jsx
    ├── components/ProtectedRoute.jsx
    └── pages/LoginPage.jsx
```

**API client**

- Axios instance with `baseURL = VITE_API_BASE_URL`.
- Request interceptor attaches `Authorization: Bearer <access>`.
- Response interceptor transparently refreshes an expired access token once,
  queues concurrent failures, and signs the user out if refresh fails.
- Tokens live in `localStorage` under versioned keys.

**Routing**

- `/login` is public.
- `/dashboard`, `/members`, `/logs`, `/devices` are wrapped in
  `ProtectedRoute` + `Layout`.
- Unknown URLs render a styled 404.

**Verified**

Login redirect, refresh-on-401, logout, protected route redirect.

---

### Step 7 — Dashboard live feed, WebSocket hook, charts

**Created**

- `hooks/useDashboardSocket.js`
- `components/LiveFeed.jsx`, `EventCard.jsx`, `StatCard.jsx`
- `components/TrafficChart.jsx`, `HourlyChart.jsx`, `StatusDonut.jsx`
- `pages/DashboardPage.jsx`

**Live feed**

- Subscribes with the access token in the query string.
- Exponential backoff (1 s → 15 s) with keepalive pings every 25 s.
- New events prepend instantly; the list is capped to avoid unbounded memory.
- Card colours and content follow the status contract:
  - green/blue: photo (or initials), name, phone, email, location, time;
  - red: `UNKNOWN PERSON DETECTED`, location, time only.
- A connection badge shows connecting / connected / reconnecting.

**Charts**

- 7-day stacked area/bar trend (members, visitors, unknowns).
- Hourly traffic for today.
- Today's status distribution donut.
- Stat cards: total today, members, visitors, unknowns, plus device health.

**Verified**

A posted UNKNOWN event appeared as a red card in an already-open dashboard
without a refresh; counters updated.

---

### Step 8 — Members, Logs and Devices pages

**Members**

- Responsive card/table listing with search, role filter and active filter.
- Create/edit modal with photo preview, client-side size check and server-side
  validation errors mapped back to fields.
- Delete confirmation dialog.
- Enroll action queues templates for device sync and reports the result.

**Logs**

- Server-side pagination (20/page, up to 100).
- Filters: status (including multi-select), date-from, date-to, device, search.
- Debounced search and request-sequence guards so stale responses cannot
  overwrite newer filter results.
- Status badges, member thumbnails, location and sync indicator.

**Devices**

- Device cards with online/offline state, location, last seen and a search box.
- Online state is computed server-side from `last_seen_at` and
  `DEVICE_OFFLINE_AFTER_SECONDS`.

**Verified**

CRUD round trip with photo upload, delete cascade, log filtering, pagination,
and device search.

---

### Step 9 — Polish, error handling, documentation

- Added `preview.proxy` to `vite.config.js` so `npm run preview` behaves like
  the dev server.
- Split `recharts` and React into separate build chunks.
- Added a root `.gitignore` covering secrets, media, caches and build output.
- Wrote `README.md` and this `DOCUMENTATION.md`.
- Ran final checks: `manage.py check`, migration drift check, production build.
- Reviewed accessibility states: focus styles, labels, empty/loading/error
  states, reduced-motion support, responsive breakpoints.

---

## 4. Data model

### `accounts.User`

Extends `AbstractUser`; `email` is unique; `REQUIRED_FIELDS = ["email"]`.
Used only for dashboard/admin login. Passwords are hashed with Argon2id.

### `members.Member`

| Field | Type | Notes |
| --- | --- | --- |
| `id` | BigAutoField | PK |
| `username` | CharField(64) | unique, validated |
| `full_name` | CharField(150) | |
| `phone_number` | CharField(32) | |
| `email` | EmailField | not unique (households share addresses) |
| `role` | CharField(10) | `MEMBER` \| `VISITOR` |
| `photo` | ImageField | upload path `members/<username>/<uuid>.<ext>` |
| `is_active` | BooleanField | default `True` |
| `created_at` / `updated_at` | DateTimeField | automatic |

Indexes: `(role, is_active)`, `email`, `full_name`.
Ordering: newest first.

### `members.FingerprintTemplate`

| Field | Type | Notes |
| --- | --- | --- |
| `id` | BigAutoField | PK |
| `member` | FK → Member | `CASCADE`, related name `fingerprints` |
| `template_data` | BinaryField | **Fernet ciphertext**, never an image |
| `sync_status` | CharField(10) | `PENDING` \| `SYNCED` |
| `last_synced_at` | DateTimeField | nullable |
| `created_at` / `updated_at` | DateTimeField | automatic |

Indexes: `(member, sync_status)`, `sync_status`.
A member may have several templates (multiple fingers).

### `devices.Device`

| Field | Type | Notes |
| --- | --- | --- |
| `id` | BigAutoField | PK |
| `device_id` | CharField(100) | unique hardware identifier |
| `location_name` | CharField(150) | e.g. "Front Door" |
| `is_online` | BooleanField | last known state |
| `last_seen_at` | DateTimeField | updated by events/sync/heartbeat |
| `created_at` / `updated_at` | DateTimeField | automatic |

Indexes: `is_online`, `last_seen_at`. Ordering: location, then device id.

### `logs.EntryLog`

| Field | Type | Notes |
| --- | --- | --- |
| `id` | BigAutoField | PK |
| `member` | FK → Member | `SET_NULL`, nullable = UNKNOWN |
| `device` | FK → Device | `PROTECT` (history cannot lose its origin) |
| `status` | CharField(10) | `MEMBER` \| `VISITOR` \| `UNKNOWN` |
| `timestamp` | DateTimeField | indexed, defaults to now |
| `synced_from_device` | BooleanField | true for buffered/replayed events |
| `created_at` | DateTimeField | server receipt time |

Indexes: `(status, timestamp)`, `(device, timestamp)`,
`(member, timestamp)`.
Constraint `entrylog_member_matches_status` keeps status and member consistent.

### Entity relationships

```
User (owner)                     Device
                                   │ 1
                                   │
Member 1 ──── n FingerprintTemplate│
   │ 1                             │ n
   └──────── n EntryLog ───────────┘
                (member nullable)
```

---

## 5. API reference

### Conventions

- Base URL (development): `http://127.0.0.1:8000`
- Dashboard requests: `Authorization: Bearer <access>`
- Device requests: `X-Device-API-Key: <key>`
- JSON bodies unless noted; member create/update accepts multipart.
- Paginated list responses:

```json
{
  "count": 53,
  "next": "http://127.0.0.1:8000/api/logs/?page=2",
  "previous": null,
  "results": []
}
```

- Validation errors use DRF's shape, normalised by
  `config/exceptions.py`:

```json
{
  "detail": "username: This username is already taken.",
  "errors": { "username": ["This username is already taken."] },
  "status_code": 400
}
```

`detail` is a flat, human-readable summary; `errors` keeps the structured
field-level detail.

### 5.1 Authentication

#### `POST /api/auth/login/`

```json
{ "username": "Engineer", "password": "Landload@100" }
```

```json
{
  "access": "<jwt>",
  "refresh": "<jwt>",
  "user": {
    "id": 1,
    "username": "Engineer",
    "email": "engineerblack95@gmail.com",
    "first_name": "",
    "last_name": "",
    "full_name": "Engineer",
    "is_staff": true,
    "is_superuser": true,
    "last_login": "2026-11-07T09:00:00+02:00"
  }
}
```

Invalid credentials return `401`.

#### `POST /api/auth/refresh/`

```json
{ "refresh": "<jwt>" }
```

Returns a new access token (and a rotated refresh token).

#### `GET /api/auth/me/`

Returns the same `user` object. Requires a bearer token.

### 5.2 Members

| Method | Path | Description |
| --- | --- | --- |
| `GET` | `/api/members/` | Paginated list |
| `POST` | `/api/members/` | Create (multipart) |
| `GET` | `/api/members/{id}/` | Retrieve |
| `PUT` | `/api/members/{id}/` | Full update |
| `PATCH` | `/api/members/{id}/` | Partial update |
| `DELETE` | `/api/members/{id}/` | Delete (cascades templates) |
| `POST` | `/api/members/{id}/enroll/` | Queue/upload template |
| `GET` | `/api/members/{id}/fingerprints/` | Template counts |

**List filters**

- `?role=MEMBER|VISITOR`
- `?is_active=true|false`
- `?search=` — name, username, email or phone
- `?page=`, `?page_size=` (max 100)

**Create / update fields**

```
username, full_name, phone_number, email, role, photo, is_active
```

Multipart example:

```powershell
curl.exe -X POST http://127.0.0.1:8000/api/members/ `
  -H "Authorization: Bearer $TOKEN" `
  -F "username=jane.doe" `
  -F "full_name=Jane Doe" `
  -F "phone_number=+250 788 000 000" `
  -F "email=jane@example.com" `
  -F "role=MEMBER" `
  -F "is_active=true" `
  -F "photo=@C:\path\jane.jpg"
```

**Member object**

```json
{
  "id": 6,
  "username": "amina.k",
  "full_name": "Amina Keza",
  "phone_number": "+250 788 123 401",
  "email": "amina.keza@example.com",
  "role": "MEMBER",
  "role_display": "Member",
  "photo": "http://127.0.0.1:8000/media/members/amina.k/abc.png",
  "photo_url": "http://127.0.0.1:8000/media/members/amina.k/abc.png",
  "is_active": true,
  "fingerprint_count": 1,
  "fingerprints": [
    {
      "id": 3,
      "sync_status": "SYNCED",
      "last_synced_at": "2026-11-07T09:29:00+02:00",
      "created_at": "2026-11-01T08:00:00+02:00",
      "updated_at": "2026-11-07T09:29:00+02:00"
    }
  ],
  "created_at": "2026-11-01T08:00:00+02:00",
  "updated_at": "2026-11-07T09:29:00+02:00"
}
```

**Enroll**

```json
{ "template_data": "<base64 template bytes>" }
```

Omit `template_data` to re-queue existing templates. If neither a body nor an
existing template is available the API returns `400`. Response:

```json
{
  "detail": "New fingerprint template stored and queued for device sync.",
  "template_id": 12,
  "member": { "...": "member object" }
}
```

**Fingerprint counts**

```json
{ "count": 2, "pending": 1, "synced": 1 }
```

### 5.3 Logs and statistics

#### `GET /api/logs/`

Read-only, newest first.

| Query | Meaning |
| --- | --- |
| `status` | `MEMBER`, `VISITOR`, `UNKNOWN` or a comma-separated list |
| `date_from` | ISO date or datetime (inclusive) |
| `date_to` | ISO date or datetime (inclusive) |
| `device` | numeric device id |
| `member` | numeric member id |
| `synced` | `true` / `false` |
| `search` | member name/username or location |
| `page`, `page_size` | pagination |

Example:

```
GET /api/logs/?status=UNKNOWN,VISITOR&date_from=2026-11-01&date_to=2026-11-07
```

Log object:

```json
{
  "id": 128,
  "status": "UNKNOWN",
  "member": null,
  "device": { "id": 1, "device_id": "FP-FRONT-01", "location_name": "Front Door" },
  "timestamp": "2026-11-07T09:31:12+02:00",
  "synced_from_device": false,
  "created_at": "2026-11-07T09:31:13+02:00"
}
```

For `MEMBER`/`VISITOR`, `member` is:

```json
{
  "id": 6,
  "username": "amina.k",
  "full_name": "Amina Keza",
  "phone_number": "+250 788 123 401",
  "email": "amina.keza@example.com",
  "role": "MEMBER",
  "photo_url": "http://127.0.0.1:8000/media/members/amina.k/abc.png"
}
```

#### `GET /api/dashboard/stats/`

```json
{
  "date": "2026-11-07",
  "today": { "total": 9, "members": 5, "visitors": 2, "unknowns": 2 },
  "totals": { "members": 3, "visitors": 2, "registered": 5 },
  "devices": { "total": 2, "online": 2 },
  "status_distribution": [
    { "status": "MEMBER", "count": 5 },
    { "status": "VISITOR", "count": 2 },
    { "status": "UNKNOWN", "count": 2 }
  ],
  "trend": [
    { "date": "2026-11-01", "members": 6, "visitors": 3, "unknowns": 1, "total": 10 }
  ],
  "hourly": [{ "hour": 0, "count": 0 }, { "hour": 8, "count": 3 }],
  "server_time": "2026-11-07T09:31:13+02:00"
}
```

`trend` always contains seven consecutive days ending today. `hourly` always
contains 24 buckets. Times are localised to `TIME_ZONE`.

### 5.4 Devices (dashboard)

#### `GET /api/devices/`

Read-only, paginated. Supports `?search=` against location or device id.

```json
{
  "id": 1,
  "device_id": "FP-FRONT-01",
  "location_name": "Front Door",
  "is_online": true,
  "last_seen_at": "2026-11-07T09:31:13+02:00",
  "created_at": "2026-11-01T08:00:00+02:00",
  "updated_at": "2026-11-07T09:31:13+02:00"
}
```

`is_online` is computed from `last_seen_at` and
`DEVICE_OFFLINE_AFTER_SECONDS`; it is not a stale stored flag.

### 5.5 Device-facing API

All three endpoints require `X-Device-API-Key`. Missing or wrong keys return
`401` with `WWW-Authenticate: X-Device-API-Key`.

#### `POST /api/device/event/`

```json
{
  "device_id": "FP-FRONT-01",
  "status": "VISITOR",
  "member_id": 9,
  "timestamp": "2026-11-07T09:30:00Z",
  "synced_from_device": false
}
```

- `timestamp` and `synced_from_device` are optional.
- Returns `201` with the created log object.
- Errors: `400` for validation, `401` for auth, `404` for unknown device in the
  heartbeat/sync endpoints.

#### `POST /api/device/heartbeat/`

```json
{ "device_id": "FP-FRONT-01" }
```

```json
{
  "status": "ok",
  "device_id": "FP-FRONT-01",
  "server_time": "2026-11-07T09:30:00+02:00"
}
```

#### `GET /api/device/templates/sync/?device_id=FP-FRONT-01&since=2026-11-01T00:00:00Z`

```json
{
  "count": 1,
  "failed": 0,
  "server_time": "2026-11-07T09:30:00+02:00",
  "templates": [
    {
      "template_id": 3,
      "member_id": 6,
      "username": "amina.k",
      "full_name": "Amina Keza",
      "role": "MEMBER",
      "template_data": "<base64>",
      "updated_at": "2026-11-07T09:29:00+02:00"
    }
  ]
}
```

---

## 6. WebSocket contract

**URL:** `ws(s)://<host>/ws/dashboard/?token=<access-token>`

The token is a query parameter because browsers cannot set headers on a
WebSocket handshake. Always use `wss://` in production.

**Origin validation:** `AllowedHostsOriginValidator` only accepts hosts in
`ALLOWED_HOSTS`.

**On connect**

```json
{
  "type": "connection_established",
  "user": { "username": "Engineer" },
  "timestamp": "2026-11-07T09:30:00+02:00"
}
```

**On every entry**

```json
{
  "type": "entry_event",
  "status": "MEMBER",
  "member": {
    "full_name": "Amina Keza",
    "phone_number": "+250 788 123 401",
    "email": "amina.keza@example.com",
    "photo_url": "http://127.0.0.1:8000/media/members/amina.k/abc.png"
  },
  "device": { "location_name": "Front Door" },
  "timestamp": "2026-11-07T09:31:12+02:00"
}
```

For `UNKNOWN`, `member` is `null`. The dashboard renders only
`UNKNOWN PERSON DETECTED`, the location and the time.

**Keepalive**

Client → server: `{"type": "ping"}`
Server → client: `{"type": "pong", "timestamp": "..."}`

**Close codes**

| Code | Meaning |
| --- | --- |
| `4401` | Missing, invalid or expired JWT |
| `1000` | Normal close (logout/navigation) |

**Reconnection:** exponential backoff 1 s → 2 s → 4 s → 8 s → 15 s, reset on a
successful open. A 25-second ping keeps proxies from closing idle sockets.

---

## 7. Email notifications

**Recipient:** `OWNER_EMAIL`.
**From:** `DEFAULT_FROM_EMAIL`.
**Transport:** Django email backend (`console` in development, `smtp` in
production).

| Status | Subject | Template | Contents |
| --- | --- | --- | --- |
| `MEMBER` | `✅ Entry Granted: {name} at {location}` | `email_member.html` | Green header, photo, name, role, phone, email, location, timestamp |
| `VISITOR` | `🔵 Visitor Arrived: {name} at {location}` | `email_visitor.html` | Blue header, photo, name, role, phone, email, location, timestamp |
| `UNKNOWN` | `🚨 SECURITY ALERT: Unknown person at {location}` | `email_unknown.html` | Red header, `UNKNOWN PERSON DETECTED`, `UNKNOWN / INTRUDER`, location, timestamp, "No registered profile found — no image, name, or contact available", dashboard button |

**Implementation notes**

- Messages are `EmailMultiAlternatives` with HTML + plain text.
- Photos are inline CID attachments (`<entry-photo>`); the template falls back
  to initials when there is no photo.
- The dashboard button points to `FRONTEND_URL/dashboard`.
- Sending happens after the DB commit and is wrapped in `try/except`, so email
  failure never loses the log.
- The timestamp is formatted in the local timezone:
  `Friday, 07 November 2026 at 09:31 EAT`.

Test:

```powershell
python manage.py send_test_email
```

---

## 8. Frontend architecture

### Stack

React 19, Vite 6, React Router 7, Axios, Recharts, lucide-react. Plain
JavaScript (JSX), no TypeScript, no UI framework — the design system lives in
`src/index.css` using CSS custom properties.

### Structure

```
src/
├── main.jsx                 # providers + router
├── App.jsx                  # routes
├── index.css                # design tokens, layout, responsive rules
├── api/client.js            # axios + JWT refresh queue
├── context/
│   ├── AuthContext.jsx      # login/logout/session bootstrap
│   └── ToastContext.jsx     # transient notifications
├── hooks/useDashboardSocket.js
├── utils/{constants,format}.js
├── components/
│   ├── Layout.jsx           # sidebar + topbar + outlet
│   ├── ProtectedRoute.jsx
│   ├── PageHeader.jsx, StatCard.jsx
│   ├── LiveFeed.jsx, EventCard.jsx
│   ├── TrafficChart.jsx, HourlyChart.jsx, StatusDonut.jsx
│   ├── MemberCard.jsx, MemberForm.jsx
│   ├── Modal.jsx, ConfirmDialog.jsx
│   ├── Pagination.jsx, Loader.jsx, EmptyState.jsx, ErrorBanner.jsx
│   ├── Badges.jsx, ChartTooltip.jsx
│   └── LoginPage.jsx, DashboardPage.jsx, MembersPage.jsx,
│       LogsPage.jsx, DevicesPage.jsx, NotFoundPage.jsx
```

### State and data flow

- `AuthContext` owns tokens and the current owner, and exposes
  `login`, `logout` and `isAuthenticated`.
- Pages fetch through `api/client.js`; the interceptor refreshes once on `401`.
- Search/filter requests carry a monotonically increasing sequence number so a
  slow response from an older filter cannot overwrite newer results.
- Dashboard stats are refetched when a WebSocket event arrives (throttled) and
  the live feed is updated locally.
- All async surfaces have loading, empty and error states.

### Responsive design

- Sidebar collapses to a top bar under 900 px.
- Stat cards and charts reflow to a single column on phones.
- Tables become stacked cards on narrow screens.
- Focus-visible rings, semantic labels, and `prefers-reduced-motion` support.

### Build

```powershell
npm.cmd run build
```

`recharts` and React are split into separate chunks so the login screen loads
quickly and vendor code caches independently.

---

## 9. Security model

### Fingerprint data

- Only **templates**, never images, are accepted or stored.
- Templates are encrypted with Fernet before `INSERT`; the database contains
  ciphertext only.
- Decryption happens in memory during device sync and is never logged or
  returned to the dashboard.
- Losing `TEMPLATE_ENCRYPTION_KEY` makes templates unrecoverable — back it up
  separately from the database.
- The API refuses template payloads larger than 64 KB (base64-decoded).

### Dashboard authentication

- JWT bearer tokens (SimpleJWT).
- Access 60 minutes, refresh 7 days, refresh rotation enabled.
- Argon2id is the preferred password hasher; legacy PBKDF2 hashes upgrade on
  next login.
- WebSocket connections validate the same JWT and require an active user.
- Protected routes redirect unauthenticated visitors to `/login`.

### Device authentication

- Shared `DEVICE_API_KEY` sent as `X-Device-API-Key`.
- Constant-time comparison (`secrets.compare_digest`).
- Devices are not Django users and cannot access dashboard endpoints.
- Dashboard users cannot post device events without the key.
- A device must be registered before it can report events.
- Rotate the key if a terminal is lost or compromised.

### Input validation

- DRF serializers validate every field; model constraints back-stop the
  database.
- Uploads are size-limited, content-type checked and Pillow-verified.
- Usernames, names and phone numbers are sanitised and length-bounded.
- Log filters validate status values and numeric ids; dates must be ISO.
- Event role/status consistency and future-timestamp limits are enforced
  server-side.
- Django's `DATA_UPLOAD_MAX_MEMORY_SIZE` caps request bodies at 6 MB.

### Transport and browser hardening

- `CORS_ALLOWED_ORIGINS` is an explicit allow-list; credentials are disabled.
- `CSRF_TRUSTED_ORIGINS` is explicit.
- `X_FRAME_OPTIONS = DENY`, `nosniff`, `same-origin` referrer policy.
- HTTPS redirect and secure cookies can be enabled with environment flags.
- Secrets live in `.env`, which is git-ignored; `.env.example` documents every
  key without values.

### Side-effect isolation

WebSocket broadcasts and emails run in `transaction.on_commit` inside
`try/except`. A failure in either is logged; the access record is still
committed.

---

## 10. Management commands

| Command | Purpose |
| --- | --- |
| `python manage.py create_owner` | Create/update the owner from `OWNER_*` |
| `python manage.py create_device --device-id ID --location "Name"` | Register or rename a device |
| `python manage.py mark_devices_offline` | Flag devices whose last heartbeat is stale |
| `python manage.py seed_demo [--force]` | Demo devices, members, templates and 7 days of logs |
| `python manage.py send_test_email` | Send a test email to `OWNER_EMAIL` |

`seed_demo` creates gradient avatar photos and **placeholder encrypted
templates** — it never creates fingerprint images.

---

## 11. Configuration reference

All backend configuration lives in `backend/.env`.

| Variable | Default | Description |
| --- | --- | --- |
| `DJANGO_SECRET_KEY` | — (required) | Signing key |
| `DJANGO_DEBUG` | `False` | Debug mode |
| `DJANGO_ALLOWED_HOSTS` | `localhost,127.0.0.1` | Comma-separated hosts |
| `PUBLIC_BASE_URL` | `http://localhost:8000` | Absolute media URLs |
| `FRONTEND_URL` | `http://localhost:5173` | Dashboard links in emails |
| `DB_NAME` | `fingerprint_db` | PostgreSQL database |
| `DB_USER` | `postgres` | PostgreSQL user |
| `DB_PASSWORD` | — (required) | PostgreSQL password |
| `DB_HOST` / `DB_PORT` | `localhost` / `5432` | PostgreSQL address |
| `DB_CONN_MAX_AGE` | `60` | Persistent connections (seconds) |
| `OWNER_USERNAME` | `Engineer` | Bootstrap owner username |
| `OWNER_EMAIL` | — | Owner email and alert recipient |
| `OWNER_PASSWORD` | — | Bootstrap owner password |
| `JWT_ACCESS_MINUTES` | `60` | Access token lifetime |
| `JWT_REFRESH_DAYS` | `7` | Refresh token lifetime |
| `DEVICE_API_KEY` | — (required) | Device shared secret |
| `DEVICE_OFFLINE_AFTER_SECONDS` | `120` | Online threshold |
| `TEMPLATE_ENCRYPTION_KEY` | — (required) | Fernet key |
| `MAX_TEMPLATE_BYTES` | `65536` | Template size cap |
| `MAX_PHOTO_BYTES` | `5242880` | Photo size cap |
| `EMAIL_BACKEND` | console | `console` or `smtp` backend |
| `EMAIL_HOST` / `EMAIL_PORT` | `smtp.gmail.com` / `587` | SMTP server |
| `EMAIL_USE_TLS` / `EMAIL_USE_SSL` | `True` / `False` | SMTP security |
| `EMAIL_HOST_USER` / `EMAIL_HOST_PASSWORD` | — | SMTP credentials |
| `DEFAULT_FROM_EMAIL` | `Fingerprint Access <...>` | Sender |
| `EMAIL_TIMEOUT` | `15` | SMTP timeout (seconds) |
| `CORS_ALLOWED_ORIGINS` | `http://localhost:5173,...` | Browser allow-list |
| `CSRF_TRUSTED_ORIGINS` | `http://localhost:5173,...` | CSRF allow-list |
| `REDIS_URL` | empty | Enables the Redis channel layer |
| `TIME_ZONE` | `Africa/Kigali` | Local time for stats/emails |
| `DJANGO_SECURE_SSL_REDIRECT` | `False` | Force HTTPS when not debugging |
| `DJANGO_SECURE_COOKIES` | `False` | Secure cookies when not debugging |

Frontend (`frontend/.env`):

| Variable | Default | Description |
| --- | --- | --- |
| `VITE_API_BASE_URL` | `/api` | API prefix |
| `VITE_WS_URL` | empty | Absolute WebSocket URL; empty = same origin |
| `VITE_BACKEND_URL` | `http://localhost:8000` | Used for absolute links |

---

## 12. Verification checklist

Run these after a fresh install.

### Backend

```powershell
cd backend
python manage.py check
python manage.py makemigrations --check --dry-run   # no pending changes
python manage.py migrate
python manage.py create_owner
python manage.py seed_demo --force
python manage.py send_test_email
```

- [ ] `check` reports no issues.
- [ ] No migration drift.
- [ ] Owner can log in at `/admin/`.
- [ ] Test email prints (console) or arrives (SMTP).

### API

- [ ] `POST /api/auth/login/` returns tokens + user.
- [ ] `GET /api/members/` returns paginated results.
- [ ] Create a member with a photo; `photo_url` opens.
- [ ] Duplicate username → `400`.
- [ ] Invalid image → `400`.
- [ ] `POST /api/members/{id}/enroll/` queues a template.
- [ ] `GET /api/logs/?status=UNKNOWN` filters correctly.
- [ ] `GET /api/dashboard/stats/` returns 7 trend days and 24 hours.
- [ ] Device event with a wrong key → `401`.
- [ ] `UNKNOWN` with a `member_id` → `400`.
- [ ] Template sync returns base64 templates and marks them `SYNCED`.
- [ ] The database column contains ciphertext, not readable template bytes.

### Real time

- [ ] Dashboard shows `connected`.
- [ ] Posting a MEMBER event adds a green card instantly.
- [ ] Posting a VISITOR event adds a blue card instantly.
- [ ] Posting an UNKNOWN event adds a red card with no personal data.
- [ ] Counters and charts update.
- [ ] Invalid/expired token → close code `4401`.

### UI

- [ ] Login redirects to `/dashboard`.
- [ ] Refresh keeps the session; logout clears it.
- [ ] Member create/edit/delete work with photo upload.
- [ ] Logs status and date filters work, including rapid changes.
- [ ] Devices show online/offline and last seen.
- [ ] Layout is usable at 360 px, 768 px and 1440 px.
- [ ] Loading, empty and error states render.
- [ ] `npm.cmd run build` succeeds.

---

## 13. Troubleshooting

| Problem | Diagnosis | Fix |
| --- | --- | --- |
| `ImproperlyConfigured` on startup | Missing secret | Set `DEVICE_API_KEY` / `TEMPLATE_ENCRYPTION_KEY` in `.env` |
| `psycopg` connection refused | PostgreSQL down or wrong port | Start the service; verify `DB_*` |
| `database "fingerprint_db" does not exist` | DB not created | `CREATE DATABASE fingerprint_db;` |
| Login is slow | PBKDF2 fallback | Install `argon2-cffi`; log in again to upgrade the hash |
| `401` on every dashboard call | Expired token / missing header | Sign in again; check the refresh flow |
| WebSocket stuck connecting | WSGI server or wrong proxy | Run Daphne/`runserver`; proxy `/ws` with upgrade headers |
| WebSocket `4401` | Invalid/expired JWT | Re-login; check `VITE_WS_URL` |
| Live feed works but email doesn't | Console backend or SMTP rejected | Check `EMAIL_BACKEND`; use an app password |
| `npm.ps1 cannot be loaded` | PowerShell policy | Use `npm.cmd` |
| Photos 404 | `/media` not served | Dev proxy or Nginx `/media/` |
| `Unknown device_id` | Device not registered | `create_device` |
| `status must be VISITOR` | Role/status mismatch | Send the member's actual role |
| Templates fail to decrypt | Key changed | Restore the original `TEMPLATE_ENCRYPTION_KEY` |
| No events across multiple workers | In-memory channel layer | Set `REDIS_URL` |

---

## 14. Production checklist

- [ ] `DJANGO_DEBUG=False`
- [ ] Strong, unique `DJANGO_SECRET_KEY`
- [ ] Real `DJANGO_ALLOWED_HOSTS`, `CORS_ALLOWED_ORIGINS`,
      `CSRF_TRUSTED_ORIGINS`
- [ ] HTTPS with `DJANGO_SECURE_SSL_REDIRECT=True` and
      `DJANGO_SECURE_COOKIES=True`
- [ ] Redis channel layer (`REDIS_URL`) for multiple workers
- [ ] Daphne/Uvicorn behind Nginx with WebSocket upgrade headers
- [ ] Static and media served by the reverse proxy or object storage
- [ ] SMTP with SPF/DKIM configured; alerts verified end to end
- [ ] PostgreSQL backups **and** a separate backup of
      `TEMPLATE_ENCRYPTION_KEY`
- [ ] Device API key stored securely on terminals; rotation plan documented
- [ ] Owner password changed from the development default
- [ ] Log retention policy agreed
- [ ] Monitoring for device heartbeats and failed email delivery
- [ ] Frontend built with production API/WS URLs and served over HTTPS

---

*Built as a monorepo: Django backend, React dashboard, PostgreSQL, Channels,
JWT, API-key device auth, encrypted templates, live WebSocket feed and HTML
email alerts.*
