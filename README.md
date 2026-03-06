# Oilfield Maintenance CMMS

Production-grade, offline-first Computerized Maintenance Management System (CMMS) purpose-built for oilfield maintenance operations and call-out tracking. Designed for field technicians working in remote locations with intermittent connectivity.

## Features

- **Multi-tenant SaaS** -- full org-level data isolation with row-level `org_id` filtering on every query
- **Offline-first PWA** -- IndexedDB-backed durable write queue that never auto-deletes unsynced changes
- **Work order lifecycle** -- 10-state FSM (NEW, ASSIGNED, ACCEPTED, IN_PROGRESS, WAITING_ON_OPS, WAITING_ON_PARTS, RESOLVED, VERIFIED, CLOSED, ESCALATED)
- **SLA enforcement** -- configurable per-priority ack/update/resolve deadlines with automatic escalation
- **QR code scanning** -- scan site, asset, or part QR codes to instantly create or look up work orders
- **Real-time updates** -- WebSocket push for live work order status changes
- **Push notifications** -- Firebase Cloud Messaging for mobile alerts; SendGrid email fallback
- **Preventive maintenance** -- recurring PM templates with checklists and auto-generated work orders
- **Parts inventory** -- stock tracking with reorder thresholds, barcode/QR lookup, and transaction history
- **Shift and on-call scheduling** -- per-area shift definitions with technician rotation management
- **Role-based access control** -- 7 roles (Super Admin, Admin, Supervisor, Operator, Technician, Read-Only, Cost Analyst)
- **MFA support** -- TOTP-based two-factor authentication, required by default for Admin and Supervisor roles
- **Safety flagging** -- safety-critical work orders with certification requirements (H2S, Hot Work, Confined Space, etc.)
- **GPS snapshots** -- optional location capture at job accept/start/resolve (privacy-first, off by default)
- **Photo attachments** -- S3/MinIO pre-signed upload with offline queuing
- **Budget tracking** -- area-level budget monitoring with labor rate calculations
- **CSV/report export** -- export work order data for regulatory and management reporting
- **Audit logging** -- immutable audit trail for compliance

## Tech Stack

### Backend
- **Python 3.12+** / FastAPI
- **PostgreSQL 16** with async SQLAlchemy 2.0 (asyncpg driver)
- **Redis 7** for session/token revocation, rate limiting, and pub/sub
- **Celery** with Redis broker for background tasks (SLA checks, PM generation, email dispatch)
- **MinIO / AWS S3** for file storage
- **Alembic** for database migrations

### Frontend
- **React 18** with TypeScript
- **Vite** for build tooling
- **Tailwind CSS** for styling
- **Zustand** for state management
- **IndexedDB** (via idb) for offline data persistence
- **Service Worker** for background sync and caching

## Architecture Overview

```
nfm-workorders/
├── backend/                    # FastAPI application
│   ├── app/
│   │   ├── api/                # Route handlers (REST endpoints)
│   │   ├── core/               # Config, security, database, deps
│   │   ├── models/             # SQLAlchemy ORM models
│   │   ├── schemas/            # Pydantic request/response schemas
│   │   ├── services/           # Business logic layer
│   │   ├── workers/            # Celery tasks (SLA, PM, email, budget)
│   │   ├── websockets/         # WebSocket manager and subscriber
│   │   ├── notifications/      # Push (FCM) and email (SendGrid)
│   │   └── reports/            # CSV export utilities
│   ├── Dockerfile
│   └── requirements.txt
├── frontend/                   # React PWA
│   ├── src/
│   │   ├── api/                # API client modules
│   │   ├── components/         # Reusable UI components
│   │   ├── hooks/              # Custom React hooks
│   │   ├── pages/              # Page-level components
│   │   ├── stores/             # Zustand state stores
│   │   ├── types/              # TypeScript type definitions
│   │   ├── utils/              # Formatting and helper utilities
│   │   └── workers/            # Service worker and offline sync
│   ├── Dockerfile.dev
│   └── package.json
├── infra/
│   └── docker-compose.yml      # PostgreSQL, Redis, MinIO, backend, frontend, Celery
├── scripts/
│   ├── seed.py                 # Database seed script
│   └── generate_qr_sheet.py    # QR code PDF generator
├── docs/                       # Project documentation
├── .env.example                # Environment variable template
└── ASSUMPTIONS.md              # Design decisions and defaults
```

