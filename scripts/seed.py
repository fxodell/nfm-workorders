"""
Database seed script for Oilfield Maintenance CMMS.

Creates two organizations with realistic oilfield data:
  - Permian Basin Operations (primary, extensive data)
  - Eagle Ford Services (secondary, minimal data for isolation testing)

Run with:
    python -m scripts.seed          (from project root)
    python scripts/seed.py          (alternative)

Idempotent: checks for existing organizations before inserting.
"""

from __future__ import annotations

import asyncio
import random
import sys
import uuid
from datetime import date, datetime, time, timedelta, timezone
from pathlib import Path

# Ensure the backend package is on sys.path when executed directly.
_backend_dir = Path(__file__).resolve().parent.parent / "backend"
if str(_backend_dir) not in sys.path:
    sys.path.insert(0, str(_backend_dir))

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import async_session
from app.core.security import hash_password
from app.models import (  # noqa: E402
    Area,
    Asset,
    Location,
    OnCallSchedule,
    Organization,
    Part,
    PartTransaction,
    PMSchedule,
    PMTemplate,
    ShiftSchedule,
    Site,
    SLAEvent,
    TimelineEvent,
    User,
    UserShiftAssignment,
    WOCounter,
    WorkOrder,
    WorkOrderPartUsed,
)
from app.models.part import TransactionType
from app.models.pm import PMAssignedRole, PMScheduleStatus, RecurrenceType
from app.models.site import SiteType
from app.models.sla import SLAEventType
from app.models.user import OnCallPriority, UserRole
from app.models.work_order import (
    TimelineEventType,
    WorkOrderPriority,
    WorkOrderStatus,
    WorkOrderType,
)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

NOW = datetime.now(timezone.utc)
YEAR = NOW.year

DEFAULT_SLA_CONFIG = {
    "sla": {
        "IMMEDIATE": {
            "ack_minutes": 15,
            "first_update_minutes": 30,
            "resolve_minutes": 240,
        },
        "URGENT": {
            "ack_minutes": 60,
            "first_update_minutes": 120,
            "resolve_minutes": 720,
        },
        "SCHEDULED": {
            "ack_minutes": 480,
            "first_update_minutes": 1440,
            "resolve_minutes": 7200,
        },
        "DEFERRED": {
            "ack_minutes": 1440,
            "first_update_minutes": 4320,
            "resolve_minutes": 20160,
        },
    },
    "timezone": "America/Chicago",
    "default_labor_rate_per_hour": 75.00,
    "escalation_enabled": True,
    "gps_snapshot_on_accept": False,
    "gps_snapshot_on_start": False,
    "gps_snapshot_on_resolve": False,
    "mfa_required_roles": ["ADMIN", "SUPERVISOR"],
    "closed_wo_cache_days": 90,
}

# Realistic Permian Basin coordinates (West Texas / SE New Mexico)
PERMIAN_GPS = [
    (31.9973, -102.0779),  # Midland area
    (31.8457, -102.3676),  # Odessa area
    (32.4487, -100.4505),  # Snyder area
    (32.7357, -103.1782),  # Hobbs NM area
    (31.3382, -103.5029),  # Pecos area
    (32.1301, -101.4855),  # Big Spring area
]

# Realistic Eagle Ford coordinates (South Texas)
EAGLE_FORD_GPS = [
    (28.7091, -98.0842),  # Karnes City area
    (28.9377, -97.7432),  # Gonzales area
    (29.3329, -98.8908),  # Poteet area
    (28.3483, -99.7488),  # Laredo area
]

# Realistic oilfield part numbers and descriptions
PARTS_CATALOG = [
    ("PMP-VLV-001", "2-inch gate valve, 5000 PSI WP", 245.00, "Shelf A-1", 10, 3, "Cameron"),
    ("PMP-SEAL-002", "Pump packing seal kit, 4-inch", 89.50, "Shelf A-2", 25, 5, "National Oilwell"),
    ("CMP-FLT-003", "Compressor air filter element", 67.00, "Shelf B-1", 15, 4, "Ingersoll Rand"),
    ("CMP-BRG-004", "Main bearing set, compressor crankshaft", 1250.00, "Shelf B-2", 2, 1, "Ariel Corp"),
    ("ELC-MTR-005", "Electric motor 50HP 480V 3-phase", 3200.00, "Warehouse C", 1, 1, "WEG"),
    ("PIP-GSK-006", "6-inch RTJ gasket, ring type", 32.00, "Shelf A-3", 50, 10, "Flexitallic"),
    ("TNK-LVL-007", "Tank level transmitter, 4-20mA", 850.00, "Shelf D-1", 3, 1, "Emerson"),
    ("WHL-ROD-008", "Sucker rod, 7/8-inch x 25ft", 185.00, "Rod Yard", 40, 8, "Weatherford"),
    ("SEP-DMR-009", "Demister pad, 36-inch separator", 425.00, "Shelf B-3", 4, 2, "Koch-Glitsch"),
    ("SAF-PRV-010", "Pressure relief valve 2-in, set at 250 PSI", 575.00, "Shelf D-2", 6, 2, "Dresser"),
]

