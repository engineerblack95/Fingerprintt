# Fingerprint Access Control & Visitor Monitoring

A production-quality biometric access-control system with **edge matching**. A
fingerprint terminal matches prints locally and reports only the *result* to
this server. Django stores profiles and encrypted templates, records every
entry, pushes live events to a React dashboard over WebSockets, and emails the
owner for each event.

Three identity categories are supported everywhere (UI, emails, logs):

| Category | Colour | Meaning |
| --- | --- | --- |
| `MEMBER` | 🟢 green | Registered family member / staff |
| `VISITOR` | 🔵 blue | Pre-enrolled, authorized visitor |
| `UNKNOWN` | 🔴 red | No match — unknown person / intruder |

> **Privacy by design:** the server never receives or stores fingerprint
> images. Templates are encrypted at rest with Fernet (AES-128-CBC + HMAC), and
> decrypted only in memory when a registered device syncs.

---

## Table of contents

1. [Architecture](#architecture)
2. [Repository layout](#repository-layout)
3. [Prerequisites](#prerequisites)
4. [PostgreSQL setup](#postgresql-setup)
5. [Backend setup](#backend-setup)
6. [Database, owner and demo data](#database-owner-and-demo-data)
7. [Run the backend](#run-the-backend)
8. [Frontend setup](#frontend-setup)
9. [Sign in](#sign-in)
10. [Verify real-time events and email](#verify-real-time-events-and-email)
11. [Device API examples](#device-api-examples)
12. [Production deployment](#production-deployment)
13. [Troubleshooting](#troubleshooting)
14. [Further documentation](#further-documentation)

---

## Architecture

```
┌────────────────────────────┐        HTTPS + X-Device-API-Key
│  Fingerprint terminal      │  ───────────────────────────────┐
│  • sensor + buzzer         │                                 │
│  • local template store    │  POST /api/device/event/         │
│  • ON-DEVICE matching      │  GET  /api/device/templates/sync/│
└────────────────────────────┘  POST /api/device/heartbeat/    │
                                                               ▼
                                                  ┌─────────────────────────┐
                                                  │  Django 6 + DRF         │
                                                  │  PostgreSQL 17          │
                                                  │  Channels (WebSocket)   │
                                                  │  SMTP email             │
                                                  └───────────┬─────────────┘
                                                              │
                                   JWT + wss://ws/dashboard/  │
                                                              ▼
                                                  ┌─────────────────────────┐
                                                  │  React 19 + Vite        │
                                                  │  live feed + charts     │
                                                  │  members / logs / devices│
                                                  └─────────────────────────┘
```

**Flow for one entry**

1. The device scans a finger and matches it against its local templates.
2. It posts the result (`MEMBER`, `VISITOR` or `UNKNOWN`) to
   `/api/device/event/` with the device API key.
3. Django validates the event, creates an `EntryLog`, marks the device online,
   broadcasts an `entry_event` over the `dashboard` channel group, and sends the
   matching HTML email to the owner — after the DB transaction commits.
4. The React dashboard prepends a coloured card and refreshes its counters.

If the network is down the device buffers events and replays them later; Django
flags anything older than two minutes as `synced_from_device = true`.

---

## Repository layout

```
fingerprint/
├── backend/
│   ├── accounts/        # owner User model, JWT login/refresh/me
│   ├── members/         # Member + FingerprintTemplate, encryption, CRUD, enroll
│   ├── devices/         # Device model, API-key auth, device endpoints
│   ├── logs/            # EntryLog, stats, filters, Channels consumer, seed_demo
│   ├── notifications/   # 3 HTML email templates + sending logic
│   ├── config/          # settings, ASGI/WSGI, root URLs, pagination, errors
│   ├── media/           # uploaded profile photos (git-ignored)
│   ├── manage.py
│   ├── requirements.txt
│   ├── .env             # local secrets (git-ignored)
│   └── .env.example     # documented template
├── frontend/
│   ├── src/
│   │   ├── api/         # axios client with JWT refresh interceptor
│   │   ├── components/  # layout, cards, charts, modals, tables
│   │   ├── context/     # auth + toast providers
│   │   ├── hooks/       # useDashboardSocket (auto-reconnect)
│   │   ├── pages/       # Login, Dashboard, Members, Logs, Devices, 404
│   │   └── utils/       # formatting + status constants
│   ├── vite.config.js   # dev + preview proxy for /api, /media, /ws
│   └── package.json
├── README.md
├── DOCUMENTATION.md     # step-by-step build & technical reference
└── instructions.md      # original specification
```

---

## Prerequisites

- **Python 3.11+** (verified on Python 3.14)
- **PostgreSQL 14+** (verified on PostgreSQL 17)
- **Node.js 18+** and npm (verified with the bundled npm 10/11)
- Windows PowerShell, macOS or Linux shell

On Windows PowerShell, use `npm.cmd` instead of `npm` if script execution is
restricted (`npm.ps1 cannot be loaded`).

---

## PostgreSQL setup

Create the database once. Replace the password with your own.

```powershell
# psql must be on PATH (PostgreSQL bin folder)
$env:PGPASSWORD = "Paccy@100"
psql -U postgres -h localhost -c "CREATE DATABASE fingerprint_db;"
```

If the database already exists PostgreSQL returns an error — that is safe to
ignore.

The local `.env` is already configured for:

```
DB_NAME=fingerprint_db
DB_USER=postgres
DB_PASSWORD=Paccy@100
DB_HOST=localhost
DB_PORT=5432
```

> Change `DB_PASSWORD` in `backend/.env` to match your PostgreSQL password
> before running migrations.

---

## Backend setup

```powershell
cd X:\fingerprint\backend

# Optional but recommended: isolated virtual environment
python -m venv .venv
.\.venv\Scripts\Activate.ps1

python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

### Environment variables

Copy the template and edit every value:

```powershell
Copy-Item .env.example .env
notepad .env
```

Required secrets:

| Variable | Purpose |
| --- | --- |
| `DJANGO_SECRET_KEY` | Django cryptographic signing |
| `DB_*` | PostgreSQL connection |
| `DEVICE_API_KEY` | Shared key sent by terminals as `X-Device-API-Key` |
| `TEMPLATE_ENCRYPTION_KEY` | Fernet key for fingerprint templates |
| `OWNER_*` | Bootstrap dashboard account |
| `OWNER_EMAIL` | Alert recipient |
| `EMAIL_*` | SMTP configuration |

Generate strong values:

```powershell
python -c "import secrets; print(secrets.token_urlsafe(50))"
python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
```

**Never reuse the example secrets and never commit `.env`.** The project
refuses to start without `DEVICE_API_KEY` and `TEMPLATE_ENCRYPTION_KEY`.

---

## Database, owner and demo data

```powershell
cd X:\fingerprint\backend

python manage.py migrate
python manage.py create_owner                 # uses OWNER_* from .env
python manage.py create_device --device-id FP-FRONT-01 --location "Front Door"
python manage.py create_device --device-id FP-SIDE-02  --location "Side Gate"

# Optional: realistic demo members, devices, encrypted templates and 7 days of logs
python manage.py seed_demo --force
```

`seed_demo --force` deletes existing members/logs and reseeds. Skip it if you
want to start with an empty system.

---

## Run the backend

```powershell
cd X:\fingerprint\backend
python manage.py runserver 0.0.0.0:8000
```

`daphne` is first in `INSTALLED_APPS`, so `runserver` serves **both HTTP and
WebSocket** traffic (ASGI). Do not run `runserver --noreload` behind a WSGI
server if you need live events.

Health check:

```powershell
Invoke-RestMethod http://127.0.0.1:8000/api/devices/ -Headers @{ Authorization = "Bearer <token>" }
```

Django admin is available at <http://127.0.0.1:8000/admin/> using the owner
account.

---

## Frontend setup

```powershell
cd X:\fingerprint\frontend
npm.cmd install
npm.cmd run dev
```

Open <http://localhost:5173>.

`frontend/.env`:

```
VITE_API_BASE_URL=/api
VITE_WS_URL=                 # empty = same origin /ws/dashboard/
VITE_BACKEND_URL=http://localhost:8000
```

Vite proxies `/api`, `/media` and `/ws` to Django in both `dev` and
`preview` modes, so no CORS setup is needed in development.

Production build:

```powershell
npm.cmd run build
npm.cmd run preview          # serves dist/ on http://localhost:4173 with proxy
```

---

## Sign in

Use the credentials configured in `backend/.env` (`OWNER_USERNAME`,
`OWNER_PASSWORD`). The local development values are:

```
Username: Engineer
Password: Landload@100
```

Change these before deploying. Access tokens last 60 minutes; refresh tokens
last 7 days and rotate on use.

---

## Verify real-time events and email

### 1. Watch the dashboard

Sign in and open **Dashboard**. Keep the browser open.

### 2. Send a MEMBER event

```powershell
$key = (Get-Content .env | Select-String '^DEVICE_API_KEY=').ToString().Split('=',2)[1]
$body = @{
  device_id  = "FP-FRONT-01"
  status     = "MEMBER"
  member_id  = 6
  timestamp  = (Get-Date).ToUniversalTime().ToString("o")
} | ConvertTo-Json

Invoke-RestMethod -Method Post http://127.0.0.1:8000/api/device/event/ `
  -Headers @{ "X-Device-API-Key" = $key } `
  -ContentType "application/json" -Body $body
```

A **green** card should appear instantly, the counters should increase, and the
backend console should print the HTML email (console email backend).

### 3. Send an UNKNOWN event

```powershell
$body = @{ device_id = "FP-FRONT-01"; status = "UNKNOWN"; member_id = $null } | ConvertTo-Json

Invoke-RestMethod -Method Post http://127.0.0.1:8000/api/device/event/ `
  -Headers @{ "X-Device-API-Key" = $key } `
  -ContentType "application/json" -Body $body
```

A **red** card appears with only `UNKNOWN PERSON DETECTED`, the location and the
time — no personal data.

### 4. Test email delivery

```powershell
cd X:\fingerprint\backend
python manage.py send_test_email
```

With `EMAIL_BACKEND=django.core.mail.backends.console.EmailBackend` the message
is printed to the terminal. Switch to SMTP in `.env` to send real mail:

```
EMAIL_BACKEND=django.core.mail.backends.smtp.EmailBackend
EMAIL_HOST=smtp.gmail.com
EMAIL_PORT=587
EMAIL_USE_TLS=True
EMAIL_HOST_USER=your-address@gmail.com
EMAIL_HOST_PASSWORD=your-app-password
DEFAULT_FROM_EMAIL=Fingerprint Access <your-address@gmail.com>
OWNER_EMAIL=your-address@gmail.com
```

For Gmail, use a 16-character **App Password**, not your normal password.

---

## Device API examples

All device calls require the header:

```
X-Device-API-Key: <DEVICE_API_KEY>
```

| Method | Path | Purpose |
| --- | --- | --- |
| `POST` | `/api/device/event/` | Report a local match result |
| `GET` | `/api/device/templates/sync/?device_id=...` | Fetch templates updated since the last sync |
| `POST` | `/api/device/heartbeat/` | Report that the terminal is alive |

### Event payload

```json
{
  "device_id": "FP-FRONT-01",
  "status": "MEMBER",
  "member_id": 6,
  "timestamp": "2026-11-07T09:30:00Z",
  "synced_from_device": false
}
```

Rules enforced by the server:

- `UNKNOWN` must send `member_id: null`.
- `MEMBER`/`VISITOR` must send an existing, active member whose role matches the
  status.
- The device must be registered first.
- Timestamps more than 5 minutes in the future are rejected; events older than
  2 minutes are marked as buffered/offline syncs.

### Heartbeat

```powershell
Invoke-RestMethod -Method Post http://127.0.0.1:8000/api/device/heartbeat/ `
  -Headers @{ "X-Device-API-Key" = $key } `
  -ContentType "application/json" `
  -Body (@{ device_id = "FP-FRONT-01" } | ConvertTo-Json)
```

### Template sync

```powershell
Invoke-RestMethod "http://127.0.0.1:8000/api/device/templates/sync/?device_id=FP-FRONT-01" `
  -Headers @{ "X-Device-API-Key" = $key }
```

Response (abridged):

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
      "template_data": "base64-encrypted-template-bytes",
      "updated_at": "2026-11-07T09:29:00+02:00"
    }
  ]
}
```

Only templates whose member is active are returned. `template_data` is the
decrypted **template** (never an image), base64-encoded for transport. Add
`&since=2026-11-01T00:00:00Z` for incremental syncs.

---

## Production deployment

### Backend

1. Set `DJANGO_DEBUG=False` and a strong, unique `DJANGO_SECRET_KEY`.
2. Set `DJANGO_ALLOWED_HOSTS`, `CORS_ALLOWED_ORIGINS` and
   `CSRF_TRUSTED_ORIGINS` to your real domains.
3. Set `DJANGO_SECURE_SSL_REDIRECT=True` and `DJANGO_SECURE_COOKIES=True`
   behind HTTPS.
4. Configure **Redis** for the channel layer so multiple Daphne workers share
   broadcasts:
   ```
   REDIS_URL=redis://127.0.0.1:6379/0
   ```
   Install and run `redis-server`; `channels-redis` is already in
   `requirements.txt`.
5. Run Daphne (or Uvicorn) behind Nginx:
   ```bash
   daphne -b 0.0.0.0 -p 8000 config.asgi:application
   ```
6. Serve `/static/` and `/media/` through Nginx (or WhiteNoise for static).
7. Use real SMTP credentials and verify SPF/DKIM for deliverability.
8. Back up PostgreSQL and **back up `TEMPLATE_ENCRYPTION_KEY`** — losing it makes
   every stored template unreadable.
9. Restrict `X-Device-API-Key` distribution and rotate it if a terminal is
   compromised.
10. Use `wss://` for the dashboard socket and serve the SPA over HTTPS.

### Frontend

```powershell
cd frontend
npm.cmd run build
```

Deploy `frontend/dist/` behind the same origin (recommended) or a CDN. If the
API lives on another origin, set `VITE_API_BASE_URL` and `VITE_WS_URL` at build
time and add that origin to the backend CORS/CSRF settings.

### Reverse proxy sketch (Nginx)

```nginx
location /api/   { proxy_pass http://127.0.0.1:8000; }
location /media/ { proxy_pass http://127.0.0.1:8000; }
location /ws/ {
    proxy_pass http://127.0.0.1:8000;
    proxy_http_version 1.1;
    proxy_set_header Upgrade $http_upgrade;
    proxy_set_header Connection "upgrade";
}
location / { root /var/www/fingerprint/dist; try_files $uri /index.html; }
```

---

## Troubleshooting

| Symptom | Cause / fix |
| --- | --- |
| `ImproperlyConfigured: DEVICE_API_KEY must be set` | Missing `.env` value. Generate one and restart. |
| `connection to server at "localhost" ... failed` | PostgreSQL not running or wrong `DB_*` values. |
| Login takes several seconds | Password hasher fell back to PBKDF2. Ensure `argon2-cffi` is installed; Argon2 hashes upgrade on next login. |
| Live feed stays "connecting" | Backend must run through ASGI (`runserver` with daphne). Check `/ws/dashboard/?token=...` in devtools. |
| `npm.ps1 cannot be loaded` | Use `npm.cmd`. |
| Email printed to console instead of sent | `EMAIL_BACKEND` is still the console backend; switch to SMTP. |
| Photos 404 in the dashboard | Make sure `/media` is proxied (dev) or served by Nginx (prod). |
| WebSocket closes with code `4401` | Missing/expired JWT in the `?token=` query string; sign in again. |
| Device gets `401` | Wrong or missing `X-Device-API-Key`. |
| Device gets `400 Unknown device_id` | Register it with `python manage.py create_device ...`. |

---

## Further documentation

See **[DOCUMENTATION.md](./DOCUMENTATION.md)** for:

- the complete step-by-step build (Step 1 → Step 9),
- data model and constraint details,
- every endpoint with request/response examples,
- the exact WebSocket contract,
- email template behaviour,
- frontend component structure,
- the security model and validation rules.
