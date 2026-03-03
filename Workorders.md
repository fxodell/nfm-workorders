# OilfieldMaint — Work Order Management System

A full-stack Computerized Maintenance Management System (CMMS) built for oilfield operations. It manages the complete lifecycle of maintenance work orders, preventive maintenance schedules, parts inventory, budgets, and field technician coordination — with real-time updates, mobile/offline support, and QR code scanning.

**Live URL:** https://workorders.nfmconsulting.com

---

## Tech Stack

| Layer | Technology |
|-------|-----------|
| Frontend | React 18 + TypeScript, Vite, React Router, Zustand |
| Backend | FastAPI (Python), async/await, Pydantic |
| Database | PostgreSQL 16 |
| Cache / Pub-Sub | Redis 7 |
| File Storage | MinIO (S3-compatible) |
| Background Jobs | Celery + Celery Beat |
| Push Notifications | Firebase Cloud Messaging (FCM) |
| Real-time | WebSockets |
| Auth | JWT + TOTP MFA |
| Infrastructure | Docker Compose, Caddy reverse proxy |

---

## Application Structure

```
/opt/nfm-workorders/
├── backend/           # FastAPI application
│   └── app/
│       ├── api/       # Route handlers
│       ├── models/    # SQLAlchemy models
│       ├── schemas/   # Pydantic request/response schemas
│       ├── services/  # Business logic
│       ├── workers/   # Celery tasks
│       └── core/      # Auth, security, config
├── frontend/          # React SPA
│   └── src/
│       ├── pages/     # Route pages
│       ├── components/# UI components
│       ├── api/       # API client modules
│       ├── stores/    # Zustand state stores
│       └── hooks/     # Custom React hooks
├── infra/             # docker-compose.yml
└── scripts/           # Seed data, QR sheet generator
```

---

## Multi-Tenancy & Organization Hierarchy

The system is multi-tenant. Each organization has its own isolated data. The hierarchy is:

```
Organization
└── Area (e.g., "Delaware Basin North")
    └── Location (e.g., "Section 12 Pad")
        └── Site (e.g., "Well A-1")
            └── Asset (e.g., "Separator SP-001")
```

Site types: `WELLSITE`, `PRODUCTION_FACILITY`, `STORAGE`, `TERMINAL`, `OFFSHORE_PLATFORM`

---

## User Roles & Permissions

Seven roles with increasing privilege:

| Role | Description |
|------|-------------|
| `READ_ONLY` | View-only access to work orders and dashboards |
| `COST_ANALYST` | Read-only plus access to budget and cost reports |
| `TECHNICIAN` | Assigned work, logs labor/parts, resolves work orders |
| `OPERATOR` | Creates work orders, views area-scoped data |
| `SUPERVISOR` | Assigns, verifies, closes work orders; manages shifts |
| `ADMIN` | Full org management, user CRUD, SLA config |
| `SUPER_ADMIN` | Cross-org access, system-level settings |

Users can also be scoped to specific **areas**, so a technician only sees work in their assigned area. Granular permissions can be layered on top of roles.

---

## Work Order Lifecycle

### Types

- **REACTIVE** — Unplanned breakdown or issue
- **PREVENTIVE** — Scheduled maintenance from PM templates
- **INSPECTION** — Routine inspection
- **CORRECTIVE** — Follow-up repair from an inspection finding

### Priorities

- **IMMEDIATE** — Drop everything
- **URGENT** — Same-day response
- **SCHEDULED** — Planned within SLA window
- **DEFERRED** — Low priority, no rush

### Status Flow

```
NEW → ASSIGNED → ACCEPTED → IN_PROGRESS → RESOLVED → VERIFIED → CLOSED
                                ↕
                        WAITING_ON_OPS
                        WAITING_ON_PARTS

Any open status → ESCALATED (manual or automatic via SLA breach)
CLOSED → (ADMIN can reopen)
```

Each transition is validated by a state machine. Only authorized roles can perform certain transitions (e.g., only `SUPERVISOR+` can verify or close).

### Work Order Features