# Work order templates for realistic oilfield maintenance scenarios
WO_TEMPLATES = [
    {
        "title": "Wellhead leak - flange connection",
        "description": "Reported gas leak at wellhead flange connection. H2S monitor alarm triggered. Isolate well and repair.",
        "type": WorkOrderType.REACTIVE,
        "priority": WorkOrderPriority.IMMEDIATE,
        "safety_flag": True,
        "safety_notes": "H2S potential. Full SCBA required. Buddy system mandatory.",
        "required_cert": "H2S Alive",
        "tags": ["h2s", "leak", "wellhead"],
    },
    {
        "title": "Compressor unit #3 high vibration alarm",
        "description": "Vibration levels exceeding threshold on unit #3 compressor. Possible bearing failure.",
        "type": WorkOrderType.REACTIVE,
        "priority": WorkOrderPriority.URGENT,
        "safety_flag": False,
        "tags": ["compressor", "vibration", "alarm"],
    },
    {
        "title": "Tank battery level gauge malfunction",
        "description": "Level gauge on tank #2 reading erratically. Unable to verify oil level. Manual gauging required.",
        "type": WorkOrderType.CORRECTIVE,
        "priority": WorkOrderPriority.URGENT,
        "safety_flag": False,
        "tags": ["tank", "gauge", "instrumentation"],
    },
    {
        "title": "Quarterly pump jack inspection",
        "description": "Scheduled quarterly inspection of pump jack unit. Check stuffing box, polished rod, bridle, walking beam, and counterweights.",
        "type": WorkOrderType.INSPECTION,
        "priority": WorkOrderPriority.SCHEDULED,
        "safety_flag": False,
        "tags": ["pump-jack", "inspection", "quarterly"],
    },
    {
        "title": "Replace separator dump valve actuator",
        "description": "Dump valve actuator on production separator failing to cycle. Production loss risk. Replace actuator assembly.",
        "type": WorkOrderType.CORRECTIVE,
        "priority": WorkOrderPriority.URGENT,
        "safety_flag": True,
        "safety_notes": "Lock-out/tag-out required before working on pneumatic actuator.",
        "tags": ["separator", "valve", "actuator"],
    },
    {
        "title": "Pipeline right-of-way mowing",
        "description": "Annual mowing and clearing of pipeline right-of-way. Section NF-PL-001 through NF-PL-003.",
        "type": WorkOrderType.PREVENTIVE,
        "priority": WorkOrderPriority.DEFERRED,
        "safety_flag": False,
        "tags": ["pipeline", "maintenance", "row"],
    },
    {
        "title": "Chemical injection pump PM",
        "description": "Monthly preventive maintenance on chemical injection pump. Check diaphragm, valves, and calibrate injection rate.",
        "type": WorkOrderType.PREVENTIVE,
        "priority": WorkOrderPriority.SCHEDULED,
        "safety_flag": True,
        "safety_notes": "Chemical PPE required (goggles, gloves, apron).",
        "tags": ["chemical", "pump", "pm"],
    },
    {
        "title": "SCADA communication failure - RTU offline",
        "description": "Remote terminal unit at well site NF-WH-001 not communicating with SCADA. No telemetry data for 6 hours.",
        "type": WorkOrderType.REACTIVE,
        "priority": WorkOrderPriority.URGENT,
        "safety_flag": False,
        "tags": ["scada", "rtu", "communications"],
    },
    {
        "title": "Motor control center breaker trip",
        "description": "MCC breaker for saltwater disposal pump tripped. Check motor insulation and restart.",
        "type": WorkOrderType.REACTIVE,
        "priority": WorkOrderPriority.IMMEDIATE,
        "safety_flag": True,
        "safety_notes": "Arc flash PPE required. Only qualified electricians.",
        "required_cert": "NFPA 70E",
        "tags": ["electrical", "mcc", "breaker"],
    },
    {
        "title": "Semi-annual safety valve testing",
        "description": "Scheduled testing of all pressure safety valves in Central Processing area. Pop test and re-certify.",
        "type": WorkOrderType.INSPECTION,
        "priority": WorkOrderPriority.SCHEDULED,
        "safety_flag": True,
        "safety_notes": "High pressure testing. Clear area of non-essential personnel.",
        "tags": ["safety-valve", "testing", "compliance"],
    },
    {
        "title": "Flowline repair - corrosion pit",
        "description": "UT inspection found wall thinning on 4-inch production flowline. Schedule cutout and sleeve repair.",
        "type": WorkOrderType.CORRECTIVE,
        "priority": WorkOrderPriority.SCHEDULED,
        "safety_flag": True,
        "safety_notes": "Hot work permit required for welding. Fire watch mandatory.",
        "required_cert": "Hot Work",
        "tags": ["pipeline", "corrosion", "repair"],
    },
    {
        "title": "Install new flow meter on injection well",
        "description": "Regulatory requirement to install totalizing flow meter on SWD injection well per permit conditions.",
        "type": WorkOrderType.CORRECTIVE,
        "priority": WorkOrderPriority.SCHEDULED,
        "safety_flag": False,
        "tags": ["flow-meter", "compliance", "installation"],
    },
    {
        "title": "Glycol dehydrator reboiler tune-up",
        "description": "Reboiler temperature running low. Clean fire tube, check thermocouple, and adjust burner.",
        "type": WorkOrderType.CORRECTIVE,
        "priority": WorkOrderPriority.URGENT,
        "safety_flag": True,
        "safety_notes": "Natural gas fired equipment. Combustible gas detector required.",
        "tags": ["dehydrator", "reboiler", "glycol"],
    },
    {
        "title": "Replace rod pump stuffing box",
        "description": "Excessive leak at stuffing box on well PB-WH-002. Replace packing and polish rod liner.",
        "type": WorkOrderType.CORRECTIVE,
        "priority": WorkOrderPriority.SCHEDULED,
        "safety_flag": False,
        "tags": ["pump-jack", "stuffing-box", "packing"],
    },
    {
        "title": "Annual cathodic protection survey",
        "description": "Perform annual CP survey on all buried pipelines in North Field area. Record pipe-to-soil potentials.",
        "type": WorkOrderType.INSPECTION,
        "priority": WorkOrderPriority.DEFERRED,
        "safety_flag": False,
        "tags": ["cathodic-protection", "pipeline", "survey"],
    },
    {
        "title": "Emergency generator load bank test",
        "description": "Quarterly load bank test of emergency standby generator at Central Processing facility.",
        "type": WorkOrderType.PREVENTIVE,
        "priority": WorkOrderPriority.SCHEDULED,
        "safety_flag": True,
        "safety_notes": "Hearing protection required. Do not approach exhaust.",
        "tags": ["generator", "load-test", "emergency"],
    },
    {
        "title": "Tank battery firewall repair",
        "description": "Recent rain eroded section of tank battery firewall. Repair berm to maintain containment integrity.",
        "type": WorkOrderType.CORRECTIVE,
        "priority": WorkOrderPriority.SCHEDULED,
        "safety_flag": False,
        "tags": ["tank-battery", "firewall", "containment"],
    },
    {
        "title": "Wellhead winterization checklist",
        "description": "Pre-winter checks: drain lines, check heat tracing, insulate exposed piping, test freeze protection.",
        "type": WorkOrderType.PREVENTIVE,
        "priority": WorkOrderPriority.SCHEDULED,
        "safety_flag": False,
        "tags": ["winterization", "wellhead", "freeze-protection"],
    },
    {
        "title": "Production separator internals inspection",
        "description": "Scheduled internal inspection of 3-phase production separator. Check weir plates, coalescing media, and mist extractor.",
        "type": WorkOrderType.INSPECTION,
        "priority": WorkOrderPriority.DEFERRED,
        "safety_flag": True,
        "safety_notes": "Confined space entry. Permit required. Standby rescue team.",
        "required_cert": "Confined Space",
        "tags": ["separator", "inspection", "confined-space"],
    },
    {
        "title": "Lease road grading and maintenance",
        "description": "Grade and maintain lease road access to South Field locations. Pot holes and washouts reported.",
        "type": WorkOrderType.CORRECTIVE,
        "priority": WorkOrderPriority.DEFERRED,
        "safety_flag": False,
        "tags": ["roads", "maintenance", "access"],
    },
]

