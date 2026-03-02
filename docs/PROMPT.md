You are a senior full-stack engineer who loves Python and React.
Build a production-grade, offline-first Oilfield Maintenance Work Order
and Call-Out Tracking System (CMMS).

Do NOT ask clarifying questions. If anything is ambiguous, pick a sensible
default, implement it, and document it in ASSUMPTIONS.md.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
OUTPUT FORMAT (MANDATORY)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

1. Print the complete monorepo file tree first.
2. Print every file using explicit markers:
     ---FILE_START: path/to/file---
     <full file contents>
     ---FILE_END---
3. If the output is too large for one response, emit labeled chunks:
     CHUNK 1/N ... CHUNK 2/N ...
   End each chunk with: Reply CONTINUE to receive the next chunk.
4. Never reference a file you have not yet emitted unless it is in
   the same chunk.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
TECH STACK
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Backend:
- Python 3.12, FastAPI, SQLAlchemy 2.x (async + asyncpg), Alembic migrations
- PostgreSQL 16 (primary DB)
- Redis 7 — pub/sub fan-out, caching, rate limit counters, Celery broker
- Celery + Celery Beat — SLA escalation, PM generation, notifications,
  budget recalculation, rollup precomputation
- WebSockets (native FastAPI/Starlette) + Redis pub/sub for real-time
  fan-out across multiple Uvicorn workers
- Firebase Admin SDK — push notifications (APNs + FCM under one API)
- AWS S3 / local MinIO — photo and document storage (pre-signed URLs only;
  file bytes never pass through the API server)
- slowapi (Redis-backed) — rate limiting on auth and write endpoints
- qrcode Python library — server-side QR PNG generation
- Python csv module — CSV export on all report endpoints
- SendGrid API — transactional email (smtplib stdout fallback for dev)
- pyotp — TOTP-based MFA
- OpenTelemetry (opentelemetry-sdk + opentelemetry-instrumentation-fastapi)
- Prometheus Python client — /metrics endpoint
- Sentry SDK — error monitoring
- pytest + httpx — backend tests
- passlib[bcrypt] — password hashing (cost factor 12)

Frontend (PWA — one codebase, all devices):
- React 18, TypeScript, Vite
- Zustand — client state (auth, notifications, offline queue, UI)
- TanStack Query v5 — server state + optimistic updates
- React Router v6
- Tailwind CSS + shadcn/ui
- Recharts — dashboard charts and reports
- vite-plugin-pwa + Workbox — service worker, offline cache, manifest
- idb library — IndexedDB for offline write queue
- Firebase JS SDK v10+ (modular) — FCM token registration
- html5-qrcode — QR/barcode scanning in the browser
- Custom reconnecting WebSocket hook — do NOT use Socket.io-client

Monorepo layout:
  /backend
  /frontend
  /infra        (docker-compose, MinIO config)
  /scripts      (seed.py, generate_qr_sheet.py)

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
ASSUMPTIONS.md — WRITE THIS FILE FIRST
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Document every default decision. Must include at minimum:

Multi-tenancy:
- Multi-tenant SaaS by default: org_id on every operational table,
  enforced on every query and every endpoint that accepts an entity ID.
- OWASP Broken Object Level Authorization (BOLA) is the target threat;
  object-level checks are required in every handler.
- Single-tenant operation: create one org and disable self-serve
  registration.

Time and timezone:
- All timestamps stored in UTC.
- Each Site stores site_timezone (IANA string).
- Seed default timezone: America/Chicago.
- Shift schedules stored per Area: name, start/end local time,
  days-of-week, site_timezone reference.

Authentication defaults:
- Email + password for MVP.
- Access token TTL: 15 minutes.
- Refresh token TTL: 7 days, rotate on every use.
- Revoked refresh token IDs stored in Redis SET.
- MFA required for ADMIN and SUPERVISOR by default (TOTP via pyotp);
  configurable per org for other roles.

SLA defaults (fully admin-configurable per Area + per Priority):
  IMMEDIATE: acknowledge 15 min | first update 30 min | resolve 4 h
  URGENT:    acknowledge 60 min | first update 2 h   | resolve 12 h
  SCHEDULED: acknowledge 8 h   | first update 24 h  | resolve 5 d
  DEFERRED:  acknowledge 24 h  | first update 72 h  | resolve 14 d

Offline:
- Open work orders always cached on device.
- Closed work orders: last 90 days cached (configurable per org).
- Durable write queue — unsynced changes are NEVER auto-deleted.
  Warn user at 24 h and 48 h of unsynced changes.
- Conflict resolution: server FSM is authoritative for status
  transitions; timeline events are append-only; editable fields are
  last-write-wins with full audit history.

Privacy:
- No continuous live location tracking.
- Optional GPS snapshot at job accept / start / resolve
  (configurable per org, off by default).

Currency:
- USD default; org.currency_code (ISO 4217) is org-level configurable.

Units:
- Store measurements with value + unit metadata.
- Default UI: US customary (oilfield-standard).

Labor rate:
- org.config stores a default_labor_rate_per_hour (decimal).
- Used for budget actual_spend calculation alongside parts cost.
- Shown only to users with CAN_VIEW_COSTS permission.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
CRITICAL RULE: MULTI-TENANCY AND DATA ISOLATION
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Every table that contains operational data MUST have an org_id column.
Every SQLAlchemy query in the service layer MUST filter by org_id.
Every endpoint that accepts an entity ID MUST verify the entity belongs
to the requesting user's org before returning or mutating data.
A missing org_id filter or missing object-level check is a critical
security bug — not a minor oversight.
The test_org_isolation.py suite must prove these rules hold before the
backend is considered complete.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
DATABASE SCHEMA — BUILD ALL MODELS AND MIGRATIONS
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

### Location Hierarchy (5 levels)

Organization:
  id (UUID), name, slug, logo_url,
  currency_code (ISO 4217 string, default "USD"),
  config (JSONB), created_at
  config structure: {
    "sla": {
      "IMMEDIATE": { "ack_minutes": 15, "first_update_minutes": 30,
                     "resolve_hours": 4 },
      "URGENT":    { "ack_minutes": 60, "first_update_minutes": 120,
                     "resolve_hours": 12 },
      "SCHEDULED": { "ack_minutes": 480, "first_update_minutes": 1440,
                     "resolve_hours": 120 },
      "DEFERRED":  { "ack_minutes": 1440, "first_update_minutes": 4320,
                     "resolve_hours": 336 }
    },
    "escalation_enabled": true,
    "closed_wo_cache_days": 90,
    "gps_snapshot_on_accept": false,
    "gps_snapshot_on_start": false,
    "gps_snapshot_on_resolve": false,
    "timezone": "America/Chicago",
    "mfa_required_roles": ["ADMIN", "SUPERVISOR"],
    "default_labor_rate_per_hour": 75.00
  }

Area:
  id, org_id, name, description, timezone (IANA string), is_active

Location:
  id, org_id, area_id, name, address, gps_lat, gps_lng,
  qr_code_token (unique UUID), is_active, created_at

Site:
  id, org_id, location_id, name,
  type ENUM(WELL_SITE, PLANT, BUILDING, APARTMENT, LINE, SUITE,
            COMPRESSOR_STATION, TANK_BATTERY, SEPARATOR, OTHER),
  address, gps_lat, gps_lng, site_timezone (IANA string),
  qr_code_token (unique UUID), is_active, created_at
  -- Site is the atomic unit where work happens.
  -- Location groups Sites (e.g., a field location with 12 well sites).
  -- Work orders are created at the Site level (not Location level).

Asset:
  id, org_id, site_id, name, asset_type, manufacturer, model,
  serial_number, install_date, warranty_expiry,
  qr_code_token (unique UUID),
  notes, is_active, created_at
  -- Assets live under Sites.
  -- Work orders attach to a Site OR to a specific Asset within a Site.
  -- Asset-level attachment enables per-asset failure history and PM.

### Shift Schedules

ShiftSchedule:
  id, org_id, area_id, name,
  start_time (TIME), end_time (TIME),
  days_of_week (int[] — 0=Mon through 6=Sun),
  timezone (IANA string), is_active

UserShiftAssignment:
  user_id, shift_schedule_id

### Users & Access

User:
  id, org_id, name, email, phone, password_hash,
  role ENUM(SUPER_ADMIN, ADMIN, SUPERVISOR, OPERATOR, TECHNICIAN,
            READ_ONLY, COST_ANALYST),
  is_active, avatar_url,
  totp_secret (nullable — set when MFA enrolled),
  mfa_enabled (bool, default false),
  fcm_token (Firebase push token, updated on every login),
  email_notifications_enabled (bool, default true),
  last_login_at, created_at, updated_at

UserAreaAssignment:
  user_id, area_id
  -- Many-to-many. Admin controls this.
  -- Swapping a tech between areas = DELETE old rows + INSERT new rows.

UserPermission:
  user_id, permission ENUM(
    CAN_VIEW_COSTS,
    CAN_MANAGE_BUDGET,
    CAN_VIEW_INCENTIVES,
    CAN_MANAGE_INVENTORY,
    CAN_MANAGE_USERS,
    CAN_VIEW_AUDIT_LOG,
    CAN_MANAGE_PM_TEMPLATES
  )
  -- Fine-grained flags layered on top of role.
  -- Example: TECHNICIAN granted CAN_VIEW_COSTS without becoming SUPERVISOR.

TechnicianCertification:
  id, user_id, cert_name, cert_number, issued_by,
  issued_date, expires_at, notes

OnCallSchedule:
  id, org_id, area_id, user_id,
  start_dt (timestamptz), end_dt (timestamptz),
  priority ENUM(PRIMARY, SECONDARY)
  -- Escalation looks up PRIMARY for the area at escalation time.
  -- Falls back to SECONDARY if PRIMARY unreachable.

### Notification Preferences