- **Human-readable numbers** — `WO-2026-000042` format, auto-incrementing per org
- **Safety flags** — Mark hazardous work orders with safety notes and required certifications
- **ETA tracking** — Technicians set estimated time to arrival on accept
- **SLA deadlines** — Acknowledgment, first update, and resolution deadlines calculated from priority
- **GPS snapshots** — Optional location capture at accept, start, and resolve
- **Idempotency** — Duplicate creation requests are detected and rejected via `X-Idempotency-Key`
- **Timeline** — Every status change, message, attachment, part add, labor log, SLA breach, and escalation is recorded as a timeline event
- **Messages** — Threaded notes/messages within each work order
- **Attachments** — Photo/file uploads stored in MinIO (S3)
- **Parts used** — Track parts consumed with quantity and cost
- **Labor logs** — Record technician hours worked per work order

---

## SLA Management

SLA deadlines are computed automatically based on work order priority. The organization's SLA configuration defines response times, first-update windows, and resolution targets for each priority level.

A **Celery Beat task runs every 5 minutes** to detect breaches:

| Breach Type | Trigger |
|-------------|---------|
| `ACK_BREACH` | Past acknowledgment deadline, work order not yet accepted |
| `FIRST_UPDATE_BREACH` | Past first-update deadline with no user activity |
| `RESOLVE_BREACH` | Past resolution deadline, auto-escalates the work order |

Breaches create `SLAEvent` records and send escalation notifications. Supervisors can acknowledge breaches.

---

## Preventive Maintenance (PM)

### PM Templates

Define recurring maintenance tasks scoped to a site or asset:
- **Recurrence types:** Daily, Weekly, Biweekly, Monthly, Quarterly, Semi-Annual, Annual, Custom Days
- **Checklist** — JSON checklist of steps
- **Role assignment** — Which role should perform the work
- **Certification requirement** — Required cert for the assigned technician

### PM Schedules

- Generated from templates automatically by a **daily Celery Beat task at 06:00**
- Each schedule entry has a due date and status: `PENDING`, `GENERATED`, or `SKIPPED`
- When generated, a work order of type `PREVENTIVE` is created with the next recurrence date calculated
- A **reminder task at 08:00** sends notifications for PMs due within 24 hours

The frontend shows a **calendar view** of upcoming and past PM schedules.

---

## Parts & Inventory

- **Parts catalog** — Part number (unique per org), description, unit cost, supplier info, barcode, storage location
- **Stock tracking** — Current quantity and reorder threshold
- **Transactions** — `IN` (received), `OUT` (consumed), `ADJUSTMENT` (correction), with notes and user tracking
- **Low-stock alerts** — Filter by parts below reorder threshold
- **Work order integration** — Parts used on a work order are logged with quantity and cost, automatically creating `OUT` transactions
- **QR codes** — Each part has a scannable QR token

---

## Budget Tracking

- **Area-level monthly budgets** — Set a budget amount per area per month
- **Actual spend** — Automatically calculated when work orders close:
  - Parts cost: sum of (unit_cost x quantity) from parts used
  - Labor cost: sum of (minutes x org labor rate) from labor logs
- **Variance reporting** — Budget vs. actual with reports and CSV export
- Recalculated by a Celery task triggered on work order close

---

## Reports & Analytics

Ten built-in reports, all exportable to CSV:

| Report | What It Shows |
|--------|--------------|
| Work Orders | Summary by status, type, priority |
| Response Times | Time from creation to acceptance |
| SLA Compliance | Breach events with acknowledgment status |
| Parts Spend | Parts cost analysis by work order/area |
| Labor Cost | Labor hours and cost by technician/area |
| Budget | Budget vs. actual spend by area/month |
| PM Completion | Preventive maintenance completion rates |
| Technician Performance | Per-technician WO count, avg resolution time |
| Safety Flags | Safety-flagged work order summary |
| Incentives | Incentive program scores |

---

## Incentive Programs

Define gamified performance programs with measurable metrics:

- **MTTR** — Mean Time To Repair
- **FIRST_TIME_FIX** — First-time fix rate
- **SLA_COMPLIANCE** — Percentage of SLA targets met
- **WO_COMPLETION_RATE** — Work orders completed on time
- **SAFETY_SCORE** — Safety compliance scoring
- **CUSTOMER_SATISFACTION** — Satisfaction ratings

Programs have configurable periods (Weekly, Monthly, Quarterly, Annual) with target values and bonus descriptions. Scores are tracked per user per period.