# Status progression for WO lifecycle simulation
STATUS_PROGRESSIONS: list[list[tuple[WorkOrderStatus, int]]] = [
    # Offset from created_at in hours
    [(WorkOrderStatus.NEW, 0)],
    [(WorkOrderStatus.NEW, 0), (WorkOrderStatus.ASSIGNED, 1)],
    [
        (WorkOrderStatus.NEW, 0),
        (WorkOrderStatus.ASSIGNED, 1),
        (WorkOrderStatus.ACCEPTED, 2),
    ],
    [
        (WorkOrderStatus.NEW, 0),
        (WorkOrderStatus.ASSIGNED, 1),
        (WorkOrderStatus.ACCEPTED, 2),
        (WorkOrderStatus.IN_PROGRESS, 3),
    ],
    [
        (WorkOrderStatus.NEW, 0),
        (WorkOrderStatus.ASSIGNED, 1),
        (WorkOrderStatus.ACCEPTED, 2),
        (WorkOrderStatus.IN_PROGRESS, 3),
        (WorkOrderStatus.WAITING_ON_PARTS, 8),
    ],
    [
        (WorkOrderStatus.NEW, 0),
        (WorkOrderStatus.ASSIGNED, 1),
        (WorkOrderStatus.ACCEPTED, 2),
        (WorkOrderStatus.IN_PROGRESS, 3),
        (WorkOrderStatus.RESOLVED, 10),
    ],
    [
        (WorkOrderStatus.NEW, 0),
        (WorkOrderStatus.ASSIGNED, 1),
        (WorkOrderStatus.ACCEPTED, 2),
        (WorkOrderStatus.IN_PROGRESS, 3),
        (WorkOrderStatus.RESOLVED, 10),
        (WorkOrderStatus.VERIFIED, 14),
    ],
    [
        (WorkOrderStatus.NEW, 0),
        (WorkOrderStatus.ASSIGNED, 1),
        (WorkOrderStatus.ACCEPTED, 2),
        (WorkOrderStatus.IN_PROGRESS, 3),
        (WorkOrderStatus.RESOLVED, 10),
        (WorkOrderStatus.VERIFIED, 14),
        (WorkOrderStatus.CLOSED, 18),
    ],
    [
        (WorkOrderStatus.NEW, 0),
        (WorkOrderStatus.ASSIGNED, 1),
        (WorkOrderStatus.ACCEPTED, 2),
        (WorkOrderStatus.IN_PROGRESS, 4),
        (WorkOrderStatus.ESCALATED, 12),
    ],
    [
        (WorkOrderStatus.NEW, 0),
        (WorkOrderStatus.ASSIGNED, 1),
        (WorkOrderStatus.ACCEPTED, 2),
        (WorkOrderStatus.IN_PROGRESS, 3),
        (WorkOrderStatus.WAITING_ON_OPS, 6),
    ],
]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _rand_dt_past(max_days: int = 90) -> datetime:
    """Return a random UTC datetime within the last ``max_days`` days."""
    offset = timedelta(
        days=random.randint(1, max_days),
        hours=random.randint(0, 23),
        minutes=random.randint(0, 59),
    )
    return NOW - offset


def _sla_deadline(created: datetime, priority: WorkOrderPriority, field: str) -> datetime:
    """Compute SLA deadline from default config."""
    sla = DEFAULT_SLA_CONFIG["sla"][priority.value]
    return created + timedelta(minutes=sla[field])


def _wo_number(counter: int) -> str:
    """Format a human-readable work order number."""
    return f"WO-{YEAR}-{counter:06d}"


# ---------------------------------------------------------------------------
# Seed Functions
# ---------------------------------------------------------------------------


async def _create_org(
    session: AsyncSession,
    name: str,
    slug: str,
    currency: str = "USD",
) -> Organization:
    org = Organization(
        name=name,
        slug=slug,
        currency_code=currency,
        config=DEFAULT_SLA_CONFIG,
    )
    session.add(org)
    await session.flush()
    return org


async def _create_wo_counter(
    session: AsyncSession,
    org_id: uuid.UUID,
    initial: int = 0,
) -> WOCounter:
    counter = WOCounter(org_id=org_id, year=YEAR, counter=initial)
    session.add(counter)
    await session.flush()
    return counter


async def _create_users(
    session: AsyncSession,
    org_id: uuid.UUID,
    slug: str,
) -> dict[str, User]:
    """Create users for all 7 roles. Returns dict keyed by role name."""
    user_defs = [
        {
            "name": "Admin User",
            "email": f"admin@{slug}.com",
            "password": "admin123!",
            "role": UserRole.ADMIN,
            "mfa_enabled": False,
        },
        {
            "name": "Field Supervisor",
            "email": f"supervisor@{slug}.com",
            "password": "supervisor123!",
            "role": UserRole.SUPERVISOR,
        },
        {
            "name": "Lease Operator",
            "email": f"operator@{slug}.com",
            "password": "operator123!",
            "role": UserRole.OPERATOR,
        },
        {
            "name": "Lead Technician",
            "email": f"tech1@{slug}.com",
            "password": "tech123!",
            "role": UserRole.TECHNICIAN,
            "phone": "+14325551001",
        },
        {
            "name": "Field Technician",
            "email": f"tech2@{slug}.com",
            "password": "tech123!",
            "role": UserRole.TECHNICIAN,
            "phone": "+14325551002",
        },
        {
            "name": "Junior Technician",
            "email": f"tech3@{slug}.com",
            "password": "tech123!",
            "role": UserRole.TECHNICIAN,
            "phone": "+14325551003",
        },
        {
            "name": "Read-Only Viewer",
            "email": f"viewer@{slug}.com",
            "password": "viewer123!",
            "role": UserRole.READ_ONLY,
        },
        {
            "name": "Cost Analyst",
            "email": f"analyst@{slug}.com",
            "password": "analyst123!",
            "role": UserRole.COST_ANALYST,
        },
        {
            "name": "Super Admin",
            "email": f"superadmin@{slug}.com",
            "password": "super123!",
            "role": UserRole.SUPER_ADMIN,
        },
    ]

    users: dict[str, User] = {}
    for udef in user_defs:
        # Skip hardcoded emails that may already exist from another org
        existing = await session.execute(
            select(User).where(User.email == udef["email"])
        )
        if existing.scalars().first() is not None:
            continue
        user = User(
            org_id=org_id,
            name=udef["name"],
            email=udef["email"],
            password_hash=hash_password(udef["password"]),
            role=udef["role"],
            phone=udef.get("phone"),
            mfa_enabled=udef.get("mfa_enabled", False),
            totp_secret=udef.get("totp_secret"),
            is_active=True,
        )
        session.add(user)
        # Key by a friendly label
        label = udef["role"].value.lower()
        if label == "technician" and "tech1" not in users:
            users["tech1"] = user
        elif label == "technician" and "tech2" not in users:
            users["tech2"] = user
        elif label == "technician":
            users["tech3"] = user
        else:
            users[label] = user

    await session.flush()
    return users


