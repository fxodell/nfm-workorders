# ASSUMPTIONS.md — Oilfield Maintenance CMMS

All default decisions made during implementation are documented here.

---

## Multi-Tenancy

- **Multi-tenant SaaS by default**: Every operational table includes an `org_id` column.
- Every SQLAlchemy query in the service layer filters by `org_id`.
- Every endpoint that accepts an entity ID verifies the entity belongs to the requesting user's organization before returning or mutating data.
- **OWASP Broken Object Level Authorization (BOLA)** is the target threat; object-level checks are required in every handler.
- **Single-tenant operation**: Create one organization and disable self-serve registration via environment variable `ALLOW_SELF_REGISTRATION=false` (default).

## Time and Timezone

- All timestamps are stored in **UTC** (`timestamptz` in PostgreSQL).
- Each `Site` stores `site_timezone` as an IANA timezone string (e.g., `"America/Chicago"`).
- Each `Area` stores `timezone` as an IANA timezone string.
- **Seed default timezone**: `America/Chicago` (US Central, common for Texas/Oklahoma/Louisiana oilfields).
- Shift schedules are stored per Area with `start_time`, `end_time` (local time), `days_of_week`, and timezone reference.
- The frontend displays times in the user's browser timezone by default, with an option to view in site timezone.

## Authentication Defaults

- **Email + password** for MVP. No OAuth/SSO in initial release.
- **Access token TTL**: 15 minutes (JWT, HS256).
- **Refresh token TTL**: 7 days, rotated on every use (old token invalidated).
- Revoked refresh token JTIs stored in a **Redis SET** with TTL matching token expiry.
- **Password hashing**: bcrypt with cost factor 12 via `passlib`.
- **Minimum password length**: 8 characters, enforced by Pydantic validator.
- **Account lockout**: After 10 failed login attempts within 15 minutes, account is locked for 30 minutes. Tracked in Redis.
- **MFA**: TOTP-based via `pyotp`, required by default for `ADMIN` and `SUPERVISOR` roles.
  - Configurable per org via `org.config.mfa_required_roles`.
  - MFA session token TTL: 2 minutes (separate signing key).
  - Users can disable MFA only by providing a valid current TOTP code.

## SLA Defaults

Fully admin-configurable per organization via `org.config.sla`:

| Priority   | Acknowledge | First Update | Resolve |
|------------|-------------|--------------|---------|
| IMMEDIATE  | 15 min      | 30 min       | 4 hours |
| URGENT     | 60 min      | 2 hours      | 12 hours|
| SCHEDULED  | 8 hours     | 24 hours     | 5 days  |
| DEFERRED   | 24 hours    | 72 hours     | 14 days |

- SLA deadlines are computed at work order creation time from the org's SLA config.
- Celery beat checks for breaches every 5 minutes.
- Escalation is enabled by default (`escalation_enabled: true`).
- Per-Area and per-Priority overrides are not implemented in MVP; org-level config applies uniformly.

## Offline Support

- **Open work orders** are always cached on the device (IndexedDB).
- **Closed work orders**: Last 90 days cached (configurable via `org.config.closed_wo_cache_days`).
- **Durable write queue**: Unsynced changes are **NEVER auto-deleted**.
  - Warning toast at 24 hours of unsynced changes.
  - Prominent modal warning at 48 hours.
- **Conflict resolution**:
  - Server FSM is authoritative for status transitions.
  - Timeline events are append-only (no conflicts possible).
  - Editable fields use **last-write-wins** with full audit history.
  - ConflictResolutionModal shown when server state diverges from queued change.
- **iOS handling**: Foreground queue drain on `online` event (Background Sync API not available on iOS).
- **Storage target**: Under 50 MB for cached data.
- `navigator.storage.persist()` called on app install.

## Privacy

- **No continuous live location tracking**.
- Optional GPS snapshot at job accept / start / resolve.
- Controlled by org config flags (`gps_snapshot_on_accept`, `gps_snapshot_on_start`, `gps_snapshot_on_resolve`).
- **All GPS features OFF by default**.
- GPS data stored only on the work order record, not in a separate tracking table.

## Currency

- **Default**: USD.
- `org.currency_code` (ISO 4217) is org-level configurable.
- All monetary values stored as `DECIMAL(12, 2)`.
- Frontend formats using `Intl.NumberFormat` with the org's currency code.

## Units

- Measurements stored with `value` + `unit` metadata (JSONB where applicable).
- **Default UI**: US customary units (oilfield-standard: PSI, °F, bbl, ft).
- Unit conversion is not implemented in MVP; stored values are displayed as-is.

## Labor Rate

- `org.config.default_labor_rate_per_hour`: Default `75.00` (decimal).
- Used for budget `actual_spend` calculation: `(labor_minutes / 60) * rate + parts_cost`.
- Shown only to users with `CAN_VIEW_COSTS` permission.
- Per-user labor rates are not supported in MVP; org-wide rate applies.

## Work Order Numbering

- Format: `WO-YYYY-NNNNNN` (e.g., `WO-2025-000042`).
- `YYYY` = year of creation.
- `NNNNNN` = zero-padded sequential counter, unique per org.
- Counter tracked via a database sequence per org (stored in org config or dedicated counter table).
- Sequence resets are NOT performed at year boundaries to avoid collisions.

## Notifications

- **Firebase Cloud Messaging (FCM)** for push notifications (handles both APNs and Android).
- **SendGrid** for transactional email; falls back to stdout logging if `SENDGRID_API_KEY` not set.
- Email fallback fires when FCM fails or user has no `fcm_token`.
- ESCALATED events always trigger email regardless of push result.

## File Storage

- **AWS S3 / MinIO** for photos and documents.
- Pre-signed URLs only; file bytes never pass through the API server.
- Pre-signed URL TTL: 15 minutes.
- Maximum file size: 25 MB (enforced client-side).

## Database

- **PostgreSQL 16** as primary database.
- All IDs are UUIDs (uuid4), generated server-side.
- Soft deletes via `is_active` flag where applicable; hard deletes not performed.
- Indexes on: `org_id`, `area_id`, `site_id`, `status`, `priority`, `assigned_to`, `qr_code_token`, `human_readable_number`.

## API Conventions

- All list endpoints return paginated results (default: 20 items, max: 100).
- Pagination via `?page=1&per_page=20`.
- Sorting via `?sort_by=created_at&sort_order=desc`.
- All timestamps in API responses are ISO 8601 UTC strings.
- Error responses follow the format: `{ "detail": "message" }`.

## Frontend

- **Single PWA** codebase for all devices (desktop, tablet, mobile).
- Responsive breakpoint: 768px (mobile ↔ desktop).
- Touch targets: minimum 48px (field use with gloves).
- Minimum body font size: 16px.
- High contrast color scheme for outdoor/sunlight readability.
- Theme color: `#1e3a5f` (dark navy blue).

## Seed Data

- 2 organizations for isolation testing.
- Realistic oilfield naming conventions (Permian Basin, Eagle Ford, etc.).
- Timestamps spread over last 90 days.
- All enum values represented in seed data.
