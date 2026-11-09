You are an expert full-stack engineer. Build me a complete, production-quality 
biometric access-control and visitor-monitoring web system. Follow every 
requirement exactly. Do not simplify, do not skip modules, do not invent 
features I did not ask for.

═══════════════════════════════════════════════════════════════
1. PROJECT OVERVIEW
═══════════════════════════════════════════════════════════════
A home/organization entry system where people are identified by fingerprint.
An embedded device (fingerprint sensor + buzzer) captures and matches 
fingerprints LOCALLY, then reports the RESULT to this web backend. The 
backend stores profiles, logs every entry, updates a real-time dashboard, 
and emails the owner. There is NO LCD and NO camera on the device.

Three identity categories:
- REGISTERED MEMBER   → authorized family/staff
- REGISTERED VISITOR  → authorized special visitor (pre-enrolled)
- UNKNOWN / INTRUDER  → no fingerprint match (unregistered person)

═══════════════════════════════════════════════════════════════
2. TECH STACK (MANDATORY — do not substitute)
═══════════════════════════════════════════════════════════════
- Frontend : React (with Vite), modern hooks, responsive dashboard UI
- Backend  : Django + Django REST Framework
- Real-time: Django Channels (WebSocket) for live dashboard updates
- Database : PostgreSQL
- Email    : Django SMTP email backend
- Auth     : JWT authentication for the owner/admin dashboard
- Language : Python 3.11+, JavaScript/TypeScript

═══════════════════════════════════════════════════════════════
3. SYSTEM ARCHITECTURE (HYBRID — EDGE MATCHING)
═══════════════════════════════════════════════════════════════
- The embedded device stores fingerprint TEMPLATES locally and performs 
  matching on-device (fast + privacy-preserving).
- The device sends ONLY THE RESULT to Django via HTTP POST (never raw 
  fingerprint images).
- Django is the MASTER SOURCE OF TRUTH for profiles and templates.
- Django logs events, pushes real-time updates to React via WebSocket, 
  and sends emails.
- If the network is down, the device buffers logs and syncs later.

═══════════════════════════════════════════════════════════════
4. DATABASE SCHEMA (PostgreSQL)
═══════════════════════════════════════════════════════════════
Design and implement these models with proper relations, indexes, 
timestamps, and constraints:

Member
  - id (PK)
  - username (unique)
  - full_name
  - phone_number
  - email
  - role: choices = MEMBER | VISITOR
  - photo (ImageField — uploaded at registration, NOT from a camera)
  - is_active (bool)
  - created_at, updated_at

FingerprintTemplate
  - id (PK)
  - member (FK → Member, one-to-one or one-to-many)
  - template_data (encrypted/binary — never raw image)
  - sync_status: choices = PENDING | SYNCED
  - last_synced_at
  - created_at

Device
  - id (PK)
  - device_id (unique hardware identifier)
  - location_name (e.g. "Front Door")
  - is_online (bool)
  - last_seen_at

EntryLog
  - id (PK)
  - member (FK → Member, NULLABLE — null means UNKNOWN)
  - device (FK → Device)
  - status: choices = MEMBER | VISITOR | UNKNOWN
  - timestamp (indexed)
  - synced_from_device (bool)

═══════════════════════════════════════════════════════════════
5. DJANGO REST API ENDPOINTS
═══════════════════════════════════════════════════════════════
Implement these endpoints with DRF, proper serializers, permissions, 
and validation:

DEVICE-FACING (authenticated via device API key):
  POST /api/device/event/          → device reports an entry result
       payload: { device_id, status, member_id (nullable), timestamp }
       behavior: create EntryLog, trigger email, push WebSocket event
  GET  /api/device/templates/sync/ → device fetches latest templates
  POST /api/device/heartbeat/      → device reports it is online

DASHBOARD-FACING (JWT-authenticated owner):
  POST   /api/auth/login/
  GET    /api/members/             → list all members
  POST   /api/members/             → create member (multipart: profile + photo)
  GET    /api/members/{id}/
  PUT    /api/members/{id}/
  DELETE /api/members/{id}/
  POST   /api/members/{id}/enroll/ → mark template for enrollment/sync
  GET    /api/logs/                → list entry logs (filter by status, date)
  GET    /api/devices/
  GET    /api/dashboard/stats/     → counts: today's entries, unknowns, etc.