async def _create_areas(
    session: AsyncSession,
    org_id: uuid.UUID,
) -> list[Area]:
    area_defs = [
        ("North Field", "Northern lease block operations covering wells NF-001 through NF-045"),
        ("South Field", "Southern lease block operations, primarily pump jack and rod pump wells"),
        ("Central Processing", "Central gathering and processing facility, compressor station, and tank farms"),
    ]
    areas = []
    for name, desc in area_defs:
        area = Area(
            org_id=org_id,
            name=name,
            description=desc,
            timezone="America/Chicago",
        )
        session.add(area)
        areas.append(area)
    await session.flush()
    return areas


async def _create_locations(
    session: AsyncSession,
    org_id: uuid.UUID,
    areas: list[Area],
    gps_coords: list[tuple[float, float]],
) -> list[Location]:
    location_names = [
        ["North Pad A", "North Pad B"],
        ["South Pad A", "South Pad B"],
        ["Processing East", "Processing West"],
    ]
    locations = []
    gps_idx = 0
    for area, names in zip(areas, location_names):
        for name in names:
            lat, lng = gps_coords[gps_idx % len(gps_coords)]
            gps_idx += 1
            loc = Location(
                org_id=org_id,
                area_id=area.id,
                name=name,
                address=f"County Rd {random.randint(100, 999)}, West Texas",
                gps_lat=lat + random.uniform(-0.01, 0.01),
                gps_lng=lng + random.uniform(-0.01, 0.01),
            )
            session.add(loc)
            locations.append(loc)
    await session.flush()
    return locations


async def _create_sites(
    session: AsyncSession,
    org_id: uuid.UUID,
    locations: list[Location],
) -> list[Site]:
    # 3 sites per location with realistic types
    site_type_rotation = [
        [SiteType.WELL_SITE, SiteType.WELL_SITE, SiteType.TANK_BATTERY],
        [SiteType.WELL_SITE, SiteType.COMPRESSOR_STATION, SiteType.SEPARATOR],
        [SiteType.WELL_SITE, SiteType.WELL_SITE, SiteType.TANK_BATTERY],
        [SiteType.WELL_SITE, SiteType.SEPARATOR, SiteType.LINE],
        [SiteType.PLANT, SiteType.COMPRESSOR_STATION, SiteType.TANK_BATTERY],
        [SiteType.COMPRESSOR_STATION, SiteType.SEPARATOR, SiteType.PLANT],
    ]

    sites = []
    for loc_idx, loc in enumerate(locations):
        types = site_type_rotation[loc_idx % len(site_type_rotation)]
        for s_idx, stype in enumerate(types):
            prefix_map = {
                SiteType.WELL_SITE: "WH",
                SiteType.COMPRESSOR_STATION: "CS",
                SiteType.TANK_BATTERY: "TB",
                SiteType.SEPARATOR: "SEP",
                SiteType.PLANT: "PLT",
                SiteType.LINE: "PL",
            }
            prefix = prefix_map.get(stype, "ST")
            site_name = f"{loc.name.split()[0][:2].upper()}-{prefix}-{loc_idx * 3 + s_idx + 1:03d}"
            site = Site(
                org_id=org_id,
                location_id=loc.id,
                name=site_name,
                type=stype,
                address=loc.address,
                gps_lat=float(loc.gps_lat) + random.uniform(-0.005, 0.005) if loc.gps_lat else None,
                gps_lng=float(loc.gps_lng) + random.uniform(-0.005, 0.005) if loc.gps_lng else None,
                site_timezone="America/Chicago",
            )
            session.add(site)
            sites.append(site)
    await session.flush()
    return sites


async def _create_assets(
    session: AsyncSession,
    org_id: uuid.UUID,
    sites: list[Site],
) -> list[Asset]:
    asset_templates = [
        ("Pump Jack Unit", "Pump Jack", "Lufkin", "C-912D-365-168", "Rod pump artificial lift"),
        ("Compressor Package", "Compressor", "Ariel", "JGJ/2", "Reciprocating gas compressor"),
        ("Production Separator", "Separator", "Exterran", "VS-3P-36x10", "3-phase vertical separator"),
        ("Electric Submersible Pump", "ESP", "Baker Hughes", "Centrilift 400", "Downhole ESP system"),
        ("Chemical Injection Pump", "Injection Pump", "Milton Roy", "MR-PD-200", "Corrosion inhibitor dosing pump"),
        ("SCADA RTU", "RTU", "ABB", "RTU560", "Remote telemetry unit for SCADA"),
        ("Emergency Shutdown Valve", "ESD Valve", "Cameron", "DBC-8", "8-inch ESD ball valve"),
        ("Glycol Dehydrator", "Dehydrator", "Smith Industries", "GD-500", "TEG glycol dehydration unit"),
        ("Tank Level Transmitter", "Transmitter", "Emerson", "Rosemount 5300", "Guided wave radar level"),
        ("Cathodic Protection Rectifier", "Rectifier", "MATCOR", "SPL-12/50", "Impressed current CP rectifier"),
    ]

    assets = []
    for s_idx, site in enumerate(sites):
        # 2-3 assets per site
        n_assets = 2 if s_idx % 3 == 0 else 3
        for a_idx in range(n_assets):
            tpl = asset_templates[(s_idx * 3 + a_idx) % len(asset_templates)]
            asset = Asset(
                org_id=org_id,
                site_id=site.id,
                name=f"{tpl[0]} - {site.name}",
                asset_type=tpl[1],
                manufacturer=tpl[2],
                model=tpl[3],
                serial_number=f"SN-{uuid.uuid4().hex[:8].upper()}",
                install_date=date(
                    random.randint(2018, 2024),
                    random.randint(1, 12),
                    random.randint(1, 28),
                ),
                warranty_expiry=date(
                    random.randint(2025, 2028),
                    random.randint(1, 12),
                    random.randint(1, 28),
                ),
                notes=tpl[4],
            )
            session.add(asset)
            assets.append(asset)
    await session.flush()
    return assets


async def _create_parts(
    session: AsyncSession,
    org_id: uuid.UUID,
) -> list[Part]:
    parts = []
    for pn, desc, cost, loc, stock, reorder, supplier in PARTS_CATALOG:
        part = Part(
            org_id=org_id,
            part_number=pn,
            description=desc,
            unit_cost=cost,
            storage_location=loc,
            stock_quantity=stock,
            reorder_threshold=reorder,
            supplier_name=supplier,
            supplier_part_number=f"SUP-{pn}",
        )
        session.add(part)
        parts.append(part)
    await session.flush()
    return parts