UserNotificationPref:
  user_id, area_id,
  push_enabled (bool),
  email_enabled (bool),
  on_shift (bool)
  -- on_shift=false suppresses push. Email still fires for ESCALATED.
  -- One row per user per area.

### Work Orders

WorkOrder:
  id (UUID), org_id, area_id, location_id, site_id,
  asset_id (nullable FK → Asset),

  human_readable_number (string, format WO-YYYY-NNNNNN,
    auto-generated, unique per org, indexed.
    IMPORTANT: field workers reference this number verbally on radio
    and in shift handover reports. It must appear prominently on every
    card, notification, email, and printed QR sheet. UUID references
    are useless in the field.),

  title, description,
  type ENUM(REACTIVE, PREVENTIVE, INSPECTION, CORRECTIVE),

  priority ENUM(IMMEDIATE, URGENT, SCHEDULED, DEFERRED),
  -- IMMEDIATE: safety or production-critical. Stop everything.
  --   Examples: H2S alarm, uncontrolled release, well blowout risk,
  --   complete production loss.
  -- URGENT: needs attention before end of current shift.
  -- SCHEDULED: plan into next work cycle, no immediate risk.
  -- DEFERRED: low priority, do when resources allow.

  status ENUM(
    NEW,              -- just created, unassigned
    ASSIGNED,         -- supervisor assigned a tech, not yet accepted
    ACCEPTED,         -- tech confirmed they are taking the job + set ETA
    IN_PROGRESS,      -- tech actively working on site
    WAITING_ON_OPS,   -- tech on site but blocked: needs operator action
                      -- (e.g., depressurize line, isolate equipment)
    WAITING_ON_PARTS, -- tech confirmed issue but part not available;
                      -- tech leaves site, returns when part arrives
    RESOLVED,         -- tech documented the fix and marked complete
    VERIFIED,         -- operator/supervisor confirmed fix worked
                      -- (the person who reported the problem signs off)
    CLOSED            -- supervisor/admin formally closed the record
  ),

  FSM transition rules (server enforces; invalid transitions → 422):
    NEW → ASSIGNED          SUPERVISOR, ADMIN (by assigning a tech)
    NEW → ACCEPTED          TECHNICIAN self-assigns + accepts
    ASSIGNED → ACCEPTED     assigned TECHNICIAN or SUPERVISOR
    ACCEPTED → IN_PROGRESS  assigned TECHNICIAN or SUPERVISOR
    IN_PROGRESS → WAITING_ON_OPS    TECHNICIAN
    IN_PROGRESS → WAITING_ON_PARTS  TECHNICIAN
    WAITING_ON_OPS → IN_PROGRESS    TECHNICIAN or SUPERVISOR
    WAITING_ON_PARTS → IN_PROGRESS  TECHNICIAN or SUPERVISOR
    IN_PROGRESS → RESOLVED  TECHNICIAN (requires resolution_summary)
    RESOLVED → VERIFIED     OPERATOR, SUPERVISOR, ADMIN
    VERIFIED → CLOSED       SUPERVISOR, ADMIN
    CLOSED → RESOLVED       ADMIN only (reopen; requires mandatory note)
    Any active → ESCALATED  Celery SLA task or manual SUPERVISOR/ADMIN
    ESCALATED → prior status SUPERVISOR/ADMIN acknowledge escalation

  requested_by (FK → User),
  assigned_to (nullable FK → User),
  accepted_by (nullable FK → User),
  verified_by (nullable FK → User),
  closed_by (nullable FK → User),

  created_at, updated_at,
  assigned_at (nullable timestamptz),
  accepted_at (nullable timestamptz),
  in_progress_at (nullable timestamptz),
  resolved_at (nullable timestamptz),
  verified_at (nullable timestamptz),
  closed_at (nullable timestamptz),
  escalated_at (nullable timestamptz),

  -- SLA deadline fields (all computed at creation from org SLA config):
  ack_deadline (timestamptz),           -- must be accepted by this time
  first_update_deadline (timestamptz),  -- first timeline event by this time
  due_at (timestamptz),                 -- must be resolved by this time

  eta_minutes (int, nullable —
    REQUIRED when accepting IMMEDIATE or URGENT work orders.
    Technician's estimate of time to resolution from moment of accept.),

  resolution_summary (text, nullable — REQUIRED to transition to RESOLVED),
  resolution_details (text, nullable — optional extended notes),

  safety_flag (bool, default false),
  safety_notes (text, nullable — REQUIRED if safety_flag=true.
    Describes the specific hazard: H2S, confined space, LOTO, dropped
    object risk, hot work, etc. Visible at every UI level.),

  required_cert (nullable string — cert_name matched against
    TechnicianCertification. Assignment shows warning if tech lacks it.),

  -- Optional GPS snapshots (controlled by org config):
  gps_lat_accept (nullable decimal), gps_lng_accept (nullable decimal),
  gps_lat_start (nullable decimal),  gps_lng_start (nullable decimal),
  gps_lat_resolve (nullable decimal), gps_lng_resolve (nullable decimal),

  tags (text[]),
  custom_fields (JSONB),

  idempotency_key (UUID — client-generated, unique per org.
    Stored server-side in Redis for 24 h. Duplicate submissions from
    offline queue retry return cached response without creating
    duplicate work orders. MANDATORY on all WO mutation endpoints.),

  Priority visual mapping (apply consistently everywhere):
    IMMEDIATE = red banner + pulsing border animation
    URGENT    = orange banner
    SCHEDULED = yellow banner
    DEFERRED  = grey banner
    status=ESCALATED overlays red flash animation on any priority color
    safety_flag=true adds ⚠ warning icon at every UI level (card,
      dashboard badge, notification, email subject line)

SLAEvent:
  id, work_order_id, org_id,
  event_type ENUM(ACK_BREACH, FIRST_UPDATE_BREACH, RESOLVE_BREACH,
                  MANUAL_ESCALATION, ACKNOWLEDGED),
  triggered_at,
  acknowledged_by (nullable FK → User),
  acknowledged_at (nullable timestamptz)

### Work Order Detail

TimelineEvent:
  id, work_order_id, org_id,
  user_id (nullable — null for system-generated events),
  event_type ENUM(STATUS_CHANGE, MESSAGE, ATTACHMENT, PARTS_ADDED,
                  LABOR_LOGGED, NOTE, ASSIGNMENT_CHANGE, SLA_BREACH,
                  ESCALATION, GPS_SNAPSHOT, SAFETY_FLAG_SET),
  payload (JSONB — content varies by event_type),
  created_at
  -- Append-only. Never edited or deleted.
  -- Every status change auto-inserts a TimelineEvent (system entry).
  -- Users can append manual notes, messages, parts, labor, attachments.

Attachment:
  id, work_order_id, org_id, uploaded_by (FK → User),
  s3_key, s3_bucket, filename, mime_type, size_bytes,
  caption, created_at
  -- File bytes in S3/MinIO only. DB stores metadata + key.
  -- Access via pre-signed URLs (15 min TTL).
  -- Mobile queues offline captures; uploads on sync.

### Parts & Labor

Part:
  id, org_id, part_number (unique per org), description,
  unit_cost (decimal, nullable),
  barcode_value (nullable — scannable with QR scanner in field),
  supplier_name, supplier_part_number,
  stock_quantity (int, default 0),
  reorder_threshold (int, default 0),
  storage_location (string),
  qr_code_token (unique UUID),
  is_active, created_at

PartTransaction:
  id, part_id, org_id, work_order_id (nullable),
  transaction_type ENUM(IN, OUT, ADJUSTMENT),
  quantity (int — negative for OUT),
  notes, created_by (FK → User), created_at
  -- Always go through a transaction. Never mutate stock_quantity directly.

WorkOrderPartUsed:
  id, work_order_id, org_id,
  part_id (nullable FK → Part — null if manually entered),
  part_number, description, quantity,
  unit_cost (decimal, nullable — copied from Part at time of use;
    shown only with CAN_VIEW_COSTS permission)

LaborLog:
  id, work_order_id, org_id, user_id (FK → User),
  minutes (int), notes (text, nullable), logged_at (timestamptz)
  -- Technician logs time spent. Multiple entries per work order allowed.
  -- Cost = (minutes / 60) * org.config.default_labor_rate_per_hour
  -- Shown only with CAN_VIEW_COSTS permission.

### Preventive Maintenance

PMTemplate:
  id, org_id,
  asset_id (nullable FK → Asset),
  site_id (nullable FK → Site),
  title, description,
  type = PREVENTIVE (fixed, not user-editable),
  priority ENUM(IMMEDIATE, URGENT, SCHEDULED, DEFERRED),
  checklist_json (JSONB array of step strings),
  recurrence_type ENUM(DAILY, WEEKLY, MONTHLY, CUSTOM_DAYS, METER_BASED),
  recurrence_interval (int — e.g. 30 if CUSTOM_DAYS means every 30 days),
  required_cert (nullable string),
  assigned_to_role ENUM(TECHNICIAN, SUPERVISOR),
  is_active, created_at

PMSchedule:
  id, pm_template_id, org_id,
  due_date (date),
  generated_work_order_id (nullable FK → WorkOrder),
  status ENUM(PENDING, GENERATED, SKIPPED),
  skip_reason (nullable text)
  -- Celery beat generates WOs from PENDING schedules daily at 06:00
  -- org timezone. After generating, creates the next PMSchedule entry.

### Budget & Incentives

AreaBudget:
  id, org_id, area_id, year (int), month (int),
  budget_amount (decimal), actual_spend (decimal)
  -- actual_spend = sum(WorkOrderPartUsed.unit_cost * quantity)
  --              + sum(LaborLog.minutes / 60 * labor_rate)
  -- for all CLOSED WOs in that area+month.
  -- Recalculated by Celery on WorkOrder CLOSE.
  -- Requires CAN_MANAGE_BUDGET to view or edit.

IncentiveProgram:
  id, org_id, name,
  metric ENUM(RESPONSE_TIME, COST_PER_SITE, RESOLUTION_RATE,
              PM_COMPLETION_RATE, MTTR, SLA_COMPLIANCE_RATE),
  target_value (decimal), bonus_description (text),
  period_type ENUM(MONTHLY, QUARTERLY), is_active

UserIncentiveScore:
  id, user_id, program_id,
  period_label (string — e.g. "2025-Q1"),
  score (decimal), achieved (bool), calculated_at

### Audit Log

AuditLog:
  id, org_id, actor_user_id, action (string),
  entity_type (string), entity_id (string),
  old_value (JSONB), new_value (JSONB), created_at
  -- Log: all status changes, area assignment changes, permission
  --   changes, user creation/deactivation, SLA config changes,
  --   role changes, safety flag additions.
  -- Requires CAN_VIEW_AUDIT_LOG to view.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
ROLES AND PERMISSIONS
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

SUPER_ADMIN:  cross-org (internal ops only — not exposed in main UI)
ADMIN:        full org config, users, areas, SLA, budgets, audit
SUPERVISOR:   manage assigned Areas; assign/triage/close work orders;
              verify resolved work; acknowledge escalations; MFA required
OPERATOR:     create work orders in assigned Areas; view history;
              message/comment; verify resolved work
TECHNICIAN:   accept jobs (set ETA for IMMEDIATE/URGENT); status
              updates; photos; log parts and labor; resolve work orders
COST_ANALYST: view costs and budgets read-only (no operational writes)
READ_ONLY:    view all data in assigned Areas; no write access

Authorization checks (enforce in every handler, in this order):
  1. Is the requesting user active?
  2. Does the user's org_id match the target entity's org_id?
  3. If area-scoped: does the user have UserAreaAssignment for this area?
  4. Does the user's role permit this action on this FSM status?
  Fail any check → 403. Log sensitive failures to AuditLog.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
AUTHENTICATION & SECURITY
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

JWT Tokens:
- POST /auth/login → access_token (15 min TTL) + refresh_token (7 days)
- POST /auth/refresh → new access_token; rotate refresh_token
- POST /auth/logout → add refresh jti to Redis revocation SET
- Access token payload: { user_id, org_id, role, exp, jti }
- Enforce exp on every request — never accept expired tokens (RFC 7519)

MFA (TOTP via pyotp):
- POST /auth/mfa/setup   → returns TOTP secret + QR code data URL
- POST /auth/mfa/verify  → verifies TOTP code, enables MFA on account
- Login flow when MFA enabled:
    POST /auth/login returns { mfa_required: true, mfa_session_token }
    (mfa_session_token is a short-lived token, 2 min TTL, different secret)
    Client posts TOTP code + mfa_session_token to POST /auth/mfa/confirm
    → returns full access_token + refresh_token on success
- MFA required by default for ADMIN and SUPERVISOR
- POST /auth/mfa/disable → requires current valid TOTP code to disable

WebSocket Auth:
- WS connections cannot send Authorization headers.
- GET /auth/ws-token → requires valid access_token in Authorization header.
  Returns short-lived WS token (60 s TTL, signed with WS_SECRET_KEY,
  separate from main SECRET_KEY).
- Client connects: /ws?token={wsToken}
- Server validates WS token on connect, extracts user_id + org_id.
- Reject expired/invalid WS token with close code 4001.
- Client must request fresh WS token before each reconnect.

Rate Limiting (slowapi, Redis-backed):
- POST /auth/login:          10 req/min per IP
- POST /auth/refresh:        20 req/min per IP
- POST /auth/mfa/confirm:    10 req/min per IP
- All other endpoints:       120 req/min per user_id
- Exceeded → HTTP 429 with Retry-After header

Password Security:
- bcrypt, cost factor 12
- Minimum 8 characters (Pydantic validator)
- POST /auth/password-reset-request → email signed reset link
- POST /auth/password-reset → consume token, set new password

Idempotency:
- All work order mutation endpoints accept X-Idempotency-Key header
  (UUID, client-generated).
- Keys stored in Redis, TTL 24 h.
- Duplicate key within TTL → return cached response, no duplicate created.
- Client generates one UUID per mutation, persists it in the offline
  queue entry, resends same key on retry.

CORS:
- Allow only FRONTEND_URL env var — never wildcard in production.
- Allow credentials: true.

Input Validation:
- All request bodies: Pydantic v2 with explicit validators.
- Strip whitespace from all string fields.
- Strict enum validation — unknown values rejected with 422.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
REAL-TIME: WEBSOCKET + REDIS PUB/SUB
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Problem: Multiple Uvicorn workers each have their own in-process
WebSocket registry. A message published on Worker A won't reach clients
connected to Worker B without an external broker.

Solution — Redis Fan-Out:

1. ConnectionManager (backend/app/websockets/manager.py):
   In-process dict: { area_id: set[WebSocket] }
   Methods: connect(ws, user_id, area_ids), disconnect(ws),
            broadcast_to_area(area_id, payload)

2. Redis Subscriber Task (backend/app/websockets/subscriber.py):
   - Async task started in FastAPI app lifespan (startup)
   - Uses redis.asyncio (redis-py >= 5.0) — NOT deprecated aioredis
   - Pattern subscribe: "org:*:area:*"
   - On message: parse area_id from channel, call broadcast_to_area()
   - Graceful cancellation on app shutdown

3. Event Publishing (service layer, after any state change):
   await redis.publish(
     f"org:{org_id}:area:{area_id}", json.dumps(payload)
   )

4. WebSocket Endpoint (/ws?token={wsToken}):
   - Validate WS token → extract user_id, org_id
   - Look up user's area_ids (from UserAreaAssignment)
   - Register in ConnectionManager for all user areas
   - Heartbeat: server sends {"type":"ping"} every 30 s
   - No {"type":"pong"} within 10 s → close connection
   - Client reconnects with fresh WS token (exponential backoff:
     1 s, 2 s, 4 s, 8 s, max 30 s)
   - On WebSocketDisconnect: remove from manager cleanly;
     Redis subscriber task continues running unaffected

Event payload envelope (all events):
  {
    "event":     EVENT_TYPE,
    "org_id":    "...",
    "area_id":   "...",
    "timestamp": "ISO8601",
    "data":      { ... }
  }

Event types:
  NEW_WORK_ORDER         data: { work_order summary including
                                 human_readable_number, safety_flag }
  STATUS_CHANGED         data: { work_order_id, human_readable_number,
                                 old_status, new_status, changed_by }
  WORK_ORDER_ESCALATED   data: { work_order_id, human_readable_number,
                                 site_name, priority, safety_flag,
                                 escalated_at }
  WORK_ORDER_ACCEPTED    data: { work_order_id, human_readable_number,
                                 accepted_by, eta_minutes }
  SLA_BREACH             data: { work_order_id, human_readable_number,
                                 breach_type, breached_at }
  WAITING_STATE_CHANGE   data: { work_order_id, human_readable_number,
                                 new_status, reason }
  NEW_MESSAGE            data: { work_order_id, human_readable_number,
                                 sender_name, preview (first 80 chars) }
  PM_GENERATED           data: { work_order_id, human_readable_number,
                                 pm_template_name, site_name }
  INVENTORY_LOW_STOCK    data: { part_id, part_number, stock_quantity,
                                 reorder_threshold }

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
OFFLINE SUPPORT (NON-NEGOTIABLE)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Field technicians work on well sites where connectivity drops completely
for hours. Every core action must work offline and sync reliably.

Service Worker Caching Strategy (Workbox):
  App shell (HTML/CSS/JS):       CacheFirst (versioned; auto-update on deploy)
  GET /dashboard/*:              NetworkFirst → IndexedDB fallback
  GET /work-orders:              NetworkFirst → IndexedDB fallback
  GET /sites:                    NetworkFirst → IndexedDB fallback
  GET /assets:                   NetworkFirst → IndexedDB fallback
  GET /parts:                    NetworkFirst → IndexedDB fallback
  Static assets (fonts, icons):  CacheFirst

Offline Write Queue (IndexedDB via idb library):
  When navigator.onLine === false OR fetch throws NetworkError:
  - Queue in IndexedDB store "offline_queue"
  - Entry shape:
    {
      id: uuid,               ← this IS the idempotency key sent to server
      type: WO_CREATE | WO_UPDATE | STATUS_CHANGE | PARTS_ADD |
            LABOR_LOG | ATTACHMENT_UPLOAD | MESSAGE_SEND,
      payload: { ... },
      endpoint: string,
      method: string,
      created_at: ISO8601,
      retry_count: 0,
      status: PENDING | SYNCING | FAILED
    }
  - Show persistent "X actions pending sync" banner in header
  - At 24 h unsynced: toast warning "You have unsynced changes"
  - At 48 h unsynced: prominent modal warning, not just a toast
  - NEVER auto-delete unsynced entries

Sync on Reconnect:
  - Background Sync API (Chrome Android, desktop) where available
  - iOS fallback: window.addEventListener('online') + fetch probe /health
    → drain queue in foreground on reconnect, oldest-first
  - On conflict (WO status changed server-side while offline):
    Show ConflictResolutionModal: server state vs. queued change.
    User chooses. Never silently overwrite server state.
  - On success: remove entry, decrement banner count
  - On server error (non-conflict): retry up to 3x with exponential
    backoff (1 s, 4 s, 16 s); mark FAILED and alert user
  - ATTACHMENT_UPLOAD entries: upload to S3 pre-signed URL directly
    from client after getting fresh pre-signed URL from server

iOS Storage Rules:
  - navigator.storage.persist() on app install
  - Re-cache critical assets on every visibilitychange → visible event
    (iOS evicts PWA cache after ~7 days of non-use)
  - Handle QuotaExceededError: clear oldest CLOSED WO data from
    IndexedDB, retry write
  - Target cache size: under 50 MB

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
PUSH NOTIFICATIONS
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Use Firebase Cloud Messaging (FCM):
  - Handles APNs (iOS) and Android FCM under one backend API
  - Raw VAPID alone is unreliable for iOS — FCM is required
  - Backend: firebase-admin Python SDK
    (init from FIREBASE_SERVICE_ACCOUNT_JSON env var)
  - Frontend: Firebase JS SDK v10+ modular (getToken, onMessage)

Backend push flow (backend/app/notifications/push.py):
  async def send_push(user_ids, title, body, data):
    - Fetch fcm_token per user_id
    - Skip users with no fcm_token
    - send_each_async() via firebase_admin.messaging
    - INVALID_ARGUMENT or UNREGISTERED response → clear stale fcm_token
    - Any exception → log error + trigger email fallback for that user

Email fallback (backend/app/notifications/email.py):
  - Fires when FCM fails OR user has no fcm_token stored
  - ALWAYS fires for ESCALATED events regardless of push result
  - Email subject includes human_readable_number and SAFETY FLAG if set
  - HTML template: org logo, WO details, action button link
  - SendGrid API (SENDGRID_API_KEY env var)
  - Dev fallback: log full email body to stdout if key not set

Frontend push setup (src/hooks/usePushNotifications.ts):
  - Request permission ONLY from user gesture (button click)
    NEVER auto-request on page load — breaks iOS/Safari
  - On permission granted: Firebase getToken(messaging, { vapidKey })
    → POST /users/me/fcm-token
  - iOS constraint: push ONLY works if PWA installed to Home Screen
    Detect: window.navigator.standalone === false && /iPhone|iPad/.test(UA)
    → show install instructions modal before offering push setup
  - Store permission state in localStorage to avoid re-requesting

Push triggers:
  NEW IMMEDIATE work order      → push all area users with push_enabled
  NEW URGENT work order         → push all area users with push_enabled
  WORK_ORDER_ESCALATED          → push on-call PRIMARY (+ SECONDARY if
                                   PRIMARY unreachable); email ALWAYS
  SLA_BREACH (any type)         → push SUPERVISOR + on-call PRIMARY
  WAITING_ON_PARTS/OPS          → push SUPERVISOR for awareness
  NEW_MESSAGE                   → push recipient only
  WORK_ORDER_ACCEPTED           → push work order creator
  PM_DUE within 24 h            → push assigned tech
  INVENTORY_LOW_STOCK           → push users with CAN_MANAGE_INVENTORY
  Any WO with safety_flag=true  → include ⚠ SAFETY in push title

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
QR / BARCODE SYSTEM
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Every Location, Site, Asset, and Part gets a unique qr_code_token (UUID)
at creation. Tokens are embedded in printed QR codes attached to physical
equipment or posted at site entrances.

Backend:
  GET /locations/{id}/qr-code → PNG (Content-Type: image/png)
    QR encodes: {FRONTEND_URL}/scan/location/{qr_code_token}
  GET /sites/{id}/qr-code     → PNG
    QR encodes: {FRONTEND_URL}/scan/site/{qr_code_token}
  GET /assets/{id}/qr-code    → PNG
    QR encodes: {FRONTEND_URL}/scan/asset/{qr_code_token}
  GET /parts/{id}/qr-code     → PNG
    QR encodes: {FRONTEND_URL}/scan/part/{qr_code_token}

  GET /scan/location/{token}  → { location_id, name, area_id,
                                   open_wo_count }
  GET /scan/site/{token}      → { site_id, name, location_id,
                                   open_wo_count, safety_flag_count }
  GET /scan/asset/{token}     → { asset_id, name, site_id,
                                   open_wo_count }
  GET /scan/part/{token}      → { part_id, part_number, description,
                                   stock_quantity, unit_cost (if permitted) }

scripts/generate_qr_sheet.py:
  - Args: --area-id or --site-id
  - Output: printable PDF grid of QR codes with human-readable labels
    (site name, asset serial number, part number + description)
  - Include human_readable_number ranges for the area in the sheet footer

Frontend QR Scanner (src/pages/QRScannerPage.tsx):
  - Mobile nav "Scan" tab
  - html5-qrcode, rear camera preferred
  - Site/Asset scan → navigate to detail, pulse "New Work Order" button
  - Part scan → open "Add Part to Work Order" modal with part pre-filled
  - Camera denied → file upload fallback (decode QR from image)
  - Manual token entry fallback
  - Offline: use cached data for navigation; queue WO creation

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
OBSERVABILITY
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Request ID middleware:
  - Every request gets a unique request_id (UUID v4)
  - Returned in X-Request-ID response header
  - Included in every log line, Sentry event, and OTel span

OpenTelemetry:
  - opentelemetry-instrumentation-fastapi auto-instruments all routes
  - Custom spans in service layer for key operations (DB queries,
    external calls, Celery task enqueues)
  - OTLP exporter endpoint configurable via OTEL_EXPORTER_OTLP_ENDPOINT

Prometheus (/metrics endpoint):
  - Request count by route + status code
  - Request latency histograms
  - Active WebSocket connection count (gauge)
  - Celery task count by task name + status
  - SLA breach count by priority
  - Offline queue depth (read from Redis)

Sentry:
  - sentry_sdk.init() in app startup (SENTRY_DSN env var)
  - Set user context (user_id, org_id) from JWT on every request
  - Capture unhandled exceptions + transactions > 2 s

Structured logging:
  - All log lines output as JSON (structlog or python-json-logger)
  - Fields: request_id, user_id, org_id, endpoint, status_code,
    duration_ms, level, message

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
FULL API ROUTE LIST
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Auth:
  POST   /auth/login
  POST   /auth/refresh
  POST   /auth/logout
  GET    /auth/ws-token
  POST   /auth/mfa/setup
  POST   /auth/mfa/verify
  POST   /auth/mfa/confirm
  POST   /auth/mfa/disable
  POST   /auth/password-reset-request
  POST   /auth/password-reset
  GET    /health                         (public, no auth — offline probe)

Users:
  GET    /users/me
  PATCH  /users/me
  POST   /users/me/fcm-token
  DELETE /users/me/fcm-token
  GET    /users/me/notification-prefs
  PATCH  /users/me/notification-prefs
  GET    /users/me/certifications
  GET    /users/me/shifts
  GET    /users                          (ADMIN only)
  POST   /users                          (ADMIN only)
  GET    /users/{id}                     (ADMIN only)
  PATCH  /users/{id}                     (ADMIN only)
  DELETE /users/{id}                     (ADMIN only — soft delete)
  PUT    /users/{id}/areas               (ADMIN only — replace assignments)
  GET    /users/{id}/permissions
  PUT    /users/{id}/permissions         (ADMIN only)
  GET    /users/{id}/certifications
  POST   /users/{id}/certifications
  DELETE /users/{id}/certifications/{cert_id}

WebSocket:
  WS     /ws?token={wsToken}

Areas:
  GET    /areas
  POST   /areas                          (ADMIN only)
  GET    /areas/{id}
  PATCH  /areas/{id}                     (ADMIN only)
  DELETE /areas/{id}                     (ADMIN only)
  GET    /areas/{id}/on-call
  GET    /areas/{id}/shifts

Locations:
  GET    /locations                      (?area_id=)
  POST   /locations                      (ADMIN/SUPERVISOR)
  GET    /locations/{id}
  PATCH  /locations/{id}                 (ADMIN/SUPERVISOR)
  DELETE /locations/{id}                 (ADMIN only)
  GET    /locations/{id}/sites
  GET    /locations/{id}/qr-code

Sites:
  GET    /sites                          (?location_id= ?area_id=)
  POST   /sites                          (ADMIN/SUPERVISOR)
  GET    /sites/{id}
  PATCH  /sites/{id}                     (ADMIN/SUPERVISOR)
  DELETE /sites/{id}                     (ADMIN only)
  GET    /sites/{id}/assets
  GET    /sites/{id}/work-order-history
  GET    /sites/{id}/qr-code

Assets:
  GET    /assets                         (?site_id=)
  POST   /assets                         (ADMIN/SUPERVISOR)
  GET    /assets/{id}
  PATCH  /assets/{id}                    (ADMIN/SUPERVISOR)
  DELETE /assets/{id}                    (ADMIN only)
  GET    /assets/{id}/work-order-history
  GET    /assets/{id}/qr-code

Parts:
  GET    /parts                          (?search= ?low_stock_only=)
  POST   /parts                          (ADMIN/SUPERVISOR)
  GET    /parts/{id}
  PATCH  /parts/{id}
  DELETE /parts/{id}                     (ADMIN only)
  GET    /parts/{id}/transactions
  POST   /parts/{id}/transactions
  GET    /parts/{id}/qr-code

QR Scan:
  GET    /scan/location/{token}
  GET    /scan/site/{token}
  GET    /scan/asset/{token}
  GET    /scan/part/{token}

Work Orders:
  GET    /work-orders
         ?area_id= &site_id= &asset_id= &status= &priority= &type=
         &assigned_to= &requested_by= &safety_flag= &date_from=
         &date_to= &search= (title + human_readable_number full-text)
         Always scoped to user's assigned areas + org_id
  POST   /work-orders               (X-Idempotency-Key required)
  GET    /work-orders/{id}
  PATCH  /work-orders/{id}          (X-Idempotency-Key required)
  DELETE /work-orders/{id}          (ADMIN only, soft delete)
  POST   /work-orders/{id}/assign   (SUPERVISOR/ADMIN)
  POST   /work-orders/{id}/accept   (eta_minutes required for IMMEDIATE/URGENT)
  POST   /work-orders/{id}/start
  POST   /work-orders/{id}/wait-ops
  POST   /work-orders/{id}/wait-parts
  POST   /work-orders/{id}/resume
  POST   /work-orders/{id}/resolve  (resolution_summary required)
  POST   /work-orders/{id}/verify   (OPERATOR/SUPERVISOR/ADMIN)
  POST   /work-orders/{id}/close    (SUPERVISOR/ADMIN)
  POST   /work-orders/{id}/reopen   (ADMIN only; reason required)
  POST   /work-orders/{id}/escalate (manual; SUPERVISOR/ADMIN)
  POST   /work-orders/{id}/acknowledge-escalation
  GET    /work-orders/{id}/timeline
  POST   /work-orders/{id}/timeline  (add manual note)
  GET    /work-orders/{id}/attachments
  POST   /work-orders/{id}/attachments  (multipart/form-data → S3)
  DELETE /work-orders/{id}/attachments/{attachment_id}
  GET    /work-orders/{id}/parts
  POST   /work-orders/{id}/parts
  DELETE /work-orders/{id}/parts/{part_id}
  GET    /work-orders/{id}/labor
  POST   /work-orders/{id}/labor
  DELETE /work-orders/{id}/labor/{labor_id}
  GET    /work-orders/{id}/messages
  POST   /work-orders/{id}/messages
  GET    /work-orders/{id}/sla-events

Shift Schedules:
  GET    /shifts                     (?area_id=)
  POST   /shifts                     (ADMIN only)
  PATCH  /shifts/{id}
  DELETE /shifts/{id}
  PUT    /shifts/{id}/users

Preventive Maintenance:
  GET    /pm-templates               (?area_id= ?site_id= ?asset_id=)
  POST   /pm-templates               (CAN_MANAGE_PM_TEMPLATES)
  GET    /pm-templates/{id}
  PATCH  /pm-templates/{id}
  DELETE /pm-templates/{id}          (ADMIN only)
  GET    /pm-schedules               (?status= ?date_from= ?date_to=
                                      ?area_id=)
  POST   /pm-schedules/{id}/skip
  POST   /pm-schedules/{id}/generate-now

Inventory:
  GET    /inventory                  (?low_stock_only=true)
  POST   /inventory                  (CAN_MANAGE_INVENTORY)
  GET    /inventory/{id}
  PATCH  /inventory/{id}             (CAN_MANAGE_INVENTORY)
  DELETE /inventory/{id}             (ADMIN only)
  GET    /inventory/{id}/transactions
  POST   /inventory/{id}/transactions

On-Call Schedules:
  GET    /on-call-schedules          (?area_id= ?from= ?to=)
  POST   /on-call-schedules          (ADMIN/SUPERVISOR)
  PATCH  /on-call-schedules/{id}
  DELETE /on-call-schedules/{id}

Dashboard:
  GET    /dashboard/overview
  GET    /dashboard/area/{area_id}
  GET    /dashboard/site/{site_id}

Budget:
  GET    /budget                     (CAN_MANAGE_BUDGET; ?area_id=
                                      ?year= ?month=)
  PUT    /budget
  GET    /budget/summary

Incentives:
  GET    /incentives/programs        (CAN_VIEW_INCENTIVES)
  POST   /incentives/programs        (ADMIN only)
  PATCH  /incentives/programs/{id}
  GET    /incentives/scores          (?user_id= ?period=)

Reports (all support ?format=csv):
  GET    /reports/work-orders
  GET    /reports/response-times
  GET    /reports/sla-compliance
  GET    /reports/parts-spend
  GET    /reports/labor-cost
  GET    /reports/budget
  GET    /reports/pm-completion
  GET    /reports/technician-performance
  GET    /reports/safety-flags
  GET    /reports/incentives

Admin:
  GET    /admin/org
  PATCH  /admin/org
  GET    /admin/org/config
  PUT    /admin/org/config
  GET    /admin/audit-log            (CAN_VIEW_AUDIT_LOG)

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
CELERY BACKGROUND TASKS
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

check_sla_breaches (every 5 minutes via Celery beat):
  - ACK breach: WorkOrders where ack_deadline < now
    AND accepted_at IS NULL AND status IN (NEW, ASSIGNED)
    → create SLAEvent(ACK_BREACH), push SUPERVISOR + on-call PRIMARY
  - First update breach: WorkOrders where first_update_deadline < now
    AND no user TimelineEvent exists after created_at
    → create SLAEvent(FIRST_UPDATE_BREACH), push SUPERVISOR
  - Resolve breach: WorkOrders where due_at < now
    AND status NOT IN (RESOLVED, VERIFIED, CLOSED)
    AND escalated_at IS NULL
    → set status=ESCALATED, escalated_at=now
    → create SLAEvent(RESOLVE_BREACH)
    → push on-call PRIMARY then SECONDARY; email ALWAYS
    → publish WORK_ORDER_ESCALATED WebSocket event
    → if safety_flag=true: prepend ⚠ SAFETY to all notification titles

generate_pm_work_orders (daily at 06:00 org timezone):
  - Find PENDING PMSchedules where due_date <= today
  - Create WorkOrders from linked PMTemplates
    Auto-assign if assigned_to_role matches active tech in area;
    otherwise leave NEW for supervisor
  - Set PMSchedule.status=GENERATED + generated_work_order_id
  - Create next PMSchedule entry per recurrence rule
  - Push relevant area users

send_pm_reminders (daily at 08:00 org timezone):
  - PREVENTIVE WorkOrders where due_at BETWEEN now AND now+24h
    AND status IN (NEW, ASSIGNED, ACCEPTED)
  - Push + email assigned tech (or area supervisor if unassigned)

send_push_notification (generic async task):
  - firebase_admin.messaging.send_each_async()
  - Stale token → clear User.fcm_token
  - Exception → trigger send_email_notification fallback

send_email_notification (generic async task):
  - SendGrid API; HTML email template
  - human_readable_number in subject; safety flag in subject if set
  - Stdout fallback if SENDGRID_API_KEY not set

recalculate_area_budget (triggered on WorkOrder CLOSE):
  - Sum (WorkOrderPartUsed.unit_cost * quantity) for area+month
  - Sum (LaborLog.minutes / 60 * org.config.default_labor_rate_per_hour)
    for area+month
  - Upsert AreaBudget.actual_spend

precompute_dashboard_rollups (every 2 minutes):
  - Per area: count open WOs by priority; flag escalated; flag safety
  - Store in Redis: key "rollup:org:{id}:area:{id}", TTL 5 min
  - GET /dashboard/overview reads Redis cache first

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
FRONTEND — ALL PAGES AND COMPONENTS
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

UI RULES (apply to every component):
  - All touch targets ≥ 48px (field use with gloves on rugged devices)
  - Minimum font size 16px for body text
  - High contrast — workers read screens in direct sunlight
  - Human-readable WO number (WO-YYYY-NNNNNN) displayed prominently
    wherever a work order appears — NEVER show raw UUIDs to users
  - Safety flag (⚠) visible at every level: card, badge, header,
    notification, email, printed QR sheet

### Layout Shell

Desktop: Left sidebar, collapsible to icon-only mode
Mobile (≤768px): Bottom tab bar (5 tabs):
  Home | Work Orders | Scan | Notifications | Profile

Persistent header:
  - Org logo + name
  - Shift toggle: "On Shift ●" / "Off Shift ○" (green/grey pill)
    → PATCHes UserNotificationPref.on_shift for all user areas instantly
  - Notification bell + unread count badge
  - User avatar → dropdown (profile, MFA status, logout)

Notification drawer (right slide-in):
  - Last 50 events, reverse chronological
  - Each entry: event icon, human_readable_number, description,
    timestamp, safety flag icon if applicable, link to WO
  - Mark all read
  - Fed from WebSocket events + fetched on load

### Login Page

  - Email + password form
  - MFA TOTP code field (shown when server returns mfa_required=true)
  - "Remember this device" checkbox (extends refresh TTL)
  - Error states: wrong credentials, account deactivated, MFA failure,
    account locked after 10 failed attempts

### Dashboard Page (role-aware)

ADMIN / SUPERVISOR: all org areas as expandable accordions
OPERATOR / TECHNICIAN: only their assigned areas

Area accordion header shows:
  - Area name
  - Priority count chips:
      [N 🔴 IMMEDIATE] [N 🟠 URGENT] [N 🟡 SCHEDULED] [N ⬜ DEFERRED]
  - ESCALATED badge (red pulse) if any site in area is escalated
  - ⚠ SAFETY badge if any open WO in area has safety_flag=true

Site Card (inside expanded area):

  Empty state (no open WOs):
    - Clean white card, site name, type badge, last-activity timestamp

  Active state (open WOs exist):
    - Color banner strip across card top:
        IMMEDIATE = red banner + pulsing border
        URGENT    = orange banner
        SCHEDULED = yellow banner
        DEFERRED  = grey banner
    - ESCALATED: banner flashes via CSS keyframe animation (not JS)
    - ⚠ SAFETY icon visible on card if any open WO has safety_flag=true
    - WO count pills by priority
    - WAITING pills: [N waiting on ops] [N waiting on parts] in amber
    - Assigned tech avatars (for accepted/in-progress WOs)
    - ETA countdown for accepted IMMEDIATE/URGENT WOs
    - Click → Site Detail page

Real-time: WebSocket events update cards live without reload.
Escalated cards sort to top of their area section.
Safety-flagged cards get a persistent ⚠ border.

### Site Detail Page (URL: /sites/{id})

Header: site name, type badge, area/location breadcrumb, address,
        GPS directions link, safety flag summary count (red if > 0),
        QR code download button, "New Work Order" button

Tabs: Open WOs | History | Assets | Parts Used | Labor | Budget (gated)

Open WOs tab:
  WorkOrderCards sorted: ESCALATED first, then by priority desc,
  then created_at asc

History tab:
  Paginated (20/page). Search by title or human_readable_number.
  Filter by type, priority, date range, safety_flag.

Assets tab:
  Asset cards: name, serial number, warranty status badge
  (green=valid, yellow=< 90 days, red=expired), open WO count,
  last maintenance date. Click → Asset Detail.

Parts Used tab:
  All WorkOrderPartUsed for this site, grouped by part_number, summed.
  Unit cost + total shown only with CAN_VIEW_COSTS.

Labor tab:
  Total labor hours by technician + by period.
  Cost column shown only with CAN_VIEW_COSTS.

Budget tab (CAN_MANAGE_BUDGET):
  Current month spend vs budget for the site's area.
  6-month trend bar chart (parts cost + labor cost stacked).

### Asset Detail Page (URL: /assets/{id})

Header: asset name, manufacturer/model, serial number, install date,
        warranty expiry (colored badge), QR download, site breadcrumb

Sections:
  - Open WOs for this asset (WorkOrderCard list)
  - Full WO history (search by human_readable_number, filter by date)
  - Parts history (all parts ever used on this asset; costs if permitted)
  - Labor history (all labor logs for this asset; costs if permitted)
  - PM Templates attached to this asset (with next due date)

### Work Order Card Component

Use everywhere work orders appear.

Display:
  - human_readable_number (WO-YYYY-NNNNNN) — large, prominent, copyable
  - Priority badge (color + text: IMMEDIATE / URGENT / SCHEDULED / DEFERRED)
  - Status badge:
      NEW=grey | ASSIGNED=blue | ACCEPTED=indigo | IN_PROGRESS=purple |
      WAITING_ON_OPS=amber | WAITING_ON_PARTS=amber |
      RESOLVED=green | VERIFIED=teal | CLOSED=dark | ESCALATED=red-pulse
  - Type badge (REACTIVE / PREVENTIVE / INSPECTION / CORRECTIVE)
  - ⚠ Safety flag icon (prominent red) if safety_flag=true
  - Title (2-line truncate)
  - Site name + Asset name (if asset-level)
  - requested_by avatar + name + timestamp
  - assigned_to avatar + name OR "Unassigned" + [Assign] button
    (SUPERVISOR/ADMIN)
  - If ACCEPTED or IN_PROGRESS: ETA countdown timer
      > 1 hr  → green
      15–60 min → yellow
      < 15 min  → red
      overdue   → red pulse
  - If WAITING_ON_OPS or WAITING_ON_PARTS: amber waiting banner with label
  - Cert warning icon if assigned tech lacks required_cert
  - Click → WorkOrderDetailPanel

### Work Order Detail Panel

Slide-in drawer (mobile) / side panel (desktop).

Tabs: Info | Timeline | Attachments | Parts & Labor | Messages | SLA

Info tab:
  - human_readable_number (large, copyable)
  - All card fields + full description
  - Safety flag section (prominent red box if set, shows safety_notes)
  - SLA deadlines: ack by | first update by | resolve by
    (each with color-coded countdown: green/yellow/red)
  - ESCALATED badge + timestamp if applicable
  - GPS snapshot map links (if captured at accept/start/resolve)
  - Tags, custom fields

Timeline tab:
  - Chronological append-only log of all events
  - System events (status changes, SLA events) → grey italic
  - User entries (notes, messages, parts, labor) → normal style
  - WAITING state entries show reason
  - "Add Note" textarea at bottom

Attachments tab:
  - Photo/file grid; tap for fullscreen lightbox
  - "Add Attachment": camera capture (mobile) or file select
  - Uploader name + timestamp per item

Parts & Labor tab:
  - Parts table: Part # | Description | Qty | Unit Cost* | Total*
  - Labor table: Technician | Minutes | Hours | Notes | Logged At
                 Cost column* (* shown only with CAN_VIEW_COSTS)
  - "Add Part": inventory autocomplete (search or scan QR/barcode)
    Pre-fills unit_cost from Part record if linked
  - "Add Labor": minutes input + notes

Messages tab:
  - Inline chat thread (OPERATOR ↔ TECHNICIAN, scoped to this WO)
  - Real-time via WebSocket (NEW_MESSAGE event)
  - Sender name, message body, timestamp, read receipts (✓✓)

SLA tab:
  - Visual timeline: ack_deadline → first_update_deadline → due_at
  - Countdown timers (green/yellow/red)
  - SLAEvent history: breach timestamps, acknowledgement records

Action buttons (role + FSM status aware — never show impossible actions):

  NEW:
    - TECHNICIAN: [Self-Assign + Accept] → ETA modal
      (ETA required for IMMEDIATE/URGENT)
    - SUPERVISOR/ADMIN: [Assign Tech] → user picker
      (shows cert warning if tech lacks required_cert)
    - Any active user: [Add Safety Flag] (if not already set)
    - OPERATOR+: [Edit Details]

  ASSIGNED:
    - Assigned TECHNICIAN: [Accept + Set ETA]
    - SUPERVISOR: [Reassign] [Accept on Tech's Behalf]

  ACCEPTED / IN_PROGRESS:
    - Assigned TECHNICIAN:
      [Mark In Progress] [Waiting on Ops] [Waiting on Parts]
      [Add Note] [Add Photo] [Log Parts] [Log Labor] [Resolve]
    - SUPERVISOR: all above + [Reassign]

  WAITING_ON_OPS / WAITING_ON_PARTS:
    - TECHNICIAN: [Resume Work] (→ IN_PROGRESS)
    - SUPERVISOR: [Resume] [Reassign]

  RESOLVED:
    - OPERATOR/SUPERVISOR/ADMIN: [Verify — Fix Confirmed]
                                 [Request Rework] (adds mandatory note)

  VERIFIED:
    - SUPERVISOR/ADMIN: [Close Work Order]

  ESCALATED:
    - SUPERVISOR/ADMIN: [Acknowledge Escalation]
      (clears flash animation, logs SLAEvent ACKNOWLEDGED)

  CLOSED:
    - ADMIN only: [Reopen] (mandatory reason; reopens to RESOLVED)

  All statuses:
    - ADMIN: [Delete Work Order] (confirmation dialog)

### New Work Order Form (URL: /work-orders/new)

  - Area picker (pre-selected from context; filtered to user's areas)
  - Location picker (filtered to area; searchable)
  - Site picker (filtered to location; searchable)
  - Asset picker (optional; filtered to site)
  - Type radio: REACTIVE | PREVENTIVE | INSPECTION | CORRECTIVE
  - Priority with color + plain-English descriptions:
      🔴 IMMEDIATE — "Stop everything. Safety or production at risk.
                      H2S, blowout risk, total production loss."
      🟠 URGENT    — "Needs attention before end of current shift."
      🟡 SCHEDULED — "Can be planned into the next work cycle."
      ⬜ DEFERRED  — "Low priority. Do when resources allow."
  - Safety Flag checkbox
    → if checked: safety_notes textarea appears (required)
      "Describe the specific hazard (H2S, confined space, LOTO, etc.)"
  - Title (required)
  - Description (required, minimum 20 characters)
  - Required Certification (optional dropdown from org cert types)
  - Tags (multi-select)
  - Attach Photos (optional)
  - Submit (generates idempotency key before POST)

  On submit:
    - POST /work-orders with X-Idempotency-Key header
    - IMMEDIATE/URGENT: push to area users immediately
    - Navigate to new WO detail
    - If offline: queue in IndexedDB, show "Saved offline — will sync"

### QR Scanner Page (URL: /scan)

  - html5-qrcode, rear camera preferred
  - Corner guide overlay
  - Site/Asset scan → navigate to detail, pulse "New WO" button 3 s
  - Part scan → open "Add Part to WO" modal, pre-filled
  - Camera denied: file upload fallback + manual token entry
  - Offline: cached data for navigation; queue WO creation

### Preventive Maintenance Page (URL: /pm)

Tabs: Templates | Schedule | Overdue

Templates tab:
  Columns: Name | Asset/Site | Recurrence | Next Due | Cert | Active
  [New Template] button (CAN_MANAGE_PM_TEMPLATES)

PM Template Form:
  - Title, description
  - Target: Asset OR Site (one required)
  - Priority (all 4 levels available)
  - Recurrence: type + interval
  - Checklist builder: add/remove/reorder steps (drag-and-drop)
  - Required certification
  - Assigned to role (TECHNICIAN or SUPERVISOR)
  - Active toggle

Schedule tab:
  Month calendar. Color coding:
    Green: not yet due | Yellow: due within 7 days |
    Red: overdue | Grey: completed/skipped
  Click date → list with [Generate Now] [Skip + reason] per PM

Overdue tab:
  All PENDING where due_date < today. Most overdue first.
  [Generate All Overdue] batch button.

### Inventory / Parts Page (URL: /inventory)

Requires CAN_MANAGE_INVENTORY.

  Table: Part # | Description | Stock | Threshold | Storage |
         Supplier | Last Ordered | Actions
  Stock color: Green > threshold | Yellow ≤ threshold | Red = 0
  Low Stock summary card at top
  Search + filter (low stock only, supplier)
  [+IN] [-OUT] [Adjust] [View History] [Edit] per row
  Stock transaction modal: type, qty, optional WO link, notes
  Transaction history drawer
  Export CSV button

### Admin Panel (URL: /admin)

Tabs: Users | Certs | Hierarchy | Shifts | SLA Config |
      On-Call | PM Programs | Incentives | Audit Log | Org Settings

Users tab:
  Table: Name | Email | Role | MFA ✓/✗ | Areas | Active | Last Login
  [Create User], [Edit], [Deactivate], [Send Password Reset]
  Area assignment: tag-select — this is the "swap a tech between areas"
  feature. Update tags and save. UserAreaAssignment rows replaced.
  Permission checkboxes per user.

Certifications tab:
  Org-wide cert type CRUD (names used for autocomplete everywhere).

Hierarchy tab:
  Tree: Area → Location → Site → Asset
  CRUD all 4 levels. QR download button on Site and Asset rows.

Shifts tab:
  Shift schedule CRUD per area.
  User-to-shift assignment (drag users onto shifts).

SLA Configuration tab:
  Current values from org.config JSONB.
  Per-priority: ack_minutes | first_update_minutes | resolve_hours.
  escalation_enabled toggle.
  Save → background task recalculates pending SLA deadlines.

On-Call Schedule tab:
  Weekly calendar per area.
  PRIMARY + SECONDARY assignment per area per week.
  Click cell → user picker (role filter: SUPERVISOR, TECHNICIAN).

Incentive Programs tab:
  CRUD for IncentiveProgram. Metric, target, bonus, period.
  Scores view: filter by user/period, achieved badge.

Audit Log tab (CAN_VIEW_AUDIT_LOG):
  Table: Timestamp | User | Action | Entity | Old | New
  Filters: date range, user, entity type.
  Export CSV.

Org Settings tab:
  Logo upload, name, slug (readonly after creation), currency code,
  GPS snapshot toggles, closed WO cache days, MFA required roles,
  default labor rate per hour.

### Reports Page (URL: /reports — SUPERVISOR/ADMIN)

Controls: Date range picker, Area multi-select, Export CSV button

Summary cards:
  - Avg response time (accepted_at − created_at)
  - Avg resolution time (resolved_at − created_at)
  - SLA compliance % (resolved before due_at)
  - Escalation rate %
  - PM completion rate %
  - Safety flag count (+ link to safety report)
  - Total parts cost* | Total labor cost* (* CAN_VIEW_COSTS only)

Charts (Recharts):
  - WO volume by week (stacked bar by priority)
  - WO volume by type (donut)
  - Response time trend (line by week)
  - SLA compliance trend (line by week)
  - Parts spend by area (horizontal bar)*
  - PM completion % by area (grouped bar)
  - Safety flags by site (bar)

Tables (paginated, sortable, CSV export on each):
  All /reports/* endpoints listed above.

Safety Flags Report (/reports/safety-flags):
  All WOs with safety_flag=true in period.
  Columns: WO# | Site | Priority | Hazard Description | Days Open |
           Resolution | Verified By.

### Profile / Settings Page (URL: /profile)

Sections:
  Personal Info: name, phone, avatar, change password form

  MFA Setup:
    Status: "Enabled ✓" / "Not configured"
    [Set Up MFA] → show TOTP QR code + manual key + verify code field
    [Disable MFA] → requires current valid TOTP code

  Notification Preferences:
    Per-area push/email toggle table.
    Global on-shift toggle (mirrors header toggle).
    [Send Test Notification] button.

  My Certifications:
    List with expiry dates.
    Red if expired, yellow if < 30 days, green otherwise.

  Push Notification Setup:
    Status indicator.
    [Enable Push Notifications] (gesture only — never auto-request).
    iOS section (shown if iOS + not standalone):
      "Push notifications require the app to be installed.
       1. Tap Share in Safari
       2. Tap Add to Home Screen
       3. Open the app from your home screen
       4. Return here to enable notifications"

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
PWA CONFIGURATION
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

vite-plugin-pwa (vite.config.ts):
  registerType: 'autoUpdate'
  manifest:
    name: "OilfieldMaint"
    short_name: "OFMaint"
    description: "Oilfield maintenance work order tracking"
    display: "standalone"
    start_url: "/"
    theme_color: "#1e3a5f"
    background_color: "#ffffff"
    icons: 192x192 PNG, 512x512 PNG,
           180x180 PNG (Apple touch icon in <head>)
  workbox:
    globPatterns: ['**/*.{js,css,html,ico,png,svg,woff2}']
    runtimeCaching: per strategies listed in Offline section

Service worker (src/service-worker.ts):
  - Workbox cache strategies (as above)
  - Firebase onBackgroundMessage → showNotification with [View] action
  - Background Sync handler for offline queue (Chrome/desktop)
  - notificationclick: focus existing window or open at WO URL

iOS Install Prompt (src/hooks/useIOSInstallPrompt.ts):
  const isIOS = /iPhone|iPad|iPod/.test(navigator.userAgent)
  const isStandalone = window.navigator.standalone === true
  If iOS and not standalone → show dismissable bottom sheet instructions
  Store dismissal in localStorage; re-show after 7 days

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
PROJECT FILE STRUCTURE
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

backend/
  app/
    api/
      auth.py, users.py, areas.py, locations.py, sites.py,
      assets.py, parts.py, work_orders.py, wo_timeline.py,
      wo_attachments.py, wo_parts.py, wo_labor.py, wo_messages.py,
      wo_sla.py, pm_templates.py, pm_schedules.py, inventory.py,
      shifts.py, on_call.py, dashboard.py, budget.py,
      incentives.py, reports.py, admin.py, scan.py, websocket.py
    models/
      org.py, user.py, area.py, location.py, site.py, asset.py,
      part.py, work_order.py, sla.py, pm.py, budget.py,
      incentive.py, audit_log.py, shift.py
    schemas/           (Pydantic v2 — request + response per domain)
    services/
      work_order_service.py, sla_service.py, pm_service.py,
      part_service.py, notification_service.py, report_service.py,
      budget_service.py, audit_service.py, qr_service.py
    workers/
      celery_app.py, sla_tasks.py, pm_tasks.py,
      email_tasks.py, budget_tasks.py, rollup_tasks.py
    core/
      config.py, security.py, mfa.py, database.py, deps.py,
      rate_limit.py, firebase.py, redis.py, s3.py,
      observability.py, idempotency.py
    websockets/
      manager.py, subscriber.py
    notifications/
      push.py, email.py
    reports/
      csv_export.py
  alembic/
    versions/, env.py
  tests/
    conftest.py
    test_auth.py
    test_mfa.py
    test_work_orders.py
    test_fsm.py              (every valid + invalid FSM transition)
    test_sla.py              (breach detection, escalation routing)
    test_permissions.py
    test_role_access.py
    test_org_isolation.py    ← MANDATORY: Org A cannot see Org B
    test_idempotency.py      (duplicate submission returns same result)
    test_pm.py
    test_inventory.py
    test_websocket.py
    test_offline_queue.py
    test_qr.py
    test_safety_flags.py

frontend/
  src/
    api/
      client.ts              (axios + auto token refresh interceptor)
      auth.ts, workOrders.ts, sites.ts, assets.ts, parts.ts,
      pm.ts, inventory.ts, dashboard.ts, reports.ts,
      admin.ts, notifications.ts, shifts.ts
    components/
      ui/                    (shadcn — do not modify)
      WorkOrderCard.tsx
      WorkOrderDetailPanel.tsx
      SiteCard.tsx
      AreaAccordion.tsx
      PriorityBadge.tsx
      StatusBadge.tsx
      TypeBadge.tsx
      SafetyFlagBadge.tsx
      WaitingStateBadge.tsx
      HumanReadableNumber.tsx
      ETACountdown.tsx
      SLACountdown.tsx
      QRScanner.tsx
      PhotoGallery.tsx
      PartsTable.tsx
      LaborTable.tsx
      MessageThread.tsx
      TimelineView.tsx
      NotificationDrawer.tsx
      OfflineQueueBanner.tsx
      ShiftToggle.tsx
      PMCalendar.tsx
      InventoryStockBadge.tsx
      CertWarningBanner.tsx
      IOSInstallPrompt.tsx
      ConflictResolutionModal.tsx
      GPSSnapshotMap.tsx
      MFASetupModal.tsx
    pages/
      LoginPage.tsx
      DashboardPage.tsx
      SiteDetailPage.tsx
      AssetDetailPage.tsx
      WorkOrderListPage.tsx
      NewWorkOrderPage.tsx
      QRScannerPage.tsx
      PMPage.tsx
      InventoryPage.tsx
      ReportsPage.tsx
      AdminPage.tsx
      ProfilePage.tsx
    hooks/
      useRealtimeChannel.ts    (WS connect, heartbeat, reconnect,
                                exponential backoff, WS token refresh)
      useOfflineQueue.ts       (IndexedDB queue, sync, conflict modal,
                                24h/48h unsynced warnings)
      usePushNotifications.ts  (FCM token, permission flow)
      useIOSInstallPrompt.ts
      useQRScanner.ts
      useShiftToggle.ts
      useIdempotencyKey.ts     (generate UUID, persist per mutation)
    stores/
      authStore.ts
      notificationStore.ts
      offlineQueueStore.ts
      uiStore.ts
    workers/
      service-worker.ts        (Workbox + Firebase background handler)
      offline-sync.ts          (queue drain on reconnect)
    types/
      api.ts                   (TypeScript interfaces mirroring all
                                Pydantic schemas exactly)
      enums.ts                 (Role, Status, Priority, Type, etc.)
    utils/
      priority.ts              (priority → color/label/CSS class)
      status.ts                (status → badge variant)
      dateFormat.ts
      qrHelpers.ts
      offlineDetect.ts
      numberFormat.ts          (currency formatting per org config)

infra/
  docker-compose.yml
  docker-compose.prod.yml
  minio-init.sh               (create bucket on first run)

scripts/
  seed.py
  generate_qr_sheet.py

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
DOCKER COMPOSE
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Services:
  postgres:       postgres:16-alpine, named volume, health check
  redis:          redis:7-alpine, named volume
  minio:          minio/minio, credentials from env
  minio-init:     mc client — creates S3 bucket, exits when done
  backend:        builds from backend/Dockerfile
                  depends_on: postgres (healthy), redis, minio-init
                  env_file: .env
  celery-worker:  same image as backend
                  command: celery -A app.workers.celery_app worker
                           --loglevel=info --concurrency=4
  celery-beat:    same image as backend
                  command: celery -A app.workers.celery_app beat
                           --loglevel=info
                           --scheduler=redbeat.RedBeatScheduler
  frontend:       builds from frontend/Dockerfile.dev (Vite dev server)
                  depends_on: backend

.env.example:
  # Database
  DATABASE_URL=postgresql+asyncpg://postgres:password@postgres:5432/ofmaint
  # Redis
  REDIS_URL=redis://redis:6379/0
  # JWT
  SECRET_KEY=change-me-in-production-min-32-chars
  WS_SECRET_KEY=change-me-too-different-from-secret-key
  MFA_SECRET_KEY=change-me-too-different-again
  ACCESS_TOKEN_EXPIRE_MINUTES=15
  REFRESH_TOKEN_EXPIRE_DAYS=7
  # S3 / MinIO
  AWS_ACCESS_KEY_ID=minioadmin
  AWS_SECRET_ACCESS_KEY=minioadmin
  AWS_ENDPOINT_URL=http://minio:9000
  S3_BUCKET=ofmaint-uploads
  # Firebase
  FIREBASE_SERVICE_ACCOUNT_JSON={"type":"service_account",...}
  FIREBASE_VAPID_KEY=your-vapid-key-here
  # Email
  SENDGRID_API_KEY=
  EMAIL_FROM=noreply@yourorg.com
  # Frontend
  FRONTEND_URL=http://localhost:5173
  # Observability
  SENTRY_DSN=
  OTEL_EXPORTER_OTLP_ENDPOINT=
  # App
  ENVIRONMENT=development
  LOG_LEVEL=INFO

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
DELIVERABLES — BUILD IN THIS EXACT ORDER
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

1.  ASSUMPTIONS.md (write first, before any code)
2.  infra/docker-compose.yml + all Dockerfiles + .env.example
3.  Backend: all SQLAlchemy models + complete initial Alembic migration
4.  Backend: core/ (config, security, mfa, database, deps, rate_limit,
    firebase, redis, s3, observability, idempotency)
5.  Backend: auth routes (login, MFA flow, refresh, logout, password
    reset, ws-token)
6.  Backend: all API routes + full service layer
    (org_id + object-level auth on every single handler)
7.  Backend: WebSocket endpoint + ConnectionManager + Redis subscriber
8.  Backend: Celery app + all tasks (SLA, PM, email, budget, rollups)
9.  Backend: FCM push + SendGrid email with fallback logic
10. Backend: QR code generation for all entity types (PNG responses)
11. Backend: CSV export on all report endpoints
12. Backend: pytest test suite
    test_org_isolation.py — MANDATORY — Org A cannot read, write,
    or affect Org B under any endpoint or circumstance
    test_fsm.py — every valid transition passes; every invalid → 422
    test_sla.py — breach detection and escalation routing correct
    test_idempotency.py — duplicate offline submissions safe
    test_safety_flags.py — flags propagate correctly to all surfaces
13. Frontend: Vite + TS scaffold, React Router, Zustand stores,
    axios client with auto token refresh interceptor
14. Frontend: useRealtimeChannel (connect, heartbeat, reconnect,
    exponential backoff, WS token refresh on each reconnect)
15. Frontend: Login page + MFA TOTP flow + protected route wrapper
16. Frontend: Dashboard (area accordion, site cards, real-time updates,
    escalation flash, safety badges, WAITING state badges)
17. Frontend: WorkOrderCard + WorkOrderDetailPanel (all 6 tabs +
    all action buttons per FSM state; human_readable_number prominent)
18. Frontend: New Work Order form (all fields including safety flag
    section + hazard notes)
19. Frontend: QR Scanner page
20. Frontend: useOfflineQueue + IndexedDB write queue +
    OfflineQueueBanner + ConflictResolutionModal +
    foreground sync + 24h/48h unsynced warnings
21. Frontend: Site Detail + Asset Detail pages (all tabs)
22. Frontend: PM page (template list, checklist builder, calendar,
    overdue list with batch generate)
23. Frontend: Inventory/Parts page (stock levels, transactions,
    low-stock alerts, CSV export)
24. Frontend: Reports page (all summary cards + Recharts charts +
    safety flags report + labor cost report + CSV export)
25. Frontend: Admin panel (all tabs: users with MFA status, certs,
    hierarchy tree, shifts, SLA config, on-call calendar, incentive
    programs, audit log, org settings)
26. Frontend: Profile page (personal info, MFA setup/disable,
    notification prefs, certs, push setup with iOS instructions)
27. Frontend: PWA config (vite-plugin-pwa, Workbox, manifest, service
    worker with Firebase background messaging handler)
28. Frontend: IOSInstallPrompt component
29. scripts/seed.py:
      2 orgs (Org A + Org B — for isolation testing)
      3 areas per org
      3 locations per area
      4 sites per location (mix of types including WELL_SITE,
        COMPRESSOR_STATION, TANK_BATTERY)
      3-4 assets per site
      20 users per org spanning all roles (include at least 2 each of
        TECHNICIAN, OPERATOR, SUPERVISOR; 1 each COST_ANALYST, READ_ONLY)
      Users with MFA enabled: all ADMIN and SUPERVISOR accounts
      40 work orders per org:
        - At least 2 in each FSM state
        - At least 5 with safety_flag=true (with realistic safety_notes)
        - At least 3 ESCALATED
        - At least 4 WAITING_ON_PARTS or WAITING_ON_OPS
        - At least 3 IMMEDIATE priority
        - Spread across all 4 priority levels
        - Mix of all 4 types (REACTIVE, PREVENTIVE, INSPECTION,
          CORRECTIVE)
        - human_readable_number generated correctly for all
      5 PM templates per org with generated schedules
        (including some overdue)
      25 parts per org with realistic stock levels
        (8 below reorder threshold, 3 at zero)
      On-call schedule for next 4 weeks per area
        (PRIMARY + SECONDARY assigned)
      Parts used + labor logs on all RESOLVED/CLOSED WOs
      Realistic timestamps spread over last 90 days
      Shift schedules for each area with users assigned
30. scripts/generate_qr_sheet.py:
      Args: --area-id or --site-id
      Output: printable PDF grid of QR codes with human-readable
        labels (site name, asset serial, part number + description)
      Include human_readable_number legend in sheet footer
31. README.md:
      ASCII architecture diagram
      Local setup: exact commands from clone to running app
      Every env var: name | description | default | required?
      Firebase project setup (create project, get service account JSON,
        get VAPID key)
      iOS "Add to Home Screen" instructions (end-user copy-paste ready)
      MFA enrollment guide for administrators
      QR code generation and printing guide
      How to run the test suite
      How to run the seed script
      How the offline sync works (plain English for field IT staff)

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
DEFINITION OF DONE
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

After docker compose up + python scripts/seed.py:

  ✓ Admin can create areas, locations, sites, assets; assign users
  ✓ Operator creates WO with safety flag — ⚠ visible on card immediately
  ✓ Technician self-assigns IMMEDIATE WO, sets ETA, moves through
    ACCEPTED → IN_PROGRESS → WAITING_ON_PARTS → IN_PROGRESS → RESOLVED
  ✓ Operator verifies; supervisor closes
  ✓ Site cards reflect correct priority color and WAITING state badges
  ✓ SLA breach Celery task escalates overdue WO + sends email
  ✓ PM Celery task generates WOs from templates on schedule
  ✓ human_readable_number (WO-YYYY-NNNNNN) visible on every card,
    notification, and email — no raw UUIDs shown to users
  ✓ Offline: create, accept, update, resolve WOs with zero network;
    sync on reconnect; idempotency prevents duplicates
  ✓ Conflict modal appears when server state diverged while offline
  ✓ 24h and 48h unsynced warnings fire correctly
  ✓ Cross-org access denied on every endpoint (test_org_isolation passes)
  ✓ Cross-area access denied for users not assigned to that area
  ✓ MFA enrollment + login flow works for ADMIN and SUPERVISOR
  ✓ WS token auth + reconnect after expiry works correctly
  ✓ QR codes generate for all entity types; scanner navigates correctly
  ✓ Safety flags propagate to cards, dashboard badges, push titles,
    email subjects, and the safety flags report
  ✓ test_org_isolation.py passes
  ✓ test_fsm.py passes (all transitions)
  ✓ test_sla.py passes
  ✓ test_idempotency.py passes
  ✓ /metrics endpoint returns Prometheus data
  ✓ iOS "Add to Home Screen" prompt appears for non-standalone iOS users
  ✓ All touch targets ≥ 48px

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
FINAL RULES — READ BEFORE WRITING CODE
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

- Build the COMPLETE system. No scaffolding, no stubs, no TODO comments.
- Every feature in this spec must be implemented with working code.
- Every DB query must include org_id. Every handler that accepts an
  entity ID must verify object ownership. Zero exceptions.
- The 9-state FSM must be enforced server-side. Invalid transitions
  return HTTP 422 with a clear error message.
- Idempotency keys must be checked on all work order mutation endpoints.
  Duplicate submissions return the original response — no duplicate WOs.
- Human-readable WO numbers (WO-YYYY-NNNNNN) must appear on every
  card, notification, push message, email, and printed QR sheet.
  Field workers use these numbers on radio calls. Never show UUIDs.
- Safety flags must be visible at the site card level, dashboard area
  badge, push notification title, email subject, and reports.
  A safety-flagged ESCALATED work order is the highest-severity item
  in the system and must be visually unmistakable.
- Labor logging is required for complete cost tracking. Budget actual
  spend = parts cost + labor cost. Do not omit labor from calculations.
- MFA must be enforced at login for ADMIN and SUPERVISOR roles.
  A user in these roles with mfa_enabled=true who skips the TOTP step
  must not receive tokens.
- Offline queue must handle iOS Background Sync limitations via
  foreground drain on reconnect. Never auto-delete unsynced entries.
- Firebase FCM (not raw VAPID alone) for push notifications.
- WebSocket fan-out must work across multiple Uvicorn workers via
  Redis pub/sub. A message published on Worker A must reach all
  clients connected to Worker B.
- ASSUMPTIONS.md must be written first and must document every
  default decision made during implementation.
- test_org_isolation.py must pass before the backend is done.