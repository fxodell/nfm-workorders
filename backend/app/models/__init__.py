"""ORM models package.

Importing this module registers every model with the SQLAlchemy ``Base``
metadata, which is required for Alembic auto-generation and
``Base.metadata.create_all()`` to discover all tables.
"""

from app.models.area import Area  # noqa: F401
from app.models.asset import Asset  # noqa: F401
from app.models.audit_log import AuditLog  # noqa: F401
from app.models.budget import AreaBudget  # noqa: F401
from app.models.incentive import (  # noqa: F401
    IncentiveProgram,
    UserIncentiveScore,
)
from app.models.location import Location  # noqa: F401
from app.models.org import Organization, WOCounter  # noqa: F401
from app.models.part import Part, PartTransaction  # noqa: F401
from app.models.pm import PMSchedule, PMTemplate  # noqa: F401
from app.models.shift import ShiftSchedule, UserShiftAssignment  # noqa: F401
from app.models.site import Site  # noqa: F401
from app.models.sla import SLAEvent  # noqa: F401
from app.models.user import (  # noqa: F401
    OnCallSchedule,
    TechnicianCertification,
    User,
    UserAreaAssignment,
    UserNotificationPref,
    UserPermission,
)
from app.models.work_order import (  # noqa: F401
    Attachment,
    LaborLog,
    TimelineEvent,
    WorkOrder,
    WorkOrderPartUsed,
)

__all__ = [
    "Area",
    "AreaBudget",
    "Asset",
    "Attachment",
    "AuditLog",
    "IncentiveProgram",
    "LaborLog",
    "Location",
    "OnCallSchedule",
    "Organization",
    "PMSchedule",
    "PMTemplate",
    "Part",
    "PartTransaction",
    "SLAEvent",
    "ShiftSchedule",
    "Site",
    "TechnicianCertification",
    "TimelineEvent",
    "User",
    "UserAreaAssignment",
    "UserIncentiveScore",
    "UserNotificationPref",
    "UserPermission",
    "UserShiftAssignment",
    "WOCounter",
    "WorkOrder",
    "WorkOrderPartUsed",
]