async def _create_part_transactions(
    session: AsyncSession,
    org_id: uuid.UUID,
    parts: list[Part],
    admin_user_id: uuid.UUID,
) -> None:
    for part in parts:
        # Initial stock-in transaction
        txn_in = PartTransaction(
            part_id=part.id,
            org_id=org_id,
            transaction_type=TransactionType.IN,
            quantity=part.stock_quantity + random.randint(5, 20),
            notes="Initial inventory count",
            created_by=admin_user_id,
            created_at=NOW - timedelta(days=60),
        )
        session.add(txn_in)

        # Some usage transactions
        if random.random() > 0.4:
            txn_out = PartTransaction(
                part_id=part.id,
                org_id=org_id,
                transaction_type=TransactionType.OUT,
                quantity=random.randint(1, 5),
                notes="Used on field repair",
                created_by=admin_user_id,
                created_at=NOW - timedelta(days=random.randint(1, 30)),
            )
            session.add(txn_out)

    await session.flush()


async def _create_work_orders(
    session: AsyncSession,
    org_id: uuid.UUID,
    areas: list[Area],
    locations: list[Location],
    sites: list[Site],
    assets: list[Asset],
    users: dict[str, User],
    wo_counter: WOCounter,
    count: int,
) -> list[WorkOrder]:
    work_orders = []
    tech_users = [users.get("tech1"), users.get("tech2"), users.get("tech3")]
    tech_users = [u for u in tech_users if u is not None]
    requester_pool = [users.get("operator"), users.get("supervisor")]
    requester_pool = [u for u in requester_pool if u is not None]

    templates = WO_TEMPLATES[:count]

    for i, tpl in enumerate(templates):
        wo_counter.counter += 1
        created_at = _rand_dt_past(max_days=80)

        # Distribute across areas/locations/sites
        area = areas[i % len(areas)]
        # Find locations in this area
        area_locs = [l for l in locations if l.area_id == area.id]
        location = area_locs[i % len(area_locs)] if area_locs else locations[0]
        # Find sites in this location
        loc_sites = [s for s in sites if s.location_id == location.id]
        site = loc_sites[i % len(loc_sites)] if loc_sites else sites[0]
        # Find assets at this site
        site_assets = [a for a in assets if a.site_id == site.id]
        asset = site_assets[i % len(site_assets)] if site_assets else None

        # Pick a status progression
        progression = STATUS_PROGRESSIONS[i % len(STATUS_PROGRESSIONS)]
        final_status = progression[-1][0]

        requester = requester_pool[i % len(requester_pool)]
        assignee = tech_users[i % len(tech_users)] if len(progression) > 1 else None

        wo = WorkOrder(
            org_id=org_id,
            area_id=area.id,
            location_id=location.id,
            site_id=site.id,
            asset_id=asset.id if asset else None,
            human_readable_number=_wo_number(wo_counter.counter),
            title=tpl["title"],
            description=tpl.get("description"),
            type=tpl["type"],
            priority=tpl["priority"],
            status=final_status,
            requested_by=requester.id,
            assigned_to=assignee.id if assignee else None,
            created_at=created_at,
            safety_flag=tpl.get("safety_flag", False),
            safety_notes=tpl.get("safety_notes"),
            required_cert=tpl.get("required_cert"),
            tags=tpl.get("tags"),
            idempotency_key=f"seed-{org_id}-{i}",
            ack_deadline=_sla_deadline(created_at, tpl["priority"], "ack_minutes"),
            first_update_deadline=_sla_deadline(created_at, tpl["priority"], "first_update_minutes"),
            due_at=_sla_deadline(created_at, tpl["priority"], "resolve_minutes"),
        )

        # Fill in timestamps based on progression
        for status, hours_offset in progression:
            ts = created_at + timedelta(hours=hours_offset)
            if status == WorkOrderStatus.ASSIGNED:
                wo.assigned_at = ts
            elif status == WorkOrderStatus.ACCEPTED:
                wo.accepted_at = ts
            elif status == WorkOrderStatus.IN_PROGRESS:
                wo.in_progress_at = ts
            elif status == WorkOrderStatus.RESOLVED:
                wo.resolved_at = ts
                wo.resolution_summary = "Issue resolved. Equipment operational."
                wo.resolution_details = "Replaced failed component and verified system operation."
            elif status == WorkOrderStatus.VERIFIED:
                wo.verified_at = ts
                wo.verified_by = users.get("supervisor", requester).id
            elif status == WorkOrderStatus.CLOSED:
                wo.closed_at = ts
                wo.closed_by = users.get("admin", requester).id
            elif status == WorkOrderStatus.ESCALATED:
                wo.escalated_at = ts

        session.add(wo)
        work_orders.append(wo)

    await session.flush()
    return work_orders