═══════════════════════════════════════════════════════════════
6. REAL-TIME WEBSOCKET
═══════════════════════════════════════════════════════════════
- Use Django Channels with a WebSocket consumer.
- When an EntryLog is created, broadcast a JSON event:
  {
    "type": "entry_event",
    "status": "MEMBER" | "VISITOR" | "UNKNOWN",
    "member": { full_name, phone_number, email, photo_url } | null,
    "device": { location_name },
    "timestamp": "ISO-8601"
  }
- React dashboard subscribes and updates live without page refresh.

═══════════════════════════════════════════════════════════════
7. EMAIL NOTIFICATIONS (sent by Django on every event)
═══════════════════════════════════════════════════════════════
Three HTML email templates, sent to the owner immediately:

A) MEMBER (green)  — Subject: "✅ Entry Granted: {name} at {location}"
   Body shows: photo, name, role, phone, email, location, timestamp.
B) VISITOR (blue)  — Subject: "🔵 Visitor Arrived: {name} at {location}"
   Body shows: photo, name, role, phone, email, location, timestamp.
C) UNKNOWN (red)   — Subject: "🚨 SECURITY ALERT: Unknown person at {location}"
   Body shows: "UNKNOWN PERSON DETECTED", location, timestamp,
   status "UNKNOWN / INTRUDER", note "No registered profile found — 
   no image, name, or contact available", and a link to the dashboard.

═══════════════════════════════════════════════════════════════
8. REACT DASHBOARD (pages + components)
═══════════════════════════════════════════════════════════════
Pages:
  1. Login page (JWT)
  2. Dashboard home:
     - Live event feed (WebSocket) with colored cards:
         🟢 green = member, 🔵 blue = visitor, 🔴 red = unknown
     - Green/blue cards show photo, name, phone, email, location, time
     - Red cards show "UNKNOWN PERSON DETECTED" + location + time only
     - Summary stats: total today, members today, visitors today, 
       unknowns today
  3. Members page: list, create (upload photo + details), edit, delete
  4. Logs page: full history with filters (status, date range)
  5. Devices page: list devices, online status, last seen

UI requirements:
  - Clean, modern, responsive
  - Clear color coding (green/blue/red) consistent across UI and emails
  - Real-time updates via WebSocket
  - Loading and error states handled

═══════════════════════════════════════════════════════════════
9. SECURITY REQUIREMENTS
═══════════════════════════════════════════════════════════════
- Store fingerprint templates encrypted — NEVER store raw images.
- JWT auth for dashboard; API-key auth for the device.
- Validate and sanitize all inputs.
- Use environment variables for secrets (DB, email, keys).
- CORS configured correctly for React ↔ Django.

═══════════════════════════════════════════════════════════════
10. PROJECT STRUCTURE & DELIVERABLES
═══════════════════════════════════════════════════════════════
Deliver a monorepo with:
  /backend   → Django project, apps (accounts, members, devices, logs, 
               notifications), Channels setup, migrations, .env.example
  /frontend  → React (Vite) app, pages, components, API client, 
               WebSocket hook
  README.md  → full setup instructions (Postgres, env vars, migrations, 
               run backend, run frontend, test email)

═══════════════════════════════════════════════════════════════
11. BUILD ORDER (IMPORTANT — build in this sequence)
═══════════════════════════════════════════════════════════════
Do NOT attempt everything in one shot. Build and verify in this order:
  Step 1: Backend project scaffold + PostgreSQL config + models + migrations
  Step 2: DRF serializers + auth (JWT) + member CRUD endpoints
  Step 3: Device endpoints (event, sync, heartbeat) + EntryLog creation
  Step 4: Django Channels + WebSocket consumer + broadcast on event
  Step 5: Email templates + sending logic (test with console backend first)
  Step 6: React scaffold + auth + API client
  Step 7: Dashboard live feed + WebSocket hook + colored cards
  Step 8: Members, Logs, Devices pages
  Step 9: Polish, error handling, README
After each step, stop and tell me what was built and what to test next.

═══════════════════════════════════════════════════════════════
12. WHAT NOT TO DO
═══════════════════════════════════════════════════════════════
- Do NOT add a camera, face recognition, LCD, or mobile app.
- Do NOT do matching on the server — matching is on-device (edge).
- Do NOT store raw fingerprint images.
- Do NOT skip the WebSocket real-time layer.
- Do NOT use SQLite — PostgreSQL only.
- Do NOT put all code in one file — use proper Django apps and React components.

Begin with Step 1. Confirm you understand the full spec, list the 
files you will create for Step 1, then produce the code.