---

## Shifts & On-Call

### Shift Schedules
- Define named shifts per area (e.g., "Day Shift 6a-6p")
- Start/end times, days of week, timezone
- Assign users to shifts

### On-Call Schedules
- Date-range-based on-call assignments per area
- Priority levels: `PRIMARY` and `SECONDARY`
- Users can toggle on-shift status from the frontend

---

## QR Code Scanning

The frontend includes a **camera-based QR scanner** that resolves tokens for:

| Entity | Info Returned |
|--------|--------------|
| Location | Location details + open work order count |
| Site | Site details + open WO count + safety flags |
| Asset | Asset details + open WO count |
| Part | Part details + current stock level |

Scanning an asset or site QR code lets a technician immediately see open work or create a new work order. A script (`scripts/generate_qr_sheet.py`) generates printable QR sheets for physical labeling.

---

## Real-Time Updates

- **WebSocket endpoint** (`/ws`) with JWT token authentication
- Broadcasts work order status changes, new assignments, and escalations to connected users
- Organization-scoped — users only receive events for their org
- Heartbeat/ping-pong for connection health
- Redis pub-sub used as the message relay between backend instances

---

## Push Notifications

- **Firebase Cloud Messaging (FCM)** for mobile/browser push notifications
- Users register their FCM token via the API
- Notifications sent for: new assignments, status changes, SLA breaches, PM reminders, escalations
- **Per-area notification preferences** — users can toggle push and email notifications per area
- Email notifications via SendGrid

---

## Offline & PWA Support

- **Progressive Web App** with service worker (Workbox)
- Installable on iOS and Android home screens
- **Offline queue** — Actions taken while offline are queued and synced when connectivity returns
- **Runtime caching** — Dashboard, work orders, sites, assets, and parts data cached with NetworkFirst strategy
- **Static asset caching** — Images and fonts cached with CacheFirst strategy
- iOS install prompt component for guided installation

---

## Authentication & Security

- **JWT tokens** — Short-lived access tokens + long-lived refresh tokens
- **MFA** — TOTP-based two-factor authentication with QR code enrollment for authenticator apps
- **Password hashing** — bcrypt
- **Token revocation** — Refresh tokens revoked on logout via Redis
- **CORS** — Configured allowed origins
- **Rate limiting** — Auth endpoints are rate-limited
- **Request IDs** — Every request gets a unique ID for tracing
- **Idempotency** — Create operations require an idempotency key to prevent duplicates
- **Multi-tenant isolation** — All queries are scoped to the user's organization
- **Area-scoped access** — Non-admin users only see data in their assigned areas

---

## Technician Certifications

- Track certifications per technician: name, number, issuer, issue date, expiry
- PM templates can require a specific certification
- Safety-flagged work orders can specify a required certification

---

## Dashboard

The dashboard provides a real-time overview:

- **Organization overview** — Work order counts rolled up by area, broken down by priority
- **Escalated count** — Number of currently escalated work orders
- **Safety-flagged count** — Number of open safety-flagged work orders
- **Area detail** — Drill into an area to see per-site summaries
- **Site detail** — Technician assignments, waiting-on-parts/ops counts

---

## Docker Services

The application runs as seven containers via Docker Compose:

| Service | Port | Purpose |
|---------|------|---------|
| `postgres` | 5433 | Primary database |
| `redis` | 6380 | Cache, session store, WebSocket relay |
| `minio` | 9000, 9001 | S3-compatible file storage + admin console |
| `backend` | 8002 | FastAPI API server |
| `celery-worker` | — | Background task processing |
| `celery-beat` | — | Scheduled task runner |
| `frontend` | 5173 | Vite React dev server |

Caddy reverse proxy sits in front on ports 80/443, routing `/api/*` and `/ws/*` to the backend and everything else to the frontend. Caddy auto-provisions TLS certificates via Let's Encrypt.

---

## Demo Data

The seed script (`scripts/seed.py`) creates two demo organizations with realistic oilfield data:

- **Permian Basin Operations** — Delaware Basin and Midland Basin areas
- **Eagle Ford Services** — Karnes County and DeWitt County areas

Each org gets a full set of users, sites, assets, work orders, PM templates, shifts, and parts.