async def _create_timeline_events(
    session: AsyncSession,
    org_id: uuid.UUID,
    work_orders: list[WorkOrder],
    users: dict[str, User],
) -> int:
    count = 0
    system_user = users.get("admin") or list(users.values())[0]
    tech_users = [users.get("tech1"), users.get("tech2"), users.get("tech3")]
    tech_users = [u for u in tech_users if u is not None]

    for wo_idx, wo in enumerate(work_orders):
        # Status change: CREATED
        te_created = TimelineEvent(
            work_order_id=wo.id,
            org_id=org_id,
            user_id=wo.requested_by,
            event_type=TimelineEventType.STATUS_CHANGE,
            payload={"from": None, "to": "NEW"},
            created_at=wo.created_at,
        )
        session.add(te_created)
        count += 1

        if wo.assigned_at:
            te_assigned = TimelineEvent(
                work_order_id=wo.id,
                org_id=org_id,
                user_id=system_user.id,
                event_type=TimelineEventType.ASSIGNMENT_CHANGE,
                payload={
                    "from": None,
                    "to": str(wo.assigned_to),
                    "status_from": "NEW",
                    "status_to": "ASSIGNED",
                },
                created_at=wo.assigned_at,
            )
            session.add(te_assigned)
            count += 1

        if wo.accepted_at:
            te_accepted = TimelineEvent(
                work_order_id=wo.id,
                org_id=org_id,
                user_id=wo.assigned_to,
                event_type=TimelineEventType.STATUS_CHANGE,
                payload={"from": "ASSIGNED", "to": "ACCEPTED"},
                created_at=wo.accepted_at,
            )
            session.add(te_accepted)
            count += 1

        if wo.in_progress_at:
            te_ip = TimelineEvent(
                work_order_id=wo.id,
                org_id=org_id,
                user_id=wo.assigned_to,
                event_type=TimelineEventType.STATUS_CHANGE,
                payload={"from": "ACCEPTED", "to": "IN_PROGRESS"},
                created_at=wo.in_progress_at,
            )
            session.add(te_ip)
            count += 1

            # Add a note after starting
            te_note = TimelineEvent(
                work_order_id=wo.id,
                org_id=org_id,
                user_id=wo.assigned_to,
                event_type=TimelineEventType.NOTE,
                payload={"text": "On site, beginning assessment."},
                created_at=wo.in_progress_at + timedelta(minutes=15),
            )
            session.add(te_note)
            count += 1

        if wo.status == WorkOrderStatus.WAITING_ON_PARTS:
            te_wop = TimelineEvent(
                work_order_id=wo.id,
                org_id=org_id,
                user_id=wo.assigned_to,
                event_type=TimelineEventType.STATUS_CHANGE,
                payload={"from": "IN_PROGRESS", "to": "WAITING_ON_PARTS"},
                created_at=wo.in_progress_at + timedelta(hours=5) if wo.in_progress_at else wo.created_at + timedelta(hours=8),
            )
            session.add(te_wop)
            count += 1

        if wo.status == WorkOrderStatus.WAITING_ON_OPS:
            te_woo = TimelineEvent(
                work_order_id=wo.id,
                org_id=org_id,
                user_id=wo.assigned_to,
                event_type=TimelineEventType.STATUS_CHANGE,
                payload={"from": "IN_PROGRESS", "to": "WAITING_ON_OPS"},
                created_at=wo.in_progress_at + timedelta(hours=3) if wo.in_progress_at else wo.created_at + timedelta(hours=6),
            )
            session.add(te_woo)
            count += 1

        if wo.resolved_at:
            te_resolved = TimelineEvent(
                work_order_id=wo.id,
                org_id=org_id,
                user_id=wo.assigned_to,
                event_type=TimelineEventType.STATUS_CHANGE,
                payload={"from": "IN_PROGRESS", "to": "RESOLVED"},
                created_at=wo.resolved_at,
            )
            session.add(te_resolved)
            count += 1

        if wo.verified_at:
            te_verified = TimelineEvent(
                work_order_id=wo.id,
                org_id=org_id,
                user_id=wo.verified_by,
                event_type=TimelineEventType.STATUS_CHANGE,
                payload={"from": "RESOLVED", "to": "VERIFIED"},
                created_at=wo.verified_at,
            )
            session.add(te_verified)
            count += 1

        if wo.closed_at:
            te_closed = TimelineEvent(
                work_order_id=wo.id,
                org_id=org_id,
                user_id=wo.closed_by,
                event_type=TimelineEventType.STATUS_CHANGE,
                payload={"from": "VERIFIED", "to": "CLOSED"},
                created_at=wo.closed_at,
            )
            session.add(te_closed)
            count += 1

        if wo.escalated_at:
            te_esc = TimelineEvent(
                work_order_id=wo.id,
                org_id=org_id,
                user_id=system_user.id,
                event_type=TimelineEventType.ESCALATION,
                payload={"reason": "SLA resolve deadline exceeded"},
                created_at=wo.escalated_at,
            )
            session.add(te_esc)
            count += 1

        if wo.safety_flag:
            te_safety = TimelineEvent(
                work_order_id=wo.id,
                org_id=org_id,
                user_id=wo.requested_by,
                event_type=TimelineEventType.SAFETY_FLAG_SET,
                payload={"notes": wo.safety_notes},
                created_at=wo.created_at + timedelta(seconds=1),
            )
            session.add(te_safety)
            count += 1

    await session.flush()
    return count


async def _create_sla_events(
    session: AsyncSession,
    org_id: uuid.UUID,
    work_orders: list[WorkOrder],
) -> int:
    """Create SLA breach events for some work orders."""
    count = 0
    for wo in work_orders:
        # Simulate SLA breach on escalated WOs
        if wo.status == WorkOrderStatus.ESCALATED and wo.escalated_at:
            sla_event = SLAEvent(
                work_order_id=wo.id,
                org_id=org_id,
                event_type=SLAEventType.RESOLVE_BREACH,
                triggered_at=wo.escalated_at - timedelta(minutes=5),
            )
            session.add(sla_event)
            count += 1

        # Simulate ack breach on some IMMEDIATE priority WOs that are still NEW
        if wo.priority == WorkOrderPriority.IMMEDIATE and wo.status == WorkOrderStatus.NEW:
            if wo.ack_deadline and wo.ack_deadline < NOW:
                sla_event = SLAEvent(
                    work_order_id=wo.id,
                    org_id=org_id,
                    event_type=SLAEventType.ACK_BREACH,
                    triggered_at=wo.ack_deadline + timedelta(minutes=1),
                )
                session.add(sla_event)
                count += 1

    await session.flush()
    return count