## Prerequisites

- [Docker](https://docs.docker.com/get-docker/) and [Docker Compose](https://docs.docker.com/compose/install/) v2+
- [Node.js](https://nodejs.org/) 20+ (for local frontend development)
- [Python](https://www.python.org/) 3.12+ (for local backend development)

## Quick Start

1. **Clone the repository**
   ```bash
   git clone <repository-url>
   cd nfm-workorders
   ```

2. **Configure environment**
   ```bash
   cp .env.example .env
   # Edit .env if needed (defaults work for local development)
   ```

3. **Start all services**
   ```bash
   cd infra
   docker compose up -d
   ```

4. **Run database migrations**
   ```bash
   docker compose exec backend alembic upgrade head
   ```

5. **Seed demo data**
   ```bash
   docker compose exec backend python -m scripts.seed
   ```

6. **Access the application**
   - Frontend: [http://localhost:5173](http://localhost:5173)
   - API docs (Swagger): [http://localhost:8000/docs](http://localhost:8000/docs)
   - API docs (ReDoc): [http://localhost:8000/redoc](http://localhost:8000/redoc)
   - MinIO console: [http://localhost:9001](http://localhost:9001) (minioadmin / minioadmin)

## Default Credentials

After running the seed script, the following accounts are available:

### Permian Basin Operations (primary org)

| Role          | Email                                   | Password         |
|---------------|-----------------------------------------|------------------|
| Admin         | admin@apachecorp.com             | admin123!        |
| Supervisor    | supervisor@apachecorp.com        | supervisor123!   |
| Operator      | operator@apachecorp.com          | operator123!     |
| Technician    | tech1@apachecorp.com             | tech123!         |
| Technician    | tech2@apachecorp.com             | tech123!         |
| Technician    | tech3@apachecorp.com             | tech123!         |
| Read-Only     | viewer@apachecorp.com            | viewer123!       |
| Cost Analyst  | analyst@apachecorp.com           | analyst123!      |
| Super Admin   | superadmin@apachecorp.com        | super123!        |

### Eagle Ford Services (secondary org)

| Role          | Email                                   | Password         |
|---------------|-----------------------------------------|------------------|
| Admin         | admin@eagle-ford-services.com           | admin123!        |
| Supervisor    | supervisor@eagle-ford-services.com      | supervisor123!   |
| Operator      | operator@eagle-ford-services.com        | operator123!     |
| Technician    | tech1@eagle-ford-services.com           | tech123!         |

> **Note:** Admin accounts have MFA enabled with a test TOTP secret. For development, you can use any TOTP app with the base32 secret `JBSWY3DPEHPK3PXP` or disable MFA verification in development mode.

## Development

### Backend (local)

```bash
cd backend
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# Start with auto-reload (requires PostgreSQL and Redis running)
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

### Frontend (local)

```bash
cd frontend
npm install
npm run dev
```

### Running Tests

```bash
# Backend tests
cd backend
pytest

# With coverage
pytest --cov=app --cov-report=term-missing
```

### Generate QR Code Sheets

```bash
# Generate QR codes for all entities in an organization
docker compose exec backend python scripts/generate_qr_sheet.py \
  --org-id <org-uuid> \
  --entity-type all \
  --output /app/qr_sheet.pdf

# Generate only site QR codes
docker compose exec backend python scripts/generate_qr_sheet.py \
  --org-id <org-uuid> \
  --entity-type site
```

## API Documentation

Interactive API documentation is available at `/docs` (Swagger UI) when the backend is running. All endpoints require authentication via JWT Bearer token except `/auth/login` and `/auth/refresh`.

Key endpoint groups:

| Path                    | Description                        |
|-------------------------|------------------------------------|
| `/auth/*`               | Login, refresh, MFA verification   |
| `/users/*`              | User management                    |
| `/areas/*`              | Area CRUD                          |
| `/locations/*`          | Location CRUD                      |
| `/sites/*`              | Site CRUD and QR lookup            |
| `/assets/*`             | Asset CRUD and QR lookup           |
| `/work-orders/*`        | Work order lifecycle               |
| `/work-orders/*/timeline` | Timeline events and messages     |
| `/work-orders/*/attachments` | Photo/document uploads        |
| `/work-orders/*/parts`  | Parts used on work orders          |
| `/work-orders/*/labor`  | Labor logging                      |
| `/work-orders/*/sla`    | SLA status and events              |

## Environment Variables

| Variable                       | Default                                              | Description                                   |
|--------------------------------|------------------------------------------------------|-----------------------------------------------|
| `DATABASE_URL`                 | `postgresql+asyncpg://postgres:password@postgres:5432/ofmaint` | PostgreSQL connection string         |
| `REDIS_URL`                    | `redis://redis:6379/0`                               | Redis connection string                       |
| `SECRET_KEY`                   | `change-me-in-production-min-32-chars`               | JWT signing key for access/refresh tokens     |
| `WS_SECRET_KEY`                | `change-me-too-different-from-secret-key`            | JWT signing key for WebSocket tokens          |
| `MFA_SECRET_KEY`               | `change-me-too-different-again`                      | JWT signing key for MFA session tokens        |
| `ACCESS_TOKEN_EXPIRE_MINUTES`  | `15`                                                 | Access token TTL in minutes                   |
| `REFRESH_TOKEN_EXPIRE_DAYS`    | `7`                                                  | Refresh token TTL in days                     |
| `AWS_ACCESS_KEY_ID`            | `minioadmin`                                         | S3/MinIO access key                           |
| `AWS_SECRET_ACCESS_KEY`        | `minioadmin`                                         | S3/MinIO secret key                           |
| `AWS_ENDPOINT_URL`             | *(none)*                                             | S3 endpoint (set for MinIO, omit for AWS S3)  |
| `S3_BUCKET`                    | `ofmaint-uploads`                                    | S3 bucket name for file uploads               |
| `S3_PRESIGN_TTL`               | `900`                                                | Pre-signed URL TTL in seconds                 |
| `FIREBASE_SERVICE_ACCOUNT_JSON`| *(empty)*                                            | Firebase service account JSON for push notifs |
| `FIREBASE_VAPID_KEY`           | *(empty)*                                            | Firebase VAPID key for web push               |
| `SENDGRID_API_KEY`             | *(empty)*                                            | SendGrid API key for transactional email      |
| `EMAIL_FROM`                   | `noreply@yourorg.com`                                | Sender email address                          |
| `FRONTEND_URL`                 | `http://localhost:5173`                              | Frontend URL (used in emails and QR codes)    |
| `SENTRY_DSN`                   | *(empty)*                                            | Sentry DSN for error tracking                 |
| `OTEL_EXPORTER_OTLP_ENDPOINT`  | *(empty)*                                            | OpenTelemetry collector endpoint              |
| `ENVIRONMENT`                  | `development`                                        | Environment name (development/production)     |
| `LOG_LEVEL`                    | `INFO`                                               | Application log level                         |
| `ALLOW_SELF_REGISTRATION`      | `false`                                              | Allow users to self-register                  |

## Deployment Notes

- **Production secrets**: Generate strong random values for `SECRET_KEY`, `WS_SECRET_KEY`, and `MFA_SECRET_KEY` (minimum 32 characters each). Never reuse keys across environments.
- **Database**: Use a managed PostgreSQL instance (RDS, Cloud SQL, etc.) with connection pooling. Update `DATABASE_URL` accordingly.
- **Redis**: Use a managed Redis instance (ElastiCache, Memorystore, etc.) with TLS enabled.
- **File storage**: Switch from MinIO to AWS S3 by removing `AWS_ENDPOINT_URL` and providing real AWS credentials.
- **HTTPS**: Terminate TLS at a load balancer or reverse proxy (nginx, Caddy, ALB). Set secure cookie flags in production.
- **Push notifications**: Configure Firebase Cloud Messaging with a real service account for production push notifications.
- **Email**: Set a valid `SENDGRID_API_KEY` for production email delivery.
- **Monitoring**: Configure Sentry (`SENTRY_DSN`) and OpenTelemetry (`OTEL_EXPORTER_OTLP_ENDPOINT`) for production observability.
- **Scaling**: The backend is stateless and horizontally scalable. Run multiple Celery workers for background task throughput. Use Redis Sentinel or Cluster for high availability.

## License

MIT
