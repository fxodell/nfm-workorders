# Project Context

## Overview
OilfieldMaint is a multi-tenant CMMS (Computerized Maintenance Management System) for oilfield operations. It tracks work orders through a 10-state lifecycle, enforces SLA deadlines with automatic escalation, manages preventive maintenance schedules, parts inventory, budgets, and field technician coordination. Built as an offline-first PWA for field technicians in remote locations.

## Architecture
- **Frontend**: React 18 + TypeScript (Vite), Zustand state management, Tailwind CSS, PWA with Workbox service worker and IndexedDB offline queue
- **Backend**: FastAPI (Python 3.12+), async SQLAlchemy 2.0 with asyncpg, Pydantic schemas
- **Database**: PostgreSQL 16 with Alembic migrations
- **Cache/Pub-Sub**: Redis 7 — token revocation, rate limiting, WebSocket message relay
- **File Storage**: MinIO (S3-compatible) with pre-signed uploads
- **Background Jobs**: Celery + Celery Beat — SLA breach detection (every 5 min), PM work order generation (daily 06:00), PM reminders (daily 08:00), budget recalculation, email dispatch
- **Notifications**: Firebase Cloud Messaging (push), SendGrid (email)
- **Real-time**: WebSocket endpoint with JWT auth and Redis pub-sub relay
- **Reverse Proxy**: Caddy — auto-TLS via Let's Encrypt, routes `/api/*` and `/ws/*` to backend, everything else to frontend

## Key Files
| Path | Purpose |
|------|---------|
| `backend/app/api/` | FastAPI route handlers for all endpoints |
| `backend/app/models/` | SQLAlchemy ORM models (work_order, user, asset, part, etc.) |
| `backend/app/schemas/` | Pydantic request/response schemas |
| `backend/app/services/` | Business logic (work orders, SLA, PM, notifications, reports) |
| `backend/app/workers/` | Celery tasks (sla_tasks, pm_tasks, budget_tasks, email_tasks) |
| `backend/app/core/security.py` | JWT token creation/validation, password hashing, MFA |
| `backend/app/core/config.py` | Settings loaded from environment variables |
| `frontend/src/pages/` | Page-level React components (Dashboard, WorkOrders, PM, Inventory, etc.) |
| `frontend/src/api/` | API client modules matching backend endpoints |
| `frontend/src/stores/` | Zustand stores (auth, notifications, offline queue, UI state) |
| `frontend/src/hooks/` | Custom hooks (WebSocket, push notifications, QR scanner, offline queue) |
| `frontend/src/workers/` | Service worker for offline sync and caching |
| `infra/docker-compose.yml` | All Docker services (postgres, redis, minio, backend, celery, frontend) |
| `scripts/seed.py` | Seeds two demo orgs with users, sites, assets, work orders, PM templates |
| `.env` | Environment variables (database, Redis, JWT keys, S3, Firebase, CORS) |

## Development Setup
1. `cp .env.example .env`
2. `cd infra && docker compose up -d`
3. `docker compose exec backend alembic upgrade head`
4. `docker compose exec backend python -m scripts.seed`
5. Frontend: http://localhost:5173 | API docs: http://localhost:8002/docs
6. Login with `admin@permian-basin-ops.com` / `admin123!`