async def _create_pm_templates(
    session: AsyncSession,
    org_id: uuid.UUID,
    sites: list[Site],
    assets: list[Asset],
) -> list[PMTemplate]:
    templates_data = [
        {
            "title": "Monthly Pump Jack Inspection",
            "description": "Monthly visual and mechanical inspection of pump jack unit. Check stuffing box, bridle, walking beam, counterweights, and prime mover.",
            "recurrence_type": RecurrenceType.MONTHLY,
            "priority": WorkOrderPriority.SCHEDULED,
            "assigned_to_role": PMAssignedRole.TECHNICIAN,
            "checklist_json": {
                "items": [
                    {"label": "Check stuffing box packing", "required": True},
                    {"label": "Inspect polished rod", "required": True},
                    {"label": "Check walking beam for cracks", "required": True},
                    {"label": "Verify counterweight balance", "required": False},
                    {"label": "Grease all fittings", "required": True},
                    {"label": "Check belt tension on prime mover", "required": True},
                    {"label": "Record wellhead pressure", "required": True},
                    {"label": "Record casing pressure", "required": True},
                ]
            },
        },
        {
            "title": "Quarterly Compressor Maintenance",
            "description": "Quarterly preventive maintenance on reciprocating gas compressor package. Oil change, filter replacement, valve inspection.",
            "recurrence_type": RecurrenceType.QUARTERLY,
            "priority": WorkOrderPriority.SCHEDULED,
            "assigned_to_role": PMAssignedRole.TECHNICIAN,
            "required_cert": "Compressor Technician",
            "checklist_json": {
                "items": [
                    {"label": "Change compressor oil", "required": True},
                    {"label": "Replace air filter element", "required": True},
                    {"label": "Inspect suction/discharge valves", "required": True},
                    {"label": "Check packing and piston rings", "required": True},
                    {"label": "Verify vibration levels", "required": True},
                    {"label": "Test safety shutdown system", "required": True},
                    {"label": "Record discharge temperature/pressure", "required": True},
                ]
            },
        },
        {
            "title": "Annual Safety Valve Certification",
            "description": "Annual pop testing and recertification of all pressure relief and safety valves per API 510/ASME guidelines.",
            "recurrence_type": RecurrenceType.ANNUAL,
            "priority": WorkOrderPriority.SCHEDULED,
            "assigned_to_role": PMAssignedRole.SUPERVISOR,
            "required_cert": "API 510",
            "checklist_json": {
                "items": [
                    {"label": "Record valve tag number", "required": True},
                    {"label": "Record set pressure", "required": True},
                    {"label": "Pop test and record actual pop pressure", "required": True},
                    {"label": "Inspect valve seat and disc", "required": True},
                    {"label": "Replace if not within tolerance", "required": True},
                    {"label": "Update valve certification tag", "required": True},
                ]
            },
        },
    ]

    pm_templates = []
    for idx, tpl_data in enumerate(templates_data):
        site = sites[idx % len(sites)] if sites else None
        # Link to first asset at the site
        site_assets = [a for a in assets if a.site_id == site.id] if site else []
        asset = site_assets[0] if site_assets else None

        pm = PMTemplate(
            org_id=org_id,
            site_id=site.id if site else None,
            asset_id=asset.id if asset else None,
            title=tpl_data["title"],
            description=tpl_data["description"],
            type="PREVENTIVE",
            priority=tpl_data["priority"],
            recurrence_type=tpl_data["recurrence_type"],
            assigned_to_role=tpl_data.get("assigned_to_role"),
            required_cert=tpl_data.get("required_cert"),
            checklist_json=tpl_data.get("checklist_json"),
        )
        session.add(pm)
        pm_templates.append(pm)

    await session.flush()

    # Create PM schedules for each template (next 3 occurrences)
    for pm in pm_templates:
        interval_map = {
            RecurrenceType.MONTHLY: 30,
            RecurrenceType.QUARTERLY: 90,
            RecurrenceType.ANNUAL: 365,
        }
        interval = interval_map.get(pm.recurrence_type, 30)
        base = date.today()
        for occ in range(3):
            due = base + timedelta(days=interval * (occ + 1))
            schedule = PMSchedule(
                pm_template_id=pm.id,
                org_id=org_id,
                due_date=due,
                status=PMScheduleStatus.PENDING,
            )
            session.add(schedule)

    await session.flush()
    return pm_templates


async def _create_on_call_schedules(
    session: AsyncSession,
    org_id: uuid.UUID,
    areas: list[Area],
    users: dict[str, User],
) -> int:
    count = 0
    tech_keys = ["tech1", "tech2", "tech3"]
    for area_idx, area in enumerate(areas):
        # Primary on-call rotation (1-week blocks)
        for week in range(4):
            tech_key = tech_keys[week % len(tech_keys)]
            tech = users.get(tech_key)
            if not tech:
                continue
            start = NOW + timedelta(weeks=week)
            end = start + timedelta(weeks=1)
            oc = OnCallSchedule(
                org_id=org_id,
                area_id=area.id,
                user_id=tech.id,
                start_dt=start,
                end_dt=end,
                priority=OnCallPriority.PRIMARY,
            )
            session.add(oc)
            count += 1

        # Secondary on-call
        secondary_key = tech_keys[(area_idx + 1) % len(tech_keys)]
        secondary = users.get(secondary_key)
        if secondary:
            oc2 = OnCallSchedule(
                org_id=org_id,
                area_id=area.id,
                user_id=secondary.id,
                start_dt=NOW,
                end_dt=NOW + timedelta(weeks=4),
                priority=OnCallPriority.SECONDARY,
            )
            session.add(oc2)
            count += 1

    await session.flush()
    return count


async def _create_shift_schedules(
    session: AsyncSession,
    org_id: uuid.UUID,
    areas: list[Area],
    users: dict[str, User],
) -> int:
    count = 0
    shift_defs = [
        ("Day Shift", time(6, 0), time(18, 0), [0, 1, 2, 3, 4]),  # Mon-Fri
        ("Night Shift", time(18, 0), time(6, 0), [0, 1, 2, 3, 4]),  # Mon-Fri
        ("Weekend Day", time(6, 0), time(18, 0), [5, 6]),  # Sat-Sun
    ]

    tech_keys = ["tech1", "tech2", "tech3"]
    for area in areas:
        for s_idx, (name, start, end, days) in enumerate(shift_defs):
            shift = ShiftSchedule(
                org_id=org_id,
                area_id=area.id,
                name=f"{area.name} - {name}",
                start_time=start,
                end_time=end,
                days_of_week=days,
                timezone="America/Chicago",
            )
            session.add(shift)
            await session.flush()

            # Assign a technician to this shift
            tech_key = tech_keys[s_idx % len(tech_keys)]
            tech = users.get(tech_key)
            if tech:
                assignment = UserShiftAssignment(
                    user_id=tech.id,
                    shift_schedule_id=shift.id,
                )
                session.add(assignment)
                count += 1

    await session.flush()
    return count


# ---------------------------------------------------------------------------
# Main seed routine
# ---------------------------------------------------------------------------


async def seed() -> None:
    """Main entry point: seed the database with demo data."""
    async with async_session() as session:
        async with session.begin():
            # Idempotency check
            existing = await session.execute(
                select(Organization).where(Organization.slug == "permian-basin-ops")
            )
            if existing.scalars().first() is not None:
                print("[SKIP] Seed data already exists. Delete organizations to re-seed.")
                return

            print("=" * 60)
            print("  Oilfield CMMS - Database Seed Script")
            print("=" * 60)

            # ==============================================================
            # Organization 1: Permian Basin Operations (extensive data)
            # ==============================================================
            print("\n--- Organization 1: Permian Basin Operations ---")

            org1 = await _create_org(
                session, "Permian Basin Operations", "permian-basin-ops"
            )
            print(f"  Organization: {org1.name} ({org1.id})")

            wo_counter1 = await _create_wo_counter(session, org1.id)
            print(f"  WO Counter: year={wo_counter1.year}")

            users1 = await _create_users(session, org1.id, "apachecorp")
            print(f"  Users: {len(users1)} created")
            for label, user in users1.items():
                print(f"    {user.role.value:<15} {user.email}")

            areas1 = await _create_areas(session, org1.id)
            print(f"  Areas: {len(areas1)} created")

            # Assign all non-readonly users to all areas
            from app.models.user import UserAreaAssignment
            area_assign_count = 0
            for _label, u in users1.items():
                if u.role.value in ("READ_ONLY", "COST_ANALYST"):
                    continue
                for area in areas1:
                    session.add(UserAreaAssignment(user_id=u.id, area_id=area.id))
                    area_assign_count += 1
            await session.flush()
            print(f"  Area Assignments: {area_assign_count} created")

            locations1 = await _create_locations(
                session, org1.id, areas1, PERMIAN_GPS
            )
            print(f"  Locations: {len(locations1)} created")

            sites1 = await _create_sites(session, org1.id, locations1)
            print(f"  Sites: {len(sites1)} created")

            assets1 = await _create_assets(session, org1.id, sites1)
            print(f"  Assets: {len(assets1)} created")

            parts1 = await _create_parts(session, org1.id)
            print(f"  Parts: {len(parts1)} created")

            await _create_part_transactions(
                session, org1.id, parts1, users1["admin"].id
            )
            print("  Part transactions: created")

            wos1 = await _create_work_orders(
                session,
                org1.id,
                areas1,
                locations1,
                sites1,
                assets1,
                users1,
                wo_counter1,
                count=20,
            )
            print(f"  Work Orders: {len(wos1)} created")
            for wo in wos1:
                print(
                    f"    {wo.human_readable_number}  {wo.status.value:<18} "
                    f"{wo.priority.value:<12} {'SAFETY' if wo.safety_flag else ''}"
                )

            te_count1 = await _create_timeline_events(
                session, org1.id, wos1, users1
            )
            print(f"  Timeline Events: {te_count1} created")

            sla_count1 = await _create_sla_events(session, org1.id, wos1)
            print(f"  SLA Events: {sla_count1} created")

            pm_count1 = await _create_pm_templates(
                session, org1.id, sites1, assets1
            )
            print(f"  PM Templates: {len(pm_count1)} created (with schedules)")

            oc_count1 = await _create_on_call_schedules(
                session, org1.id, areas1, users1
            )
            print(f"  On-Call Schedules: {oc_count1} created")

            shift_count1 = await _create_shift_schedules(
                session, org1.id, areas1, users1
            )
            print(f"  Shift Assignments: {shift_count1} created")

            # ==============================================================
            # Organization 2: Eagle Ford Services (minimal data)
            # ==============================================================
            print("\n--- Organization 2: Eagle Ford Services ---")

            org2 = await _create_org(
                session, "Eagle Ford Services", "eagle-ford-services"
            )
            print(f"  Organization: {org2.name} ({org2.id})")

            wo_counter2 = await _create_wo_counter(session, org2.id)
            print(f"  WO Counter: year={wo_counter2.year}")

            users2 = await _create_users(session, org2.id, "eagle-ford-services")
            print(f"  Users: {len(users2)} created")
            for label, user in users2.items():
                print(f"    {user.role.value:<15} {user.email}")

            areas2 = await _create_areas(session, org2.id)
            print(f"  Areas: {len(areas2)} created")

            area_assign_count2 = 0
            for _label, u in users2.items():
                if u.role.value in ("READ_ONLY", "COST_ANALYST"):
                    continue
                for area in areas2:
                    session.add(UserAreaAssignment(user_id=u.id, area_id=area.id))
                    area_assign_count2 += 1
            await session.flush()
            print(f"  Area Assignments: {area_assign_count2} created")

            locations2 = await _create_locations(
                session, org2.id, areas2, EAGLE_FORD_GPS
            )
            print(f"  Locations: {len(locations2)} created")

            sites2 = await _create_sites(session, org2.id, locations2)
            print(f"  Sites: {len(sites2)} created")

            assets2 = await _create_assets(session, org2.id, sites2)
            print(f"  Assets: {len(assets2)} created")

            parts2 = await _create_parts(session, org2.id)
            print(f"  Parts: {len(parts2)} created")

            await _create_part_transactions(
                session, org2.id, parts2, users2["admin"].id
            )
            print("  Part transactions: created")

            wos2 = await _create_work_orders(
                session,
                org2.id,
                areas2,
                locations2,
                sites2,
                assets2,
                users2,
                wo_counter2,
                count=5,
            )
            print(f"  Work Orders: {len(wos2)} created")
            for wo in wos2:
                print(
                    f"    {wo.human_readable_number}  {wo.status.value:<18} "
                    f"{wo.priority.value:<12} {'SAFETY' if wo.safety_flag else ''}"
                )

            te_count2 = await _create_timeline_events(
                session, org2.id, wos2, users2
            )
            print(f"  Timeline Events: {te_count2} created")

            sla_count2 = await _create_sla_events(session, org2.id, wos2)
            print(f"  SLA Events: {sla_count2} created")

            pm_count2 = await _create_pm_templates(
                session, org2.id, sites2, assets2
            )
            print(f"  PM Templates: {len(pm_count2)} created (with schedules)")

            oc_count2 = await _create_on_call_schedules(
                session, org2.id, areas2, users2
            )
            print(f"  On-Call Schedules: {oc_count2} created")

            shift_count2 = await _create_shift_schedules(
                session, org2.id, areas2, users2
            )
            print(f"  Shift Assignments: {shift_count2} created")

            # ==============================================================
            # Summary
            # ==============================================================
            print("\n" + "=" * 60)
            print("  SEED COMPLETE")
            print("=" * 60)
            print(f"""
  Organizations:     2
  Users:             {len(users1) + len(users2)}
  Areas:             {len(areas1) + len(areas2)}
  Locations:         {len(locations1) + len(locations2)}
  Sites:             {len(sites1) + len(sites2)}
  Assets:            {len(assets1) + len(assets2)}
  Parts:             {len(parts1) + len(parts2)}
  Work Orders:       {len(wos1) + len(wos2)}
  Timeline Events:   {te_count1 + te_count2}
  SLA Events:        {sla_count1 + sla_count2}
  PM Templates:      {len(pm_count1) + len(pm_count2)}
  On-Call Schedules: {oc_count1 + oc_count2}
  Shift Assignments: {shift_count1 + shift_count2}

  Default Credentials:
  ────────────────────────────────────────
  Org 1 (Permian Basin Operations):
    Admin:       admin@apachecorp.com / admin123!
    Supervisor:  supervisor@apachecorp.com / supervisor123!
    Operator:    operator@apachecorp.com / operator123!
    Tech:        tech1@apachecorp.com / tech123!

  Org 2 (Eagle Ford Services):
    Admin:       admin@eagle-ford-services.com / admin123!
    Supervisor:  supervisor@eagle-ford-services.com / supervisor123!
""")


def main() -> None:
    asyncio.run(seed())


if __name__ == "__main__":
    main()